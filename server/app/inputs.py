import time

import numpy as np
import pyaudio

from app import Task
from app.lib.pubsub import publish
from app.lib.misc import FPSCounter



class Input(Task):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fps = FPSCounter("Audio input: " + self.name)
        self.frames_per_buffer = int(self.config['MIC_RATE'] / self.config['FPS'])


class DeviceInput(Input):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.p = pyaudio.PyAudio()
        self.stream = self.p.open(format=pyaudio.paInt16,
                        channels=1,
                        rate=self.config['MIC_RATE'],
                        input=True,
                        frames_per_buffer=self.frames_per_buffer,
                        # TODO: configurable
                        input_device_index=7
                        # input_device_index=8
                        )
        self.overflows = 0
        self.prev_ovf_time = time.time()

    def run(self):
        with self.fps:
            try:
                y = np.fromstring(self.stream.read(self.frames_per_buffer, exception_on_overflow=False), dtype=np.int16)
                y = y.astype(np.float32)
                self.stream.read(self.stream.get_read_available(), exception_on_overflow=False)
                publish('raw_audio', y)
            except IOError:
                self.overflows += 1
                if time.time() > self.prev_ovf_time + 1:
                    self.prev_ovf_time = time.time()
                    print('Audio buffer has overflowed {} times'.format(self.overflows))

    def stop(self):
        self.stream.stop_stream()
        self.stream.close()
        self.p.terminate()
