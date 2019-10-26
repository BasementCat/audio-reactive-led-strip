import socket
import logging
import time
import random

import numpy as np
from scipy.ndimage.filters import gaussian_filter1d

from . import Output
from app.effects import Effect
from app.lib.dsp import ExpFilter
from app.lib.pubsub import subscribe, publish
from app.lib.misc import FPSCounter


logger = logging.getLogger()


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


# Effects

class IdleFlameEffect(object):
    COLORS = {
        'orange': (226, 121, 35),
        'purple': (158, 8, 148),
        'green': (74, 150, 12),
    }

    # make it look like an effect
    done = False
    done_value = None

    def __init__(self, n_leds, color='random'):
        if color != 'random' and color not in self.COLORS:
            color = 'random'
        if color == 'random':
            color = random.choice(list(self.COLORS.keys()))

        self.n_leds = n_leds
        self.color = color
        self.next_switch = 0

    @property
    def value(self):
        if self.next_switch <= time.time():
            self.pixels = np.array([[self.COLORS[self.color][i] for _ in range(self.n_leds)] for i in range(3)])
            for i in range(self.n_leds):
                flicker = random.randint(0, 75)
                self.pixels[0][i] = max(0, self.pixels[0][i] - flicker)
                self.pixels[1][i] = max(0, self.pixels[1][i] - flicker)
                self.pixels[2][i] = max(0, self.pixels[2][i] - flicker)
            self.next_switch = time.time() + (random.randint(10, 40) / 1000.0)

        return self.pixels


class IdleAdvancedFlameEffect(object):
    class FlameElement(object):
        def __init__(self, brightness=0, step=0, max_brightness=0, color=(0, 0, 0), state='RESET'):
            self.brightness = brightness
            self.step = step
            self.max_brightness = max_brightness
            self.color = color
            self.state = state

        def __repr__(self):
            return f'FlameElement<{self.color}@{self.brightness}/{self.max_brightness}, +{self.step}, {self.state}>'

        def __str__(self):
            return repr(self)

        def update(self, flicker_chance):
            if self.state == 'RESET':
                self._set_random_step()
                self._set_random_max_brightness()
                self.brightness = 0
                self.state = 'INCREASING'
                self.color = random.choice(IdleAdvancedFlameEffect.FLAMECOLORS)
            elif self.state == 'INCREASING':
                new_brightness = self.brightness + self.step
                if new_brightness > self.max_brightness:
                    self._update_flame_color(new_brightness)
                    self.brightness = self.max_brightness
                    self._set_random_step()
                    self.state = 'DECREASING'
                else:
                    self._update_flame_color(new_brightness)
                    self.brightness = new_brightness
            elif self.state == 'DECREASING':
                new_brightness = max(0, self.brightness - self.step)
                # Chance to flicker/rekindle
                if random.randint(0, 100) < flicker_chance:
                    # Rekindle
                    self.state = 'INCREASING'
                    cur_brightness = self.brightness
                    self._set_random_max_brightness()
                    self.brightness = max(cur_brightness, self.brightness)
                    self._set_random_step()
                else:
                    if new_brightness < 1:
                        self.state = 'RESET'
                        self.brightness = 0
                        self._update_flame_color(0)
                    else:
                        self._update_flame_color(new_brightness)
                        self.brightness = new_brightness

        def get_colors(self, width):
            r = list(range(1, width + 1))
            if len(r) % 2 == 0:
                # Even number
                r0 = []
                r1 = r[:int(len(r) / 2)]
                r2 = r[int(len(r) / 2) + 1:]
            else:
                r0 = [r[int(len(r) / 2)]]
                r1 = r[:int(len(r) / 2)]
                r2 = r[int(len(r) / 2) + 1:]
            r = r0
            r1 = list(reversed(r1))
            for i in range(len(r1)):
                r.append(r1[i])
                r.append(r2[i])
            for i in r:
                yield tuple(map(lambda v: min(255, (v / i) * 1.2), self.color))

        def _set_random_step(self):
            self.step = random.randint(1, 71)

        def _set_random_max_brightness(self):
            # # bell curve
            # self.max_brightness = random.randint(0, 256 / 4) +  random.randint(0, 256 / 4) + random.randint(0, 256 / 4) + 256 / 4 + 1

            # # flat distribution
            # self.max_brightness = random.randint(0, 256 * 3 / 4) +  256 / 4

            # brighter flat distribution
            self.max_brightness = random.randint(0, 256 / 2) +  256 / 2

        def _update_flame_color(self, new_brightness):
            new_brightness = min(new_brightness, self.max_brightness)
            # new_color = []
            # for rgb_channel in range(3):
            #     chan_val = self.color[rgb_channel]
            #     chan_val *= new_brightness
            #     chan_val /= 256
            #     new_color.append(max(0, int(chan_val)))
            new_inc = random.randint(6, max(6, int(new_brightness / 4)))
            if self.state == 'DECREASING':
                new_inc = -new_inc
            new_color = tuple(map(lambda v: min(255, int(v + new_inc)), self.color))
            self.color = tuple(new_color)

    SCALERVAL = 256
    REZ_RANGE = SCALERVAL
    FLAMECOLORS = (
        (SCALERVAL, 0,  0),
        (SCALERVAL, 0,  0),
        (SCALERVAL, 0,  0),
        (SCALERVAL, 0,  0),
        (SCALERVAL, 0,  0),
        (SCALERVAL, 0,  0),
        (SCALERVAL, 0,  0),
        (SCALERVAL, 0,  0),
        (SCALERVAL, SCALERVAL*.4,  0),
        (SCALERVAL, SCALERVAL*.4,  0),
        (SCALERVAL, SCALERVAL*.4,  0),
        (SCALERVAL, SCALERVAL*.4,  0),
        (SCALERVAL, SCALERVAL*.3,  0),
        (SCALERVAL, SCALERVAL*.3,  0),
        (SCALERVAL, SCALERVAL*.3,  0),
        (SCALERVAL, SCALERVAL*.3,  0),
        (SCALERVAL, SCALERVAL*.3,  0),
        (SCALERVAL, SCALERVAL*.3,  0),
        (SCALERVAL, SCALERVAL*.3,  0),
        (SCALERVAL, SCALERVAL*.3,  SCALERVAL), # white
        (0, SCALERVAL*.2,  SCALERVAL), # that one blue flame
        (SCALERVAL,  SCALERVAL*.3,  SCALERVAL*.5),
    )

    # make it look like an effect
    done = False
    done_value = None

    def __init__(self, n_leds, *, flame_width=3, flicker_chance=3, **kwargs):
        self.n_leds = n_leds
        self.flame_width = flame_width
        self.flicker_chance = flicker_chance
        self.n_flames = int(self.n_leds / self.flame_width)
        self.flames = [self.FlameElement() for _ in range(self.n_flames)]
        self.pixels = None
        self.last_value = 0

    @property
    def value(self):
        if time.time() - self.last_value >= 0.022:
            self.last_value = time.time()
            temp_pixels = [[] for _ in range(3)]
            for i in range(self.n_flames):
                self.flames[i].update(self.flicker_chance)
                for c in self.flames[i].get_colors(self.flame_width):
                    for x in range(3):
                        temp_pixels[x].append(c[x])
            self.pixels = np.array(temp_pixels)

            # print(self.pixels)

        return self.pixels


class BaseLEDStrip(Output):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.p = np.tile(1.0, (3, self.output_config['N_PIXELS'] // 2))
        self.gain = ExpFilter(np.tile(0.01, self.config['N_FFT_BINS']),
                     alpha_decay=0.001, alpha_rise=0.99)
        self.common_mode = ExpFilter(np.tile(0.01, self.output_config['N_PIXELS'] // 2),
                     alpha_decay=0.99, alpha_rise=0.01)
        self.r_filt = ExpFilter(np.tile(0.01, self.output_config['N_PIXELS'] // 2),
                       alpha_decay=0.2, alpha_rise=0.99)
        self.g_filt = ExpFilter(np.tile(0.01, self.output_config['N_PIXELS'] // 2),
                       alpha_decay=0.05, alpha_rise=0.3)
        self.b_filt = ExpFilter(np.tile(0.01, self.output_config['N_PIXELS'] // 2),
                       alpha_decay=0.1, alpha_rise=0.5)
        self.p_filt = ExpFilter(np.tile(1, (3, self.output_config['N_PIXELS'] // 2)),
                       alpha_decay=0.1, alpha_rise=0.99)
        self._prev_spectrum = np.tile(0.01, self.output_config['N_PIXELS'] // 2)

        self._prev_pixels = np.tile(253, (3, self.output_config['N_PIXELS']))
        self.pixels = np.tile(1, (3, self.output_config['N_PIXELS']))
        self.brightness = 1.0

        self.effects = {}

        self.fps = FPSCounter(f"{self.__class__.__name__} {self.name}")

        subscribe('audio', self.handle_audio)
        if self.output_config.get('IDLE'):
            subscribe('idle_instant', self.handle_idle_instant)
            if self.output_config['IDLE'].get('FADEOUT') and self.output_config['IDLE'].get('NAME'):
                # If we're fading out on idle, don't apply the idle effect until afterwards
                subscribe('idle_for', self.handle_idle_for, condition=lambda e, t, *a, **ka: t and t > self.output_config['IDLE']['FADEOUT'])

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
        y *= float((self.output_config['N_PIXELS'] // 2) - 1)
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
        y = np.copy(interpolate(y, self.output_config['N_PIXELS'] // 2))
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

    def handle_idle_instant(self, is_idle, *args, **kwargs):
        # Assume idle config is set
        if is_idle:
            if self.output_config['IDLE'].get('FADEOUT'):
                # Fade out on idle
                # Called only when the state changes so we can make some assumptions
                # Idle anim will be set by idle_for
                self.effects['brightness'] = Effect(self.brightness * 100, 0, self.output_config['IDLE']['FADEOUT'], 0)
            else:
                # No fadeout, so apply the animation as appropriate
                self._apply_idle_anim()
        else:
            self._clear_idle_anim()

    def handle_idle_for(self, idle_for, *args, condition=None, **kwargs):
        # Only called if idle config is set, and fadeout is set, and if the condition changes
        if condition:
            self._apply_idle_anim()
        # Don't clear here, it'll be cleared as soon as the instant idle state changes

    def _apply_idle_anim(self):
        if self.output_config['IDLE'].get('NAME'):
            effect = globals().get('Idle' + self.output_config['IDLE']['NAME'] + 'Effect', None)
            if effect:
                # Add the brightness/idle
                if self.output_config['IDLE'].get('FADEIN'):
                    self.effects['brightness'] = Effect(0, 100, self.output_config['IDLE']['FADEIN'], 1)
                self.effects['idle'] = effect(self.output_config['N_PIXELS'], **self.output_config['IDLE'].get('ARGS', {}))

    def _clear_idle_anim(self):
        for k in ('brightness', 'idle'):
            try:
                del self.effects[k]
            except KeyError:
                pass
            self.brightness = 1

    def run(self):
        done = []
        for k, v in self.effects.items():
            value = None
            if v.done:
                value = v.done_value
                done.append(k)
            else:
                value = v.value

            if k == 'brightness':
                self.brightness = v.value / 100.0

            if k == 'idle':
                self.pixels = v.value

        for k in done:
            del self.effects[k]

        self.send_data(self.pixels)

    def handle_audio(self, data):
        with self.fps:
            fn = getattr(self, 'visualize_' + self.output_config.get('EFFECT', 'scroll'), None)
            if not fn:
                logger.error("Bad effect: %s", self.output_config.get('EFFECT'))
                return
            self.pixels = self.visualize_scroll(data)

    def send_data(self, data):
        raise NotImplementedError()


class RemoteStrip(BaseLEDStrip):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def send_data(self, data):
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
        p = (np.clip(data, 0, 255) * self.brightness).astype(int)
        # Optionally apply gamma correc tio
        # TODO: implement
        # p = _gamma[self.pixels] if config.SOFTWARE_GAMMA_CORRECTION else np.copy(self.pixels)
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
            self._sock.sendto(m, (self.output_config['HOST'], self.output_config['PORT']))

        publish('led_data', {'name': self.name, 'pixels': p})
        self._prev_pixels = np.copy(self.pixels)
