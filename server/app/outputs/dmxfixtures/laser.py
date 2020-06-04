import random

from app.effects import Effect, StateEffect

from . import BasicDMX


class IdleOffStateEffect(StateEffect):
    FUNCTIONS = ['mode']

    def __init__(self, delay=0.5, param='mode', value=0, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.delay = delay
        self.param = param
        self.value = value

    def applicable(self, light, data):
        return (data.get('idle_for') or 0) > self.delay

    def apply(self, light, data):
        light.auto_state[self.param] = self.value


class DeadPatternStateEffect(StateEffect):
    FUNCTIONS = ['speed', 'dim']

    def __init__(self, delay=2, mode_param='mode', mode_value=100, pattern_duration=5, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.delay = delay
        self.mode_param = mode_param
        self.mode_value = mode_value
        self.pattern_duration = pattern_duration
        self.prev_mode = None

    def applicable(self, light, data):
        return (data.get('dead_for') or 0) > self.delay

    def apply(self, light, data):
        if self.mode_param:
            self.prev_mode = light.auto_state[self.mode_param]
            light.auto_state[self.mode_param] = self.mode_value

    def unapply(self, light, data):
        if self.prev_mode is not None:
            light.auto_state[self.mode_param] = self.prev_mode
            self.prev_mode = None

    def run(self, light, data):
        light.add_effect('pattern', Effect(random.randint(0, 255), None, self.pattern_duration))


class PatternLaserMixin:
    INVERT = ['scan_speed', 'pattern_speed']
    CLEAR_EFFECTS_ON_NEW_STATE = ['scan_speed', 'pattern_speed']


class Generic4ColorLaser(PatternLaserMixin, BasicDMX):
    FUNCTIONS = {
        'mode': 1,
        'pattern': 2,
        'x': 3,
        'y': 4,
        'scan_speed': 5,
        'pattern_speed': 6,
        'pattern_size': 7,
    }

    INITIALIZE = {
        'mode': 50,
        'pattern': 0,
        'x': 128,
        'y': 128,
        'scan_speed': 255,
        'pattern_speed': 255,
        'pattern_size': 128,
    }

    RATES = {
        'mode': 0,
        # 'pattern': 0.125,
        'pattern': 4,
        'pattern_size': 5,
        'x': 1,
        'y': 1,
    }

    ENUMS = {
        'mode': {
            'off': (0, 49),
            'static': (50, 99),
            'dynamic': (100, 149),
            'sound': (150, 199),
            'auto': (200, 255),
        },
        'pattern_static': {
            'circle': (0, 4),
            'dot_circle_1': (5, 9),
            'dot_circle_2': (10, 14),
            'scan_circle': (15, 19),
            'horiz_line': (20, 24),
            'horiz_dot_line': (25, 29),
            'vert_line': (30, 34),
            'vert_dot_line': (35, 39),
            '45deg_diag': (40, 44),
            '45deg_dot_diag': (45, 49),
            '135deg_diag': (50, 54),
            '135deg_dot_diag': (55, 59),
            'v_line_1': (60, 64),
            'v_dot_line_1': (65, 69),
            'v_line_2': (70, 74),
            'v_dot_line_2': (75, 79),
            'triangle_1': (80, 84),
            'dot_triangle_1': (85, 89),
            'triangle_2': (90, 94),
            'dot_triangle_2': (95, 99),
            'square': (100, 104),
            'dot_square': (105, 109),
            'rectangle_1': (110, 114),
            'dot_rectangle_1': (115, 119),
            'rectangle_2': (120, 124),
            'dot_rectangle_2': (125, 129),
            'criscross': (130, 134),
            'chiasma_line': (135, 139),
            'horiz_extend_line': (140, 144),
            'horiz_shrink_line': (145, 149),
            'horiz_flex_line': (150, 154),
            'horiz_flex_dot_line': (155, 159),
            'vert_extend_line': (160, 164),
            'vert_shrink_line': (165, 169),
            'vert_flex_line': (170, 174),
            'vert_flex_dot_line': (175, 179),
            'ladder_line_1': (180, 184),
            'ladder_line_2': (185, 189),
            'ladder_line_3': (190, 194),
            'ladder_line_4': (195, 199),
            'tetragon_1': (200, 204),
            'tetragon_2': (205, 209),
            'pentagon_1': (210, 214),
            'pentagon_2': (215, 219),
            'pentagon_3': (220, 224),
            'pentagon_4': (225, 229),
            'wave_line': (230, 234),
            'wave_dot_line': (235, 239),
            'spiral_line': (240, 244),
            'many_dot_1': (245, 249),
            'many_dot_2': (250, 254),
            'square_dot': (255, 255),
        },
        'pattern_dynamic': {
            'circle_to_big': (0, 4),
            'dot_circle_to_big': (5, 9),
            'scan_circle_to_big': (10, 14),
            'circle_flash': (15, 19),
            'dot_circle_flash': (20, 24),
            'circle_roll': (25, 29),
            'dot_circle_roll': (30, 34),
            'circle_turn': (35, 39),
            'dot_circle_turn': (40, 44),
            'dot_circle_to_add': (45, 49),
            'scan_circle_extend': (50, 54),
            'circle_jump': (55, 59),
            'dot_circle_jump': (60, 64),
            'horiz_line_jump': (65, 69),
            'horiz_dot_line_jump': (70, 74),
            'vert_line_jump': (75, 79),
            'vert_dot_line_jump': (80, 84),
            'diag_jump': (85, 89),
            'dot_diag_jump': (90, 94),
            'short_sector_round_1': (95, 99),
            'short_sector_round_2': (100, 104),
            'long_sector_round_1': (105, 109),
            'long_sector_round_2': (110, 114),
            'line_scan': (115, 119),
            'dot_line_scan': (120, 124),
            '45deg_diag_move': (125, 129),
            'dot_diag_move': (130, 134),
            'horiz_line_flex': (135, 139),
            'horiz_dot_line_flex': (140, 144),
            'horiz_line_move': (145, 149),
            'horiz_dot_line_move': (150, 154),
            'vert_line_move': (155, 159),
            'vert_dot_line_move': (160, 164),
            'rect_extend': (165, 169),
            'dot_rect_extend': (170, 174),
            'square_extend': (175, 179),
            'dot_square_extend': (180, 184),
            'rect_turn': (185, 189),
            'dot_rect_turn': (190, 194),
            'square_turn': (195, 199),
            'dot_square_turn': (200, 204),
            'pentagon_turn': (205, 209),
            'dot_pentagon_turn': (210, 214),
            'tetragon_turn': (215, 219),
            'pentagon_star_turn': (220, 224),
            'bird_fly': (225, 229),
            'dot_bird_fly': (230, 234),
            'wave_flowing': (235, 239),
            'dot_wave_flowing': (240, 244),
            'many_dot_jump_1': (245, 249),
            'square_dot_jump': (250, 254),
            'many_dot_jump_2': (255, 255),
        }
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.xmin, self.ymin, self.xmax, self.ymax = self.output_config.get('RESTRICT_POSITION', [0, 0, 255, 255])

    def get_state_effects(self):
        # return [DeadCoastingStateEffect(), IdleCoastingStateEffect(), IdleFadeoutStateEffect()]
        return [DeadPatternStateEffect(), IdleOffStateEffect()]

    def _map_full_range(self, trigger, value, threshold, cap=None):
        if value >= threshold:
            # Could do an infinite loop here but it's better to restrict retries
            for _ in range(25):
                out = random.randint(0, 255)
                if cap and (out < cap[0] or out > cap[1]):
                    continue
                return out
            # If we couldn't get something in the range, don't alter the state
            return None

    def map_pattern(self, trigger, value, threshold):
        return self._map_full_range(trigger, value, threshold)

    def map_x(self, trigger, value, threshold):
        return self._map_full_range(trigger, value, threshold, cap=(self.xmin, self.xmax))

    def map_y(self, trigger, value, threshold):
        return self._map_full_range(trigger, value, threshold, cap=(self.ymin, self.ymax))

    def map_pattern_size(self, trigger, value, threshold):
        shrink = True
        if threshold < 0:
            shrink = False
            threshold = -threshold

        if value >= threshold:
            # Instead of returning a new value, force an effect
            if shrink:
                eff = Effect(255, 0, 0.25)
            else:
                eff = Effect(0, 255, 0.25)
            self.add_effect('pattern_size', eff, overwrite=False)
