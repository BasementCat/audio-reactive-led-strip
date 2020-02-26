import random
import time

from app.effects import Effect
from app.lib.misc import map_to_range

from . import BasicDMX



class MovingHeadMixin:
    """\
    Basic moving head light.
    """

    def _get_dead_coasting_color_effect(self):
        return {}

    def _apply_dead_coasting(self, data):
        # speed = 20
        speed = 5
        # dim = 75
        dim = 20
        if (data.get('dead_for') or 0) >= 2:
            # If we're dead for 2s, go into dead coasting
            if self.state['speed'] != speed or self.state['dim'] != dim:
                self.state['speed'] = speed
                self.add_effect('dim', Effect(self.state['dim'], dim, 1, dim))
                self.send_dmx(data, True)
            self.add_effect('pan', Effect(random.randint(0, 255), None, 8))
            self.add_effect('tilt', Effect(random.randint(0, 255), None, 8))
            for k, e in self._get_dead_coasting_effects().items():
                self.add_effect(k, e)

            return True

    def _apply_idle_coasting(self, data):
        speed = 31
        idle_pan_tilt = time.time() - max(self.last_function['pan'], self.last_function['tilt']) >= 2
        if data.get('audio_v_sum') and idle_pan_tilt:
            # Below threshold, but there's still audio
            # Only called if mapping is set
            if self.state['speed'] != speed:
                self.state['speed'] = speed
                self.send_dmx(data, True)
            self.add_effect('pan', Effect(self.state['pan'], random.randint(0, 255), 5))
            self.add_effect('tilt', Effect(self.state['tilt'], random.randint(0, 255), 5))

            # Don't return true, so that mapping is still run
            # This allows pan/tilt to be updated
            # return True

    def _apply_idle_fadeout(self, data):
        return
        if (data.get('idle_for') or 0) > 0.25:
            self.add_effect('dim', Effect(self.state['dim'], 0, 0.25))
            return True


class TomshineMovingHead6in1(MovingHeadMixin, BasicDMX):
    FUNCTIONS = {
        'pan': 1,
        'pan_fine': 2,
        'tilt': 3,
        'tilt_fine': 4,
        'speed': 5,
        'dim': 6,
        'strobe': 7,
        'red': 8,
        'green': 9,
        'blue': 10,
        'white': 11,
        'amber': 12,
        'uv': 13,
        'mode': 14,
        'motor_sens': 15,
        'effect': 16,
        'led_sens': 17,
        'reset': 18,
    }

    RATES = {
        'pan': 0.75,
        'tilt': 0.75,
        'color': 0.125,
        'strobe': 10,
        'dim': 0.125,
    }

    INITIALIZE = {
        'dim': 255,
        # 'dim': 80,
        'speed': 255,
        # 'uv': 255,
    }

    INVERT = ['speed']
    CLEAR_EFFECTS_ON_NEW_STATE = ['pan', 'tilt', 'speed', 'dim', 'uv', 'white', 'amber']
    RESET_ON_NEW_STATE = ['speed', 'dim']
    MULTI_PROP_MAP = {'color': ['red', 'green', 'blue']}

    def _get_dead_coasting_effects(self):
        return {
            'color': Effect(
                (self.state['red'], self.state['green'], self.state['blue'],),
                self.map_color(None, 1, 0),
                2
            )
        }

    def get_state_chain(self):
        return [self._apply_dead_coasting, self._apply_idle_coasting, self._apply_idle_fadeout]

    def _map_pan_tilt(self, function, value, threshold):
        if value < threshold:
            return
        cur_value = self.state[function]
        distance = int(map_to_range(value, threshold) * (max(cur_value, 255 - cur_value)))
        choices = [
            min(cur_value + distance, 255),
            max(cur_value - distance, 0),
        ]
        return random.choice(choices)

    def map_pan(self, trigger, value, threshold):
        return self._map_pan_tilt('pan', value, threshold)

    def map_tilt(self, trigger, value, threshold):
        return self._map_pan_tilt('tilt', value, threshold)

    def map_color(self, trigger, value, threshold):
        if trigger == 'frequency_all':
            bins_per = int(len(value) / 3)
            out = []
            for color, offset in (('red', 0), ('green', bins_per), ('blue', bins_per * 2)):
                newvalue = max(value[offset:offset + bins_per])
                if newvalue > threshold:
                    out.append(int(newvalue * 255))
                else:
                    out.append(0)
            if sum(out):
                # Try to create an effect to fade to the next color, always return something if there's data
                curr = (self.state['red'], self.state['green'], self.state['blue'])
                self.add_effect('color', Effect(curr, out, 0.25))
                # return curr
            return None

        if value < threshold:
            return

        if trigger == 'pitch':
            return int((value / 128) * 255), 0, 0

        old_rgb = [self.state[k] for k in ('red', 'green', 'blue')]
        diff = 0
        while diff < 0.25:
            rgb = [random.randint(0, 256) for _ in range(3)]
            diff = sum((abs(rgb[i] - old_rgb[i]) / 256 for i in range(3))) / 3
        return rgb

    # def map_color(self, trigger, value, threshold):
    #     if value >= threshold:
    #         half_color = random.random() > 0.75
    #         if half_color:
    #             return random.randint(57, 127)
    #         return random.randint(0, 56)

    # def map_gobo(self, trigger, value, threshold):
    #     if value >= threshold:
    #         dither = random.random() > 0.75
    #         if dither:
    #             return random.randint(64, 127)
    #         return random.randint(0, 63)

    def map_strobe(self, trigger, value, threshold):
        return None
        # should set a high threshold for this
        if value > threshold and self.last_function['strobe'] + self.RATES.get('strobe', 0) < time.time():
            # TODO: might need a different value for some lights
            self.add_effect('strobe', Effect(255, 255, 1, 0))
            # Because this is not applied normally...
            self.last_function['strobe'] = time.time()

    # 'dim': 6,
    # 'red': 8,
    # 'green': 9,
    # 'blue': 10,
    # 'white': 11,
    # 'amber': 12,
    # 'uv': 13,
