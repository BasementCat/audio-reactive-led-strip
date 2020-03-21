import time

import numpy as np
from scipy.ndimage.filters import gaussian_filter1d
import aubio

from app import Task
from app.lib.dsp import create_mel_bank, ExpFilter
from app.lib.misc import FPSCounter
from app.lib.network import send_monitor


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

    def run(self, data):
        audio_samples = data.get('raw_audio')
        if audio_samples is None:
            return
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
                data['audio'] = output

            send_monitor(None, 'AUDIO', bins=list(output))


class BeatProcessor(Processor):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fps = FPSCounter('Beat Processor')
        self.win_s = 1024
        self.hop_s = self.frames_per_buffer = int(self.config['MIC_RATE'] / self.config['FPS'])
        self.onset_detect = aubio.onset('energy', self.win_s, self.hop_s, self.config['MIC_RATE'])
        self.beat_detect = aubio.tempo('hfc', self.win_s, self.hop_s, self.config['MIC_RATE'])

    def run(self, data):
        audio_samples = data.get('raw_audio')
        if audio_samples is None:
            return
        with self.fps:
            data.update({
                'is_onset': True if self.onset_detect(audio_samples) else False,
                'is_beat': True if self.beat_detect(audio_samples) else False,
                })

            # if is_onset:
            #     # print("onset", self.onset_detect.get_last_s())
            #     send_to('@output', 'onset')
            # # if is_beat:
            # #     print("beat", self.beat_detect.get_last_s())


class PitchProcessor(Processor):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fps = FPSCounter('Pitch Processor')
        self.win_s = 1024
        self.hop_s = self.frames_per_buffer = int(self.config['MIC_RATE'] / self.config['FPS'])
        self.pitch_detect = aubio.pitch('yin', self.win_s, self.hop_s, self.config['MIC_RATE'])
        self.pitch_detect.set_unit('midi')
        # self.pitch_detect.set_tolerance(1)
        self.buffer = []
        self.buffer_len = 3

    def run(self, data):
        audio_samples = data.get('raw_audio')
        if audio_samples is None:
            return
        with self.fps:
            pitch = self.pitch_detect(audio_samples)[0]
            confidence = self.pitch_detect.get_confidence()
            # print('{:1.5f} {:s}'.format(confidence, '*' * int(pitch)))
            if confidence > 0:
                self.buffer.append(pitch)
                self.buffer = self.buffer[-self.buffer_len:]

            if len(self.buffer) == self.buffer_len:
                avg = sum(self.buffer) / len(self.buffer)
                data['pitch'] = avg
            else:
                data['pitch'] = None


class IdleProcessor(Processor):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fps = FPSCounter('Idle Processor')
        self.idle_since = None
        self.dead_since = None

    def run(self, data):
        audio = data.get('audio')
        if audio is None:
            return
        threshold = self.config.get('IDLE_THRESHOLD', 0.1)
        v_sum = np.sum(audio)
        v_avg = v_sum / len(audio)
        data.update({'audio_v_sum': v_sum, 'audio_v_avg': v_avg})
        if v_avg < threshold:
            self.idle_since = self.idle_since or time.time()
            data['idle_for'] = time.time() - self.idle_since
        else:
            self.idle_since = None
            data['idle_for'] = None

        if v_sum == 0:
            self.dead_since = self.dead_since or time.time()
            data['dead_for'] = time.time() - self.dead_since
        else:
            self.dead_since = None
            data['dead_for'] = None
