import random
import time

from app.effects import Effect, StateEffect
from app.lib.misc import map_to_range

from . import BasicDMX


class DeadCoastingStateEffect(StateEffect):
    FUNCTIONS = ['speed', 'dim']

    def __init__(self, speed=5, dim=20, delay=2, dim_duration=1, move_duration=8, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.speed = speed
        self.dim = dim
        self.delay = delay
        self.dim_duration = dim_duration
        self.move_duration = move_duration

    def applicable(self, light, data):
        return (data.get('dead_for') or 0) > self.delay

    def apply(self, light, data):
        light.auto_state['speed'] = self.speed
        light.add_effect('dim', Effect(light.auto_state['dim'], self.dim, self.dim_duration), overwrite=True)

    def run(self, light, data):
        light.add_effect('pan', Effect(random.randint(0, 255), None, 8))
        light.add_effect('tilt', Effect(random.randint(0, 255), None, 8))
        if hasattr(light, '_get_dead_coasting_effects'):
            for k, e in light._get_dead_coasting_effects().items():
                light.add_effect(k, e)


class IdleCoastingStateEffect(StateEffect):
    FUNCTIONS = ['speed']

    def __init__(self, speed=31, delay=2, move_duration=5, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.speed = speed
        self.delay = delay
        self.move_duration = move_duration

    def applicable(self, light, data):
        idle_pan_tilt = time.time() - max(light.last_function['pan'], light.last_function['tilt']) >= self.delay
        return data.get('audio_v_sum') and idle_pan_tilt

    def apply(self, light, data):
        light.auto_state['speed'] = self.speed

    def run(self, light, data):
        light.add_effect('pan', Effect(random.randint(0, 255), None, self.move_duration))
        light.add_effect('tilt', Effect(random.randint(0, 255), None, self.move_duration))


class IdleFadeoutStateEffect(StateEffect):
    FUNCTIONS = ['dim']

    def __init__(self, delay=0.25, dim_duration=0.5, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.delay = delay
        self.dim_duration = dim_duration
        # self.applied = None

    def applicable(self, light, data):
        # if self.applied and time.time() - self.applied > self.dim_duration:
        #     return False
        return (data.get('idle_for') or 0) > self.delay

    def apply(self, light, data):
        light.add_effect('dim', Effect(light.auto_state['dim'], 0, self.dim_duration), overwrite=True)
    #     self.applied = time.time()

    # def unapply(self, light, data):
    #     super().unapply(light, data)
    #     self.applied = None


class MovingHeadMixin:
    """\
    Basic moving head light.
    """

    # Probably should adjust these per light
    SPEEDS = {
        'pan': (25, 1),
        'tilt': (10, 0.5),
    }

    def _get_dead_coasting_effects(self):
        return {}

    def get_state_effects(self):
        return [DeadCoastingStateEffect(), IdleCoastingStateEffect(), IdleFadeoutStateEffect()]


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
                (self.auto_state['red'], self.auto_state['green'], self.auto_state['blue'],),
                self.map_color(None, 1, 0),
                2
            )
        }

    def _map_pan_tilt(self, function, value, threshold):
        if value < threshold:
            return
        cur_value = self.auto_state[function]
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
            if not isinstance(value[0], list):
                # Raw bins
                bins_per = int(len(value) / 3)
                temp_value = []
                for offset in (0, bins_per, bins_per * 2):
                    bucket = []
                    for idx in range(offset, offset + bins_per):
                        bucket.append(value[idx])
                value = temp_value

            out = []
            colors = ('red', 'green', 'blue')
            for color, bins in zip(colors, value[:3]):
                newvalue = max(bins)
                if newvalue > threshold:
                    out.append(int(newvalue * 255))
                else:
                    out.append(0)
            if sum(out):
                # Try to create an effect to fade to the next color, always return something if there's data
                curr = (self.auto_state['red'], self.auto_state['green'], self.auto_state['blue'])
                self.add_effect('color', Effect(curr, out, 0.25))
                # return curr
            return None

        if value < threshold:
            return

        if trigger == 'pitch':
            return int((value / 128) * 255), 0, 0

        old_rgb = [self.auto_state[k] for k in ('red', 'green', 'blue')]
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
