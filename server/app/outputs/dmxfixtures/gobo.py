import random

from app.effects import Effect
from app.lib.misc import map_to_range

from . import BasicDMX
from .movinghead import MovingHeadMixin


class GoboMixin:
    INVERT = ['speed', 'strobe']
    CLEAR_EFFECTS_ON_NEW_STATE = ['pan', 'tilt', 'speed', 'dim']
    RESET_ON_NEW_STATE = ['speed', 'dim']

    def _get_dead_coasting_effects(self):
        color = self.map_color(None, 1, 0)
        gobo = self.map_gobo(None, 1, 0)
        return {
            'color': Effect(color, color, 8),
            'gobo': Effect(gobo, gobo, 8),
        }

    def _map_pan_tilt(self, function, trigger, value, threshold):
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
        return self._map_pan_tilt('pan', trigger, value, threshold)

    def map_tilt(self, trigger, value, threshold):
        return self._map_pan_tilt('tilt', trigger, value, threshold)

    def map_color(self, trigger, value, threshold):
        if value >= threshold:
            half_color = random.random() > 0.75
            if half_color:
                return random.randint(57, 127)
            return random.randint(0, 56)

    def map_gobo(self, trigger, value, threshold):
        if value >= threshold:
            dither = random.random() > 0.75
            if dither:
                return random.randint(64, 127)
            return random.randint(0, 63)

    def map_strobe(self, trigger, value, threshold):
        # should set a high threshold for this
        if value > threshold:
            # TODO: might need a different value for some lights
            if 'strobe' not in self.effects:
                self.effects['strobe'] = Effect(255, 255, 1, 0)


class UKingGobo(GoboMixin, MovingHeadMixin, BasicDMX):
    FUNCTIONS = {
        'pan': 1,
        'pan_fine': 2,
        'tilt': 3,
        'tilt_fine': 4,
        'color': 5,
        'gobo': 6,
        'strobe': 7,
        'dim': 8,
        'speed': 9,
        'mode': 10,
        'dim_mode': 11,
    }

    INITIALIZE = {
        'pan': 0,
        'pan_fine': 0,
        'tilt': 0,
        'tilt_fine': 0,
        'color': 0,
        'gobo': 0,
        'strobe': 0,
        'dim': 255,
        'speed': 255,
        'mode': 0,
        'dim_mode': 0
    }

    RATES = {
        'pan': 0.75,
        'tilt': 0.75,
        'gobo': 0.25,
        'color': 0.25,
        'strobe': 10,
        'dim': 0.125,
    }

    ENUMS = {
        'color': {
            'white': (0, 9),
            'red': (10, 19),
            'green': (20, 29),
            'blue': (30, 39),
            'yellow': (40, 49),
            'orange': (50, 59),
            'cyan': (60, 69),
            'pink': (70, 79),
            'pink_cyan': (80, 89),
            'cyan_orange': (90, 99),
            'orange_yellow': (100, 109),
            'yellow_blue': (110, 119),
            'blue_green': (120, 127),
        },
        'gobo': {
            'none': (0, 7),
            'broken_circle': (8, 15),
            'burst': (16, 23),
            '3_spot_circle': (24, 31),
            'square_spots': (32, 39),
            'droplets': (40, 47),
            'swirl': (48, 55),
            'stripes': (56, 63),
            'dither_none': (64, 71),
            'dither_broken_circle': (72, 79),
            'dither_burst': (80, 87),
            'dither_3_spot_circle': (88, 95),
            'dither_square_spots': (96, 103),
            'dither_droplets': (104, 111),
            'dither_swirl': (112, 119),
            'dither_stripes': (120, 127),
        }
    }


class UnnamedGobo(GoboMixin, MovingHeadMixin, BasicDMX):
    FUNCTIONS = {
        'pan': 1,
        'pan_fine': 2,
        'tilt': 3,
        'tilt_fine': 4,
        'color': 5,
        'gobo': 6,
        'strobe': 7,
        'dim': 8,
        'speed': 9,
        'mode': 10,
        'dim_mode': 11,  # Actually reset, but changing the name fucks with linking
    }

    INITIALIZE = {
        'pan': 0,
        'pan_fine': 0,
        'tilt': 0,
        'tilt_fine': 0,
        'color': 0,
        'gobo': 0,
        'strobe': 0,
        'dim': 255,
        'speed': 255,
        'mode': 0,
        'dim_mode': 0,
    }

    RATES = {
        'pan': 0.75,
        'tilt': 0.75,
        'gobo': 0.25,
        'color': 0.25,
        'strobe': 10,
        'dim': 0.125,
    }

    ENUMS = {
        'color': {
            'white': (0, 9),
            'yellow': (10, 19),
            'orange': (20, 29),
            'cyan': (30, 39),
            'blue': (40, 49),
            'green': (50, 59),
            'pink': (60, 69),
            'red': (70, 79),
            'pink_red': (80, 89),
            'green_pink': (90, 99),
            'blue_green': (100, 109),
            'cyan_blue': (110, 119),
            'orange_cyan': (120, 129),
            'yellow_orange': (130, 139),
        },
        'gobo': {
            'none': (0, 7),
            'broken_circle': (8, 15),
            'burst': (16, 23),
            '3_spot_circle': (24, 31),
            'square_spots': (32, 39),
            'droplets': (40, 47),
            'swirl': (48, 55),
            'stripes': (56, 63),
            'dither_none': (64, 71),
            'dither_broken_circle': (72, 79),
            'dither_burst': (80, 87),
            'dither_3_spot_circle': (88, 95),
            'dither_square_spots': (96, 103),
            'dither_droplets': (104, 111),
            'dither_swirl': (112, 119),
            'dither_stripes': (120, 127),
        }
    }
