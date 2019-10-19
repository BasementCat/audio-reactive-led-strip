import queue
import socket

import numpy as np
from scipy.ndimage.filters import gaussian_filter1d

from . import OutputThread
from app.lib.dsp import ExpFilter


# TODO: put this crap in a library
def memoize(function):
    """Provides a decorator for memoizing functions"""
    from functools import wraps
    memo = {}

    @wraps(function)
    def wrapper(*args):
        if args in memo:
            return memo[args]
        else:
            rv = function(*args)
            memo[args] = rv
            return rv
    return wrapper


@memoize
def _normalized_linspace(size):
    return np.linspace(0, 1, size)


def interpolate(y, new_length):
    """Intelligently resizes the array by linearly interpolating the values

    Parameters
    ----------
    y : np.array
        Array that should be resized

    new_length : int
        The length of the new interpolated array

    Returns
    -------
    z : np.array
        New array with length of new_length that contains the interpolated
        values of y.
    """
    if len(y) == new_length:
        return y
    x_old = _normalized_linspace(len(y))
    x_new = _normalized_linspace(new_length)
    z = np.interp(x_new, x_old, y)
    return z


class BaseLEDThread(OutputThread):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # TODO: From output config
        self.config['N_PIXELS'] = 120

        self.p = np.tile(1.0, (3, self.config['N_PIXELS'] // 2))
        self.gain = ExpFilter(np.tile(0.01, self.config['N_FFT_BINS']),
                     alpha_decay=0.001, alpha_rise=0.99)
        self.common_mode = ExpFilter(np.tile(0.01, self.config['N_PIXELS'] // 2),
                     alpha_decay=0.99, alpha_rise=0.01)
        self.r_filt = ExpFilter(np.tile(0.01, self.config['N_PIXELS'] // 2),
                       alpha_decay=0.2, alpha_rise=0.99)
        self.g_filt = ExpFilter(np.tile(0.01, self.config['N_PIXELS'] // 2),
                       alpha_decay=0.05, alpha_rise=0.3)
        self.b_filt = ExpFilter(np.tile(0.01, self.config['N_PIXELS'] // 2),
                       alpha_decay=0.1, alpha_rise=0.5)
        self.p_filt = ExpFilter(np.tile(1, (3, self.config['N_PIXELS'] // 2)),
                       alpha_decay=0.1, alpha_rise=0.99)
        self._prev_spectrum = np.tile(0.01, self.config['N_PIXELS'] // 2)

        self._prev_pixels = np.tile(253, (3, self.config['N_PIXELS']))
        self.pixels = np.tile(1, (3, self.config['N_PIXELS']))

    def visualize_scroll(self, y):
        """Effect that originates in the center and scrolls outwards"""
        y = y**2.0
        self.gain.update(y)
        y /= self.gain.value
        y *= 255.0
        r = int(np.max(y[:len(y) // 3]))
        g = int(np.max(y[len(y) // 3: 2 * len(y) // 3]))
        b = int(np.max(y[2 * len(y) // 3:]))
        # Scrolling effect window
        self.p[:, 1:] = self.p[:, :-1]
        self.p *= 0.98
        self.p = gaussian_filter1d(self.p, sigma=0.2)
        # Create new color originating at the center
        self.p[0, 0] = r
        self.p[1, 0] = g
        self.p[2, 0] = b
        # Update the LED strip
        return np.concatenate((self.p[:, ::-1], self.p), axis=1)

    def visualize_energy(self, y):
        """Effect that expands from the center with increasing sound energy"""
        y = np.copy(y)
        self.gain.update(y)
        y /= self.gain.value
        # Scale by the width of the LED strip
        y *= float((self.config['N_PIXELS'] // 2) - 1)
        # Map color channels according to energy in the different freq bands
        scale = 0.9
        r = int(np.mean(y[:len(y) // 3]**scale))
        g = int(np.mean(y[len(y) // 3: 2 * len(y) // 3]**scale))
        b = int(np.mean(y[2 * len(y) // 3:]**scale))
        # Assign color to different frequency regions
        self.p[0, :r] = 255.0
        self.p[0, r:] = 0.0
        self.p[1, :g] = 255.0
        self.p[1, g:] = 0.0
        self.p[2, :b] = 255.0
        self.p[2, b:] = 0.0
        self.p_filt.update(self.p)
        self.p = np.round(self.p_filt.value)
        # Apply substantial blur to smooth the edges
        self.p[0, :] = gaussian_filter1d(self.p[0, :], sigma=4.0)
        self.p[1, :] = gaussian_filter1d(self.p[1, :], sigma=4.0)
        self.p[2, :] = gaussian_filter1d(self.p[2, :], sigma=4.0)
        # Set the new pixel value
        return np.concatenate((self.p[:, ::-1], self.p), axis=1)

    def visualize_spectrum(self, y):
        """Effect that maps the Mel filterbank frequencies onto the LED strip"""
        y = np.copy(interpolate(y, self.config['N_PIXELS'] // 2))
        self.common_mode.update(y)
        diff = y - self._prev_spectrum
        self._prev_spectrum = np.copy(y)
        # Color channel mappings
        r = self.r_filt.update(y - self.common_mode.value)
        g = np.abs(diff)
        b = self.b_filt.update(np.copy(y))
        # Mirror the color channels for symmetric output
        r = np.concatenate((r[::-1], r))
        g = np.concatenate((g[::-1], g))
        b = np.concatenate((b[::-1], b))
        output = np.array([r, g,b]) * 255
        return output

    def run(self):
        while not self.stop_event.is_set():
            try:
                fn, args, kwargs = self.queue.get(timeout=0.25)
                if fn != 'audio':
                    continue
            except queue.Empty:
                continue

            # TODO: configure
            self.pixels = self.visualize_scroll(args[0])
            self.send_data()

    def send_data(self, data):
        raise NotImplementedError()


class RemoteStripThread(BaseLEDThread):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def send_data(self):
        """Sends UDP packets to ESP8266 to update LED strip values

        The ESP8266 will receive and decode the packets to determine what values
        to display on the LED strip. The communication protocol supports LED strips
        with a maximum of 256 LEDs.

        The packet encoding scheme is:
            |i|r|g|b|
        where
            i (0 to 255): Index of LED to change (zero-based)
            r (0 to 255): Red value of LED
            g (0 to 255): Green value of LED
            b (0 to 255): Blue value of LED
        """
        # Truncate values and cast to integer
        self.pixels = np.clip(self.pixels, 0, 255).astype(int)
        # Optionally apply gamma correc tio
        # TODO: implement
        # p = _gamma[self.pixels] if config.SOFTWARE_GAMMA_CORRECTION else np.copy(self.pixels)
        p = np.copy(self.pixels)
        # TODO: figure out automatically
        MAX_PIXELS_PER_PACKET = 126
        # Pixel indices
        idx = range(self.pixels.shape[1])
        idx = [i for i in idx if not np.array_equal(p[:, i], self._prev_pixels[:, i])]
        n_packets = len(idx) // MAX_PIXELS_PER_PACKET + 1
        idx = np.array_split(idx, n_packets)
        for packet_indices in idx:
            m = []
            for i in packet_indices:
                m.append(i)  # Index of pixel to change
                m.append(p[0][i])  # Pixel red value
                m.append(p[1][i])  # Pixel green value
                m.append(p[2][i])  # Pixel blue value
            m = bytes(m)
            # TODO: from output config
            self._sock.sendto(m, ('10.0.1.10', 7777))
        self._prev_pixels = np.copy(p)
