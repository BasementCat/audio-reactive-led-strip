import time
import sys
import socket
import logging
import select
import re

import numpy as np
import pyaudio

from app import Task
from app.lib.misc import FPSCounter


logger = logging.getLogger(__name__)


class Input(Task):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fps = FPSCounter("Audio input: " + self.name)
        self.frames_per_buffer = int(self.config['MIC_RATE'] / self.config['FPS'])


class DeviceInput(Input):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.p = pyaudio.PyAudio()
        valid_input_devices = {}

        for i in range(self.p.get_device_count()):
            info = self.p.get_device_info_by_index(i)
            if info.get('maxInputChannels') > 0:
                valid_input_devices[i] = info.get('name')

        device_num = None
        try:
            device = int(self.config.get('INPUT_DEVICE'))
            device_num = device if device in valid_input_devices else None
        except (TypeError, ValueError):
            device = self.config.get('INPUT_DEVICE')
            for k, v in valid_input_devices.items():
                if device in v:
                    device_num = k
                    break

        if not device_num:
            print(f"Invalid device {device} - valid devices are:")
            for k in sorted(valid_input_devices.keys()):
                print(f"{k}: {valid_input_devices[k]}")
            sys.exit(1)

        self.stream = self.p.open(format=pyaudio.paInt16,
                        channels=1,
                        rate=self.config['MIC_RATE'],
                        input=True,
                        frames_per_buffer=self.frames_per_buffer,
                        input_device_index=device_num
                        )
        self.overflows = 0
        self.prev_ovf_time = time.time()

    def run(self, data):
        with self.fps:
            try:
                y = np.fromstring(self.stream.read(self.frames_per_buffer, exception_on_overflow=False), dtype=np.int16)
                y = y.astype(np.float32)
                self.stream.read(self.stream.get_read_available(), exception_on_overflow=False)
                data['raw_audio'] = y
            except IOError:
                self.overflows += 1
                if time.time() > self.prev_ovf_time + 1:
                    self.prev_ovf_time = time.time()
                    print('Audio buffer has overflowed {} times'.format(self.overflows))

    def stop(self):
        self.stream.stop_stream()
        self.stream.close()
        self.p.terminate()
