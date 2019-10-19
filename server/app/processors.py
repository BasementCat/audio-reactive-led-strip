import numpy as np
from scipy.ndimage.filters import gaussian_filter1d
import aubio

from app import Task
from app.lib.dsp import create_mel_bank, ExpFilter
from app.lib.pubsub import subscribe, publish
from app.lib.misc import FPSCounter


class Processor(Task):
    pass


class SmoothingProcessor(Processor):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fps = FPSCounter('Smoothing Processor')
        self.samples_per_frame = int(self.config['MIC_RATE'] / self.config['FPS'])
        self.y_roll = np.random.rand(self.config['N_ROLLING_HISTORY'], self.samples_per_frame) / 1e16
        self.fft_window = np.hamming(int(self.config['MIC_RATE'] / self.config['FPS']) * self.config['N_ROLLING_HISTORY'])
        self.mel_y, self.mel_x = create_mel_bank(self.config)
        self.mel_gain = ExpFilter(np.tile(1e-1, self.config['N_FFT_BINS']),
                         alpha_decay=0.01, alpha_rise=0.99)
        self.mel_smoothing = ExpFilter(np.tile(1e-1, self.config['N_FFT_BINS']),
                         alpha_decay=0.5, alpha_rise=0.99)

        subscribe('raw_audio', self.handle)

    def handle(self, audio_samples):
        with self.fps:
            # Normalize samples between 0 and 1
            y = audio_samples / 2.0**15
            # Construct a rolling window of audio samples
            self.y_roll[:-1] = self.y_roll[1:]
            self.y_roll[-1, :] = np.copy(y)
            y_data = np.concatenate(self.y_roll, axis=0).astype(np.float32)

            output = None
            
            vol = np.max(np.abs(y_data))
            if vol < self.config['MIN_VOLUME_THRESHOLD']:
                # print('No audio input. Volume below threshold. Volume:', vol)
                output = np.tile(0, self.config['N_FFT_BINS'])
            else:
                # Transform audio input into the frequency domain
                N = len(y_data)
                N_zeros = 2**int(np.ceil(np.log2(N))) - N
                # Pad with zeros until the next power of two
                y_data *= self.fft_window
                y_padded = np.pad(y_data, (0, N_zeros), mode='constant')
                YS = np.abs(np.fft.rfft(y_padded)[:N // 2])
                # Construct a Mel filterbank from the FFT data
                mel = np.atleast_2d(YS).T * self.mel_y.T
                # Scale data to values more suitable for visualization
                # mel = np.sum(mel, axis=0)
                mel = np.sum(mel, axis=0)
                mel = mel**2.0
                # Gain normalization
                self.mel_gain.update(np.max(gaussian_filter1d(mel, sigma=1.0)))
                mel /= self.mel_gain.value
                mel = self.mel_smoothing.update(mel)
                output = mel

            if output is not None:
                publish('audio', output)


class BeatProcessor(Processor):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fps = FPSCounter('Beat Processor')
        self.win_s = 1024
        self.hop_s = self.frames_per_buffer = int(self.config['MIC_RATE'] / self.config['FPS'])
        self.onset_detect = aubio.onset('energy', self.win_s, self.hop_s, self.config['MIC_RATE'])
        self.beat_detect = aubio.tempo('hfc', self.win_s, self.hop_s, self.config['MIC_RATE'])

        subscribe('raw_audio', self.handle)

    def handle(self, audio_samples):
        with self.fps:
            if self.onset_detect(audio_samples):
                publish('onset')
            if self.beat_detect(audio_samples):
                publish('beat')

            # if is_onset:
            #     # print("onset", self.onset_detect.get_last_s())
            #     send_to('@output', 'onset')
            # # if is_beat:
            # #     print("beat", self.beat_detect.get_last_s())