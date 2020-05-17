import time
import sys
import socket
import logging
import select
import re
import multiprocessing
from multiprocessing.queues import Empty
from threading import Lock
import os
import signal

import numpy as np

from app import Task, NoData
from app.lib.misc import FPSCounter


logger = logging.getLogger(__name__)

# Audio libs
try:
    import pyaudio
except ImportError:
    logger.info("PyAudio is not installed")

try:
    import alsaaudio
except ImportError:
    logger.info("PyAlsaAudio is not installed")


class Input(Task):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fps = FPSCounter("Audio input: " + self.name)
        self.frames_per_buffer = int(self.config['MIC_RATE'] / self.config['FPS'])


def _get_device_index(valid_input_devices, in_device):
    device_num = None
    try:
        device = int(in_device)
        device_num = device if device in valid_input_devices else None
    except (TypeError, ValueError):
        device = in_device
        for k, v in valid_input_devices.items():
            if device == v:
                device_num = k
                break
        if device_num is None:
            for k, v in valid_input_devices.items():
                if device in v:
                    device_num = k
                    break

    if device_num is None:
        print(f"Invalid device {in_device} - valid devices are:")
        for k in sorted(valid_input_devices.keys()):
            print(f"{k}: {valid_input_devices[k]}")
        sys.exit(1)

    return device_num


def _pa_get_device_index(in_device, pa=None):
    pa = pa or pyaudio.PyAudio()

    valid_input_devices = {}

    for i in range(pa.get_device_count()):
        info = pa.get_device_info_by_index(i)
        if info.get('maxInputChannels') > 0:
            valid_input_devices[i] = info.get('name')

    return _get_device_index(valid_input_devices, in_device)


def _pa_device_input_process(wd, device, mic_rate, frames_per_buffer, queue, stop_event):
    pa = pyaudio.PyAudio()
    device_num = _pa_get_device_index(device, pa=pa)
    stream = pa.open(format=pyaudio.paInt16,
                    channels=1,
                    rate=mic_rate,
                    input=True,
                    frames_per_buffer=frames_per_buffer,
                    input_device_index=device_num
                    )
    overflows = 0
    prev_ovf_time = time.time()

    try:
        while not stop_event.is_set():
            wd.value = time.time()
            try:
                queue.put(stream.read(frames_per_buffer, exception_on_overflow=False))
                stream.read(stream.get_read_available(), exception_on_overflow=False)
            except IOError:
                overflows += 1
                if time.time() > prev_ovf_time + 1:
                    prev_ovf_time = time.time()
                    print('Audio buffer has overflowed {} times'.format(overflows))
    finally:
        stream.stop_stream()
        stream.close()
        pa.terminate()


class PyAudioDeviceInput(Input):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Validate that the configured input device is ok
        # Actually can't do validation here, breaks pyaudio w/ multiprocessing
        # _pa_get_device_index(self.config['INPUT_DEVICE'])
        self.process = None
        self.watchdog = multiprocessing.Value('d', 0.0)
        self.stop_event = multiprocessing.Event()
        self.queue = multiprocessing.Queue(maxsize=1)

    def start_process(self):
        if self.process:
            if self.process.is_alive():
                if time.time() - self.watchdog.value < 0.1:
                    return
                else:
                    logger.error("watchdog not updated for >1s")
                    os.kill(self.process.pid, signal.SIGKILL)
            else:
                logger.error("Process is not alive")

        self.watchdog.value = time.time() + 0.5
        self.process = multiprocessing.Process(target=_pa_device_input_process, args=(self.watchdog, self.config['INPUT_DEVICE'], self.config['MIC_RATE'], self.frames_per_buffer, self.queue, self.stop_event))
        self.process.start()

    def start(self, data):
        self.start_process()

    def stop(self):
        self.stop_event.set()
        if self.process:
            self.process.join()

    def run(self, data):
        self.start_process()
        try:
            raw_data = self.queue.get(block=False)
            with self.fps:
                raw_data = np.fromstring(raw_data, dtype=np.int16)
                raw_data = raw_data.astype(np.float32)
                data['raw_audio'] = raw_data
        except Empty:
            raise NoData()


def _alsa_get_device(in_device):
    devices = dict(enumerate(alsaaudio.pcms(alsaaudio.PCM_CAPTURE)))
    return devices[_get_device_index(devices, in_device)]


class AlsaDeviceInput(Input):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.buffer = b''
        self.device = alsaaudio.PCM(alsaaudio.PCM_CAPTURE, alsaaudio.PCM_NONBLOCK, device=_alsa_get_device(self.config['INPUT_DEVICE']))
        # Set attributes: Mono, 44100 Hz, 16 bit little endian samples
        self.device.setchannels(1)
        self.device.setrate(self.config['MIC_RATE'])
        self.device.setformat(alsaaudio.PCM_FORMAT_S16_LE)
        self.device.setperiodsize(self.frames_per_buffer)

    def start(self, data):
        pass

    def stop(self):
        pass

    def run(self, data):
        num_frames, frame_data = self.device.read()
        if num_frames:
            self.buffer += frame_data

        offset = self.frames_per_buffer * 2
        if len(self.buffer) < offset:
            raise NoData()

        with self.fps:
            raw_data = self.buffer[:offset]
            self.buffer = self.buffer[offset:]
            raw_data = np.frombuffer(raw_data, dtype=np.int16)
            raw_data = raw_data.astype(np.float32)
            data['raw_audio'] = raw_data
