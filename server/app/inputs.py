import time

import numpy as np
import pyaudio

from app.lib.threads import Thread, send_to
from app.lib.misc import FPSCounter


class DeviceInputThread(Thread):
    def run(self):
        fps = FPSCounter("Audio input")
        p = pyaudio.PyAudio()
        frames_per_buffer = int(self.config['MIC_RATE'] / self.config['FPS'])
        stream = p.open(format=pyaudio.paInt16,
                        channels=1,
                        rate=self.config['MIC_RATE'],
                        input=True,
                        frames_per_buffer=frames_per_buffer,
                        # TODO: configurable
                        input_device_index=7
                        # input_device_index=8
                        )
        overflows = 0
        prev_ovf_time = time.time()
        while not self.stop_event.is_set():
            with fps:
                try:
                    y = np.fromstring(stream.read(frames_per_buffer, exception_on_overflow=False), dtype=np.int16)
                    y = y.astype(np.float32)
                    stream.read(stream.get_read_available(), exception_on_overflow=False)
                    send_to('@processor', 'audio', y)
                except IOError:
                    overflows += 1
                    if time.time() > prev_ovf_time + 1:
                        prev_ovf_time = time.time()
                        print('Audio buffer has overflowed {} times'.format(overflows))
        stream.stop_stream()
        stream.close()
        p.terminate()
