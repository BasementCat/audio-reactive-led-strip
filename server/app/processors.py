import queue

import numpy as np
from scipy.ndimage.filters import gaussian_filter1d

from app.lib.dsp import create_mel_bank, ExpFilter
from app.lib.threads import Thread, send_to
from app.lib.misc import FPSCounter


class ProcessorThread(Thread):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.is_processor = True
        self.unrestrict_queue()


class SmoothingProcessorThread(ProcessorThread):
    def run(self):
        fps = FPSCounter('Smoothing Processor')
        samples_per_frame = int(self.config['MIC_RATE'] / self.config['FPS'])
        y_roll = np.random.rand(self.config['N_ROLLING_HISTORY'], samples_per_frame) / 1e16
        fft_window = np.hamming(int(self.config['MIC_RATE'] / self.config['FPS']) * self.config['N_ROLLING_HISTORY'])
        mel_y, mel_x = create_mel_bank(self.config)
        mel_gain = ExpFilter(np.tile(1e-1, self.config['N_FFT_BINS']),
                         alpha_decay=0.01, alpha_rise=0.99)
        mel_smoothing = ExpFilter(np.tile(1e-1, self.config['N_FFT_BINS']),
                         alpha_decay=0.5, alpha_rise=0.99)

        while not self.stop_event.is_set():
            with fps:
                try:
                    fn, args, kwargs = self.queue.get(timeout=0.25)
                    if fn != 'audio':
                        continue
                    audio_samples = args[0]
                except queue.Empty:
                    continue

                # Normalize samples between 0 and 1
                y = audio_samples / 2.0**15
                # Construct a rolling window of audio samples
                y_roll[:-1] = y_roll[1:]
                y_roll[-1, :] = np.copy(y)
                y_data = np.concatenate(y_roll, axis=0).astype(np.float32)

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
                    y_data *= fft_window
                    y_padded = np.pad(y_data, (0, N_zeros), mode='constant')
                    YS = np.abs(np.fft.rfft(y_padded)[:N // 2])
                    # Construct a Mel filterbank from the FFT data
                    mel = np.atleast_2d(YS).T * mel_y.T
                    # Scale data to values more suitable for visualization
                    # mel = np.sum(mel, axis=0)
                    mel = np.sum(mel, axis=0)
                    mel = mel**2.0
                    # Gain normalization
                    mel_gain.update(np.max(gaussian_filter1d(mel, sigma=1.0)))
                    mel /= mel_gain.value
                    mel = mel_smoothing.update(mel)
                    output = mel

                if output is not None:
                    send_to('@output', 'audio', output)


# # TESTING
# import aubio
# import time
# class BeatProcessorThread(ProcessorThread):
#     def run(self):
#         # TODO: configurable? sample rate is part of config
#         samplerate, win_s, hop_s = 44100, 1024, 512
#         # actually this
#         hop_s = frames_per_buffer = int(self.config['MIC_RATE'] / self.config['FPS'])
#         # maybe?
#         win_s = 1024
#         beat_detect = aubio.tempo('specdiff', win_s, hop_s, samplerate)
#         now = time.time()

#         use_methods = ['energy','hfc','complex','phase','wphase','specdiff','kl','mkl','specflux']
#         # use_methods = ['energy', 'kl', 'specflux']
#         use_methods = []
#         methods = {n: aubio.tempo(n, win_s, hop_s, samplerate) for n in use_methods}
#         rolling_beats_n = 40
#         rolling_beats = {n: np.tile(-1.0, rolling_beats_n) for n in use_methods}
#         filtered_beats = {n: np.tile(-1.0, rolling_beats_n) for n in use_methods}
#         bpms = {n: np.inf for n in use_methods}
#         next_beat = None
#         last_beat_reset = time.time()

#         tempmethod = aubio.tempo('complex', 8192, hop_s, samplerate)
#         onset = aubio.onset('energy', 1024, hop_s, samplerate)

#         # rolling_beats_n = 60
#         # rolling_beats = np.tile(-1.0, rolling_beats_n)
#         # bpm = np.inf
#         # next_beat = None

#         while not self.stop_event.is_set():
#             try:
#                 fn, args, kwargs = self.queue.get(block=False)
#                 if fn != 'audio':
#                     continue
#                 audio_samples = args[0]
#             except queue.Empty:
#                 pass
#             else:
#                 # intensity = np.max(audio_samples)
#                 # if intensity < 0.7:
#                 #     continue
#                 for name, method in methods.items():
#                     is_beat = method(audio_samples)
#                     if is_beat:
#                         rolling_beats[name] = np.roll(rolling_beats[name], -1)
#                         rolling_beats[name][-1] = method.get_last_s()
#                         filtered_beats[name] = rolling_beats[name][rolling_beats[name] >= 0]
#                         filtered_beats[name] = filtered_beats[name][abs(filtered_beats[name] - np.mean(filtered_beats[name])) > 1 * np.std(filtered_beats[name])]
#                         if len(filtered_beats[name]) > 0:
#                             bpms[name] = np.median(60. / np.diff(filtered_beats[name]))

#                 if tempmethod(audio_samples):
#                     print("real beat", time.time())

#                 if onset(audio_samples):
#                     print("onset", time.time())

#             bpm = np.median(list(bpms.values()))
#             if np.isfinite(bpm):
#                 if next_beat is None or (time.time() - last_beat_reset > 2):
#                     last_beat_reset = time.time()
#                     last_beats = [b[-1] for b in filtered_beats.values() if len(b)]
#                     last_temp = max(last_beats)
#                     last_beats = [v for v in last_beats if v > (last_temp - (60.0 / bpm))]
#                     next_beat = now + np.median(last_beats)
#                     # next_beat = now + max(last_beats)
#                     while next_beat <= time.time():
#                         next_beat += (60.0 / bpm)
#                     # print("nb set", next_beat)
#                 elif next_beat <= time.time():
#                     # print(next_beat)
#                     next_beat += (60.0 / bpm)



#             #     is_beat = beat_detect(audio_samples)
#             #     if is_beat:
#             #         print("real beat", beat_detect.get_last_s())
#             #         rolling_beats = np.roll(rolling_beats, -1)
#             #         rolling_beats[rolling_beats_n - 1] = beat_detect.get_last_s()
#             #         filtered_beats = rolling_beats[rolling_beats >= 0]
#             #         filtered_beats = filtered_beats[abs(filtered_beats - np.mean(filtered_beats)) < 1 * np.std(filtered_beats)]
#             #         if len(filtered_beats) > 0:
#             #             # print(filtered_beats)
#             #             bpms = 60./np.diff(filtered_beats)
#             #             bpm = np.median(bpms)
#             #             # print(bpm)

#             #             if bpm and np.isfinite(bpm):  # and not (next_beat and np.isfinite(next_beat)):
#             #                 next_beat = now + filtered_beats[-1] + (60.0 / bpm)
#             #                 if np.isfinite(next_beat):
#             #                     while next_beat <= time.time():
#             #                         next_beat += (60.0 / bpm)
#             #                 else:
#             #                     next_beat = None

#             # if next_beat and np.isfinite(next_beat) and time.time() >= next_beat:
#             #     # print("beat", next_beat)
#             #     if bpm and np.isfinite(bpm):
#             #         next_beat += (60.0 / bpm)
#             #     else:
#             #         next_beat = None


# Testing2
import aubio
class BeatProcessorThread(ProcessorThread):
    def run(self):
        fps = FPSCounter('Beat Processor')
        win_s = hop_s = frames_per_buffer = int(self.config['MIC_RATE'] / self.config['FPS'])
        beat_detect = aubio.tempo('hfc', 1024, hop_s, 44100)
        onset_detect = aubio.onset('energy', 1024, hop_s, 44100)
        while not self.stop_event.is_set():
            with fps:
                try:
                    fn, args, kwargs = self.queue.get(timeout=0.25)
                    if fn != 'audio':
                        continue
                    audio_samples = args[0]
                except queue.Empty:
                    pass
                else:
                    is_beat = beat_detect(audio_samples)
                    is_onset = onset_detect(audio_samples)
                    if is_onset:
                        # print("onset", onset_detect.get_last_s())
                        send_to('@output', 'onset')
                    # if is_beat:
                    #     print("beat", beat_detect.get_last_s())