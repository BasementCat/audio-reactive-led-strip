import time
import logging
import threading
import random
import math
import copy

# from launchpad import Launchpad
# from launchpad.colors import Color
# # from launchpad.clock import Clock, MidiClock
# from launchpad.pages import PageManager, Page
# from launchpad.buttons import ButtonGroup
# from launchpad.controls import Momentary, Toggle, Slider
from launchpad import *

from .tasks import Thread


logger = logging.getLogger(__name__)
lp_lock = threading.Lock()
lp_thread = None
db = None
# Light = None
network = None


class ModePage(Page):
    @property
    def groups(self):
        return super().groups + ['MODE', 'RIGHT']

    nav = Toggle(colors=[Color('BLUE'), Color('GREEN')], mutex=True, buttons=ButtonGroup((('MODE', 'SESSION'), ('MODE', 'MIXER'))))
    # TODO: handle partial suspend
    suspend = Toggle(colors=[Color('GREEN', pulse=True), Color('RED')], buttons=ButtonGroup('RIGHT', 'STOP'))

    def on_nav(self, event):
        if event.value:
            if event.control_value:
                self.last_colors = {}
                if event.button == 'SESSION':
                    pass
                elif event.button == 'MIXER':
                    event.pm.push_page(pages['light_select'])
            else:
                event.pm.pop_to_page(self)

    def on_suspend(self, event):
        if event.value:
            network.send_to_server('SUSPEND', state=event.control_value)

    def loop(self, lp):
        self.last_colors = getattr(self, 'last_colors', {})
        colors = [Color('BLUE'), Color('BLUE'), Color('GREEN'), Color('GREEN'), Color('YELLOW'), Color('YELLOW'), Color('RED'), Color('RED')]
        for command in network.get_for_client(self.id, timeout=0.001):
            if command['command'] == 'MONITOR':
                for op in command['args']:
                    if op['op'] == 'AUDIO':
                        bins = op['state']['bins']
                        bins_per = int(len(bins) / 8)
                        cur_colors = {}
                        new_bins = []
                        for i in range(0, len(bins), bins_per):
                            v = sum(bins[i:i+bins_per]) / bins_per
                            v = min(7, int(v * 8))
                            new_bins.append(v)
                        for x, v in enumerate(new_bins):
                            for y in range(8):
                                c = colors[y] if v >= y else Color('OFF')
                                y = 7 - y
                                lp.set_color(x, y, c)
                                if v >= y:
                                    cur_colors[(x, y)] = c

                        for (x, y), c in self.last_colors.items():
                            if (x, y) not in cur_colors:
                                if c.intensity > 1:
                                    c.intensity -= 1
                                    lp.set_color(x, y, c)
                        self.last_colors.update(cur_colors)
            # {'command': 'MONITOR', 'args': ({'type': None, 'name': None, 'op': 'AUDIO', 'op_state': None, 'op_name': None, 'state': {'bins': [0.0008095284154875653, 0.0004129723488438304, 0.0002619102943592236, 0.0001448746803748676, 0.00011036217143709908, 0.00014793158051035595, 0.0004249906242255858, 0.0012078756174993765, 0.0009825639937860531, 0.000850298445862784, 0.0010913673979903312, 0.0017136609089781095, 0.0020748073191475995, 0.005616237781804547, 0.0010994918672858434, 0.0007393411358778792, 0.0010158650398389665, 0.0005083017894632193, 0.0008937393676232735, 0.0009378670903511295, 0.00139282252550007, 0.0013827365999368553, 0.001389185956535607, 0.0013078198566362023]}},), 'kwargs': {}}


class LightSelectPage(Page):
    @property
    def groups(self):
        return super().groups + ['RIGHT', 'GRID']

    mode_select = Toggle(
        colors={
            ('RIGHT', 'VOLUME'): [Color('BLUE'), Color('BLUE', pulse=True)],
            ('RIGHT', 'PAN'): [Color('PINK'), Color('PINK', pulse=True)],
            ('RIGHT', 'STOP'): [Color('GREEN'), Color('GREEN', pulse=True)],
        },
        buttons=ButtonGroup((('RIGHT', 'VOLUME'), ('RIGHT', 'PAN'), ('RIGHT', 'STOP'))),
        mutex=True
    )
    light_select = Momentary(on_color=Color('OFF'), off_color=Color('OFF'), buttons=ButtonGroup())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.mode = None
        self.selected_light = None
        self.suspended_lights = []

    def add_light(self, light):
        is_new = False
        position = light.get('pos')
        if position is None:
            is_new = True

            valid_positions = [(x, y) for y in range(8) for x in range(8)]
            for type_, button in self.light_select.value_map.keys():
                if type_ == 'GRID' and button in valid_positions:
                    valid_positions.remove(button)
            if not valid_positions:
                raise RuntimeError("No empty position for new light")
            position = valid_positions[0]
        position = tuple(position)

        self.light_select.off_color[('GRID', position)] = Color(light['color'])
        self.light_select.on_color[('GRID', position)] = Color('GREEN', pulse=True)
        self.light_select.value_map[('GRID', position)] = light

        if is_new:
            return position

    def on_mode_select(self, event):
        if event.value:
            if event.control_value:
                if event.button == 'VOLUME':
                    self.mode = 'position'
                elif event.button == 'PAN':
                    self.mode = 'color'
                elif event.button == 'STOP':
                    self.mode = 'suspend'
                else:
                    # Should not happen
                    self.mode = None
            else:
                self.mode = None

            for l in self.light_select.value_map.values():
                if self.mode == 'suspend':
                    # TODO: handle suspended
                    self.light_select.off_color[('GRID', tuple(l['pos']))] = Color(l['color'], pulse=True)
                else:
                    self.light_select.off_color[('GRID', tuple(l['pos']))] = Color(l['color'])

    def on_light_select(self, event):
        if event.value:
            if self.mode == 'position':
                if not self.selected_light:
                    if event.attached_value:
                        # Mark as selected, flash the button
                        l = self.selected_light = event.attached_value
                        self.light_select.off_color[('GRID', tuple(l['pos']))] = Color(l['color'], pulse=True)
                        # TODO: needs to be reflected in the UI?
                        print("Selected", l['name'])
                else:
                    if event.attached_value:
                        # A light is already here, reset the color and deselect
                        self.light_select.off_color[('GRID', tuple(self.selected_light['pos']))] = Color(self.selected_light['color'])
                        self.selected_light = None
                    else:
                        # Attempt to move the light to the new position
                        old_pos = tuple(self.selected_light['pos'])
                        new_pos = event.button
                        self.light_select.off_color[('GRID', old_pos)] = Color('OFF')
                        self.light_select.on_color[('GRID', old_pos)] = Color('OFF')
                        self.light_select.off_color[('GRID', new_pos)] = Color(self.selected_light['color'])
                        self.light_select.on_color[('GRID', new_pos)] = Color('GREEN', pulse=True)
                        self.light_select.value_map[('GRID', new_pos)] = self.light_select.value_map.pop(('GRID', old_pos))
                        self.selected_light['pos'] = new_pos
                        with db:
                            self.selected_light['pos'] = new_pos
                            db.save()
                        self.selected_light = None
            elif self.mode == 'color':
                if event.attached_value:
                    self.selected_light = event.attached_value

                    def _select_color(event, color):
                        with db:
                            self.selected_light['color'] = color
                            db.save()
                        self.light_select.off_color[('GRID', tuple(self.selected_light['pos']))] = Color(color)
                        event.pm.pop_page()
                        self.selected_light = None

                    self.selected_light
                    event.pm.push_page(ColorSelectPage(_select_color))
            elif self.mode == 'suspend':
                light = event.attached_value
                if light:
                    state = light['name'] not in self.suspended_lights
                    network.send_to_server('SUSPEND', light['name'], state=state)
                    if state:
                        self.light_select.off_color[('GRID', tuple(light['pos']))] = Color('RED')
                        self.suspended_lights.append(light['name'])
                    else:
                        self.light_select.off_color[('GRID', tuple(light['pos']))] = Color(light['color'], pulse=True)
                        self.suspended_lights.remove(light['name'])

            else:
                if event.attached_value:
                    event.pm.push_page(LightControlPage(event.attached_value))


class ColorSelectPage(Page):
    @property
    def groups(self):
        return super().groups + ['RIGHT', 'GRID', 'NAV', 'MODE']

    def __init__(self, sel_callback, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.sel_callback = sel_callback

    _colors = [Color(x) for x in list(Color.COLORS.keys())[1:]]
    color_select = Momentary(off_color=_colors, value_map=ButtonMap(_colors), buttons=ButtonGroup(0, 0, 7, 2))

    def on_color_select(self, event):
        if event.value and event.attached_value:
            self.sel_callback(event, event.attached_value.color)


class RecordDurationPage(Page):
    groups=['GRID']

    duration_pb = Momentary(on_color=Color('PINK'), off_color=Color('BLUE', pulse=True), buttons=ButtonGroup(0, 0, 0, 7))
    duration_b = Momentary(on_color=Color('PINK'), off_color=Color('BLUE'), buttons=ButtonGroup(1, 0, 1, 7))

    duration_pm = Momentary(on_color=Color('PINK'), off_color=Color('YELLOW', pulse=True), buttons=ButtonGroup(3, 0, 3, 7))
    duration_m = Momentary(on_color=Color('PINK'), off_color=Color('YELLOW'), buttons=ButtonGroup(4, 0, 4, 7))

    duration_ps = Momentary(on_color=Color('PINK'), off_color=Color('WHITE', pulse=True), buttons=ButtonGroup(6, 0, 6, 7))
    duration_s = Momentary(on_color=Color('PINK'), off_color=Color('WHITE'), buttons=ButtonGroup(7, 0, 7, 7))

    def __init__(self, control_page, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.control_page = control_page

    def _set_duration(self, event, unit, partial):
        partial_map = {
            0: 128,
            1: 64,
            2: 32,
            3: 16,
            4: 8,
            5: 4,
            6: 2,
            7: 1,
        }
        if event.value:
            if partial:
                value = 1 / partial_map[event.button[1]]
            else:
                value = 8 - event.button[1]
            self.control_page.record_duration(event, value, unit)

    def on_duration_pb(self, event):
        self._set_duration(event, unit='b', partial=True)

    def on_duration_b(self, event):
        self._set_duration(event, unit='b', partial=False)

    def on_duration_pm(self, event):
        self._set_duration(event, unit='m', partial=True)

    def on_duration_m(self, event):
        self._set_duration(event, unit='m', partial=False)

    def on_duration_ps(self, event):
        self._set_duration(event, unit='s', partial=True)

    def on_duration_s(self, event):
        self._set_duration(event, unit='s', partial=False)


class RecordControlPage(Page):
    groups = ['RIGHT']

    effect_item = Toggle(
        colors=ColorMap([
            [Color('GREEN'), Color('GREEN', pulse=True)],
            [Color('YELLOW'), Color('YELLOW', pulse=True)],
            [Color('RED'), Color('RED', pulse=True)],
            [Color('WHITE'), Color('WHITE', pulse=True)],
            [Color('GREEN'), Color('GREEN', pulse=True)],
        ]),
        mutex=True,
        buttons=ButtonGroup((
            ('RIGHT', 'VOLUME'),  # Start
            ('RIGHT', 'PAN'),  # End
            ('RIGHT', 'SENDA'),  # Done
            ('RIGHT', 'SENDB'),  # Duration
            ('RIGHT', 'SOLO'),  # Property
        ))
    )
    toggle_current_random = Toggle(colors=[Color('ORANGE'), Color('BLUE'), Color('PINK')], states=3, buttons=ButtonGroup('RIGHT', 'MUTE'))
    stop_recording = Momentary(on_color=Color('GREEN'), off_color=Color('RED'), buttons=ButtonGroup('RIGHT', 'STOP'))
    save_recording = Momentary(on_color=Color('WHITE'), off_color=Color('GREEN', pulse=True), buttons=ButtonGroup('RIGHT', 'RECORDARM'))

    def __init__(self, control_page, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.control_page = control_page

    def record_duration(self, event, value, unit):
        self.control_page.record_duration(event, value, unit)
        event.pm.pop_to_page(self)

    def on_effect_item(self, event):
        if event.value:
            # Ensure the record duration page isn't pushed
            event.pm.pop_to_page(self)
            state_map = {
                ('RIGHT', 'VOLUME'): 'start',
                ('RIGHT', 'PAN'): 'end',
                ('RIGHT', 'SENDA'): 'done',
                ('RIGHT', 'SENDB'): 'duration',
                ('RIGHT', 'SOLO'): 'property',
            }
            state = None
            if event.control_value:
                state = state_map[(event.type, event.button)]
                self.control_page.record_focus(event, state)
                if state == 'duration':
                    # TODO: send in control page
                    event.pm.push_page(RecordDurationPage(self))
            else:
                self.control_page.record_focus(event, None)

    def on_toggle_current_random(self, event):
        if event.value:
            self.control_page.record_toggle_current_random(event, ['state', 'current', 'random'][event.control_value])

    def on_save_recording(self, event):
        if event.value:
            self.control_page.record_save(event)
            self.on_stop_recording(event)

    def on_stop_recording(self, event):
        if event.value:
            self.control_page.record_cancel(event)
            event.pm.pop_to_page(self.control_page)


class LightControlPage(NavigablePage):
    @property
    def groups(self):
        return super().groups + ['RIGHT', 'GRID', 'MODE']

    # Misc
    exit = Momentary(off_color=Color('RED'), buttons=ButtonGroup('MODE', 'MIXER'))
    # Recording controls
    start_recording = Momentary(on_color=Color('WHITE'), off_color=Color('GREEN'), buttons=ButtonGroup('RIGHT', 'RECORDARM'))

    MOVEMENT_COLORS = [
        Color('GREEN', intensity=4),
        Color('GREEN', intensity=2),
        Color('GREEN', intensity=1),
        Color('WHITE'),
        Color('RED'),
        Color('GREEN', intensity=1),
        Color('GREEN', intensity=2),
        Color('GREEN', intensity=4),
    ]

    GOBO_COLORS = {
        'none': ('WHITE', False),
        'broken_circle': ('RED', False),
        'burst': ('ORANGE', False),
        '3_spot_circle': ('YELLOW', False),
        'square_spots': ('GREEN', False),
        'droplets': ('CYAN1', False),
        'swirl': ('BLUE', False),
        'stripes': ('PINK', False),

        'dither_none': ('WHITE', False),
        'dither_broken_circle': ('RED', 'WHITE'),
        'dither_burst': ('ORANGE', 'WHITE'),
        'dither_3_spot_circle': ('YELLOW', 'WHITE'),
        'dither_square_spots': ('GREEN', 'WHITE'),
        'dither_droplets': ('CYAN1', 'WHITE'),
        'dither_swirl': ('BLUE', 'WHITE'),
        'dither_stripes': ('PINK', 'WHITE'),
    }

    COLOR_COLORS = {
        'blue': ('BLUE', False),
        'blue_green': ('BLUE', 'GREEN'),
        'cyan': ('CYAN1', False),
        'cyan_blue': ('CYAN1', 'BLUE'),
        'green': ('GREEN', False),
        'green_pink': ('GREEN', 'PINK'),
        'orange': ('ORANGE', False),
        'orange_cyan': ('ORANGE', 'CYAN1'),
        'pink': ('PINK', False),
        'pink_red': ('PINK', 'RED'),
        'red': ('RED', False),
        'white': ('WHITE', False),
        'yellow': ('YELLOW', False),
        'yellow_orange': ('YELLOW', 'ORANGE'),

        # Alt mappings
        'blue_green': ('BLUE','GREEN'),
        'cyan_orange': ('CYAN1','ORANGE'),
        'orange_yellow': ('ORANGE','YELLOW'),
        'pink_cyan': ('PINK','CYAN1'),
        'yellow_blue': ('YELLOW','BLUE'),
    }

    MODE_COLORS = {
        # Lasers, etc
        'off': ('RED', False),
        'static': ('CYAN1', False),
        'dynamic': ('CYAN1', 'BLUE'),
        'sound': ('BLUE', 'OFF'),
        'auto': ('GREEN', 'OFF'),
    }


    def __init__(self, light, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._main_controls_x = 0
        self._sub_controls_x = 0
        self.light = light

        self.record_focused = None

        # Moving head lights
        if 'pan' in light['functions']:
            self.pan = Momentary(on_color=Color('PINK'), off_color=self.MOVEMENT_COLORS, buttons=ButtonGroup(self._main_controls_x, 0, self._main_controls_x, 7))
            self._main_controls_x += 1

        if 'tilt' in light['functions']:
            self.tilt = Momentary(on_color=Color('PINK'), off_color=self.MOVEMENT_COLORS, buttons=ButtonGroup(self._main_controls_x, 0, self._main_controls_x, 7))
            self._main_controls_x += 1

        if 'dim' in light['functions']:
            self.dim = Slider(self._main_controls_x, 8, on_colors=[Color('WHITE', intensity=x) for x in (4, 3, 2, 1)], color_mode=Slider.CM_GROUP)
            self._main_controls_x += 1

        if 'strobe' in light['functions']:
            self.strobe = Slider(self._main_controls_x, 8, on_colors=[Color('RED')] + [Color('YELLOW') for _ in range(7)], color_mode=Slider.CM_GROUP)
            self._main_controls_x += 1

        # Gobos
        if 'gobo' in light['enums']:
            colors = []
            values = []
            for k, v in self.GOBO_COLORS.items():
                e = light['enums']['gobo'].get(k)
                if e:
                    colors.append([Color(v[0], flash=v[1]), Color(v[0], pulse=True)])
                    values.append(e[0])
            num_cols = math.ceil(len(colors) / 8)
            self.gobo = Toggle(
                colors=ColorMap(colors),
                value_map=ButtonMap(values),
                mutex=True,
                buttons=ButtonGroup(self._main_controls_x, 0, self._main_controls_x + num_cols - 1, 7)
            )
            self._main_controls_x += num_cols

        # Static colors
        if 'color' in light['enums']:
            colors = []
            values = []
            for k, v in self.COLOR_COLORS.items():
                e = light['enums']['color'].get(k)
                if e:
                    colors.append([Color(v[0], flash=v[1]), Color(v[0], pulse=True)])
                    values.append(e[0])
            num_cols = math.ceil(len(colors) / 8)
            self.color = Toggle(
                colors=ColorMap(colors),
                value_map=ButtonMap(values),
                mutex=True,
                buttons=ButtonGroup(self._main_controls_x, 0, self._main_controls_x + num_cols - 1, 7)
            )
            self._main_controls_x += num_cols

        # RGB, etc
        for prop, c in (('red', 'RED'), ('green', 'GREEN'), ('blue', 'BLUE'), ('white', 'WHITE'), ('amber', 'YELLOW'), ('uv', 'PURPLE')):
            if prop in light['functions']:
                setattr(self, prop, Slider(
                    self._main_controls_x,
                    8,
                    on_colors=Color(c)
                ))
                self._main_controls_x += 1

        # Lasers
        if 'x' in light['functions']:
            self.x = Momentary(on_color=Color('PINK'), off_color=self.MOVEMENT_COLORS, buttons=ButtonGroup(self._main_controls_x, 0, self._main_controls_x, 7))
            self._main_controls_x += 1

        if 'y' in light['functions']:
            self.y = Momentary(on_color=Color('PINK'), off_color=self.MOVEMENT_COLORS, buttons=ButtonGroup(self._main_controls_x, 0, self._main_controls_x, 7))
            self._main_controls_x += 1

        if 'mode' in light['enums']:
            colors = []
            values = []
            for k, v in self.MODE_COLORS.items():
                e = light['enums']['mode'].get(k)
                if e:
                    colors.append([Color(v[0], flash=v[1]), Color(v[0], pulse=True)])
                    values.append(e[0])
            num_cols = math.ceil(len(colors) / 8)
            self.mode = Toggle(
                colors=ColorMap(colors),
                value_map=ButtonMap(values),
                mutex=True,
                buttons=ButtonGroup(self._main_controls_x, 0, self._main_controls_x + num_cols - 1, 7)
            )
            self._main_controls_x += num_cols

        if 'scan_speed' in light['functions']:
            self.scan_speed = Slider(self._main_controls_x, 8, on_colors=[Color('BLUE', intensity=x) for x in (4, 3, 2, 1)], color_mode=Slider.CM_GROUP)
            self._main_controls_x += 1

        if 'pattern_speed' in light['functions']:
            self.pattern_speed = Slider(self._main_controls_x, 8, on_colors=[Color('WHITE', intensity=x) for x in (4, 3, 2, 1)], color_mode=Slider.CM_GROUP)
            self._main_controls_x += 1

        if 'pattern_size' in light['functions']:
            self.pattern_size = Slider(self._main_controls_x, 8, on_colors=[Color('GREEN', intensity=x) for x in (4, 3, 2, 1)], color_mode=Slider.CM_GROUP)
            self._main_controls_x += 1

        # Patterns might be very large
        if 'pattern' in light['functions'] and ('pattern_static' in light['enums'] or 'pattern_dynamic' in light['enums']):
            # This is making some assumptions that static/dynamic pattern count is the same, as are the offsets
            # Currently this is true
            num_cols = math.ceil(len(light['enums']['pattern_static']) / 8)
            self.pattern = Toggle(
                colors=ColorMap([[Color('ORANGE'), Color('ORANGE', pulse=True)] for _ in range(len(light['enums']['pattern_static']))]),
                value_map=ButtonMap([e[0] for e in light['enums']['pattern_static'].values()]),
                mutex=True,
                buttons=ButtonGroup(self._sub_controls_x, 8, self._sub_controls_x + num_cols - 1, 15)
            )
            self._sub_controls_x += num_cols

        network.send_to_client('C_SELECT', light['name'])

    @property
    def size(self):
        return (max(self._main_controls_x, self._sub_controls_x), 16 if self._sub_controls_x else 8)

    # Recording controls
    def record_focus(self, event, control):
        self.record_focused = control
        network.send_to_client('C_FOCUS', control)

    def record_duration(self, event, value, unit):
        network.send_to_client('C_DURATION', value, unit)

    def record_toggle_current_random(self, event, value):
        if self.record_focused in ('start', 'end'):
            network.send_to_client('C_SET_VALUE', value)

    def record_save(self, event):
        network.send_to_client('C_SAVE')

    def record_cancel(self, event):
        network.send_to_client('C_CANCEL')

    # Button handlers
    def on_exit(self, event):
        if event.value:
            event.pm.pop_to_page(pages['light_select'])
            network.send_to_client('C_DESELECT')

    def on_start_recording(self, event):
        if event.value:
            event.pm.push_page(RecordControlPage(self))

    def _check_record_focused(self, event, prop):
        if event.value:
            if self.record_focused == 'property':
                network.send_to_client('C_PROPERTY', prop)
                return True

    def _incr_decr_value(self, prop, event):
        if event.value:
            _map = {
                0: (50, None),
                1: (10, None),
                2: (1, None),
                3: (None, 127),
                4: (None, 0),
                5: (-1, None),
                6: (-10, None),
                7: (-50, None),
            }
            v, sv = _map[event.button[1]]
            if sv is not None:
                print(prop, '@', sv)
                network.send_to_server('SET', self.light['name'], **{prop: sv})
            else:
                print(prop, 'inc', v)
                network.send_to_server('SET', self.light['name'], _relative=True, **{prop: v})

    def _slider_value(self, prop, event):
        if event.value:
            sv = int((255 / 7) * (event.control_value - 1))
            print(prop, '@', sv)
            network.send_to_server('SET', self.light['name'], **{prop: sv})

    def _enum_value(self, prop, event):
        if event.value:
            print(prop, '@', event.attached_value)
            network.send_to_server('SET', self.light['name'], **{prop: event.attached_value})

    def on_pan(self, event):
        if self._check_record_focused(event, 'pan'):
            return
        self._incr_decr_value('pan', event)

    def on_tilt(self, event):
        if self._check_record_focused(event, 'tilt'):
            return
        self._incr_decr_value('tilt', event)

    def on_dim(self, event):
        if self._check_record_focused(event, 'dim'):
            return
        self._slider_value('dim', event)

    def on_strobe(self, event):
        if self._check_record_focused(event, 'strobe'):
            return
        self._slider_value('strobe', event)

    def on_gobo(self, event):
        if self._check_record_focused(event, 'gobo'):
            return
        self._enum_value('gobo', event)

    def on_color(self, event):
        if self._check_record_focused(event, 'color'):
            return
        self._enum_value('color', event)

    def on_red(self, event):
        if self._check_record_focused(event, 'red'):
            return
        self._slider_value('red', event)

    def on_green(self, event):
        if self._check_record_focused(event, 'green'):
            return
        self._slider_value('green', event)

    def on_blue(self, event):
        if self._check_record_focused(event, 'blue'):
            return
        self._slider_value('blue', event)

    def on_white(self, event):
        if self._check_record_focused(event, 'white'):
            return
        self._slider_value('white', event)

    def on_amber(self, event):
        if self._check_record_focused(event, 'amber'):
            return
        self._slider_value('amber', event)

    def on_uv(self, event):
        if self._check_record_focused(event, 'uv'):
            return
        self._slider_value('uv', event)

    def on_x(self, event):
        if self._check_record_focused(event, 'x'):
            return
        self._incr_decr_value('x', event)

    def on_y(self, event):
        if self._check_record_focused(event, 'y'):
            return
        self._incr_decr_value('y', event)

    def on_mode(self, event):
        if self._check_record_focused(event, 'mode'):
            return
        self._enum_value('mode', event)

    def on_scan_speed(self, event):
        if self._check_record_focused(event, 'scan_speed'):
            return
        self._slider_value('scan_speed', event)

    def on_pattern_speed(self, event):
        if self._check_record_focused(event, 'pattern_speed'):
            return
        self._slider_value('pattern_speed', event)

    def on_pattern_size(self, event):
        if self._check_record_focused(event, 'pattern_size'):
            return
        self._slider_value('pattern_size', event)

    def on_pattern(self, event):
        if self._check_record_focused(event, 'pattern'):
            return
        self._enum_value('pattern', event)


pages = {
    'mode': ModePage(),
    'light_select': LightSelectPage(),
}


class LPControlThread(Thread):
    def setup(self):
        global lp_thread
        if lp_thread:
            return
        lp_thread = self
        self.lp = None
        self.pm = None
        self.connect()

    def connect(self, wait=False):
        with lp_lock:
            while not self.lp and not self.stop_event.is_set():
                logger.debug("Connecting to launchpad...")
                try:
                    self.lp = Launchpad.open()
                    self.pm = PageManager(self.lp)
                    self.pm.push_page(pages['mode'])
                    logger.info("Connected to launchpad")
                except:
                    logger.warning("Failed to connect", exc_info=True)
                    if wait:
                        time.sleep(1)
                    else:
                        break

    def run(self):
        global db, network
        if lp_thread is not self:
            return
        from app import database as db_
        db = db_
        from app import network as network_
        network = network_
        super().run()
        if self.lp:
            self.lp.reset()

    def loop(self):
        self.connect(wait=True)
        time.sleep(1)
        self.setup_lights()
        if self.pm:
            self.pm.poll(stop_event=self.stop_event)

    def setup_lights(self):
        api_lights = network.get_lights()
        logger.debug("Found %d lights", len(api_lights))
        for api_light in api_lights:
            # hax!
            if not any((k in api_light.get('functions', []) for k in ('pan', 'tilt', 'color', 'gobo', 'strobe', 'dim', 'x', 'y'))):
                continue

            with db:
                db_light = db['lights'].get(api_light['name'])
                if db_light:
                    db_light.update(copy.deepcopy(api_light))
                else:
                    db_light = copy.deepcopy(api_light)
                    db_light['color'] = 'WHITE'
                    db['lights'][db_light['name']] = db_light

                pos = pages['light_select'].add_light(db_light)
                if pos:
                    db_light['pos'] = pos
                    db.save()
