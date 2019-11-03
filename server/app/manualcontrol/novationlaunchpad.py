import json
import os

from launchpad import Launchpad, Page
from launchpad.controls import Momentary, Toggle, Slider
from launchpad.buttons import ButtonGroup
from launchpad.colors import Color, Colors, RGBColor

from app.inputs import Input
# from app.outputs.gobo import BasicGobo


class LaunchpadInput(Input):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.light_button_map = {}
        self.current_light = None
        self.lights = {}
        self.data_queue = {}

        self.recording = {'states': []}
        self.recording_ptr = -1
        self.recording_to = self.config.get('RECORD')

        self.dim_speed = 0

        if self.recording_to:
            if os.path.exists(self.recording_to):
                with open(self.recording_to, 'r') as fp:
                    self.recording = json.load(fp)
                self.recording_ptr = len(self.recording['states']) - 1
                if self.recording['states']:
                    self.set_recording_state(-1)
                else:
                    self.recording['states'].append({'lights': {}})
                    self.recording_ptr = 0

        light_buttons = []
        x = y = 0
        for i in self.config.get('OUTPUTS', []):
            if not i['DEVICE'].endswith('Gobo'):
                # FIXME: this is hacky
                continue

            c = i.get('LABEL_COLOR')
            if c:
                if isinstance(c, str):
                    c = Color(getattr(Colors, c), intensity=3)
                else:
                    c = RGBColor(*c)
            else:
                c = Color(Colors.WHITE, intensity=4)
            light_buttons.append(Momentary(on_color=Color(Colors.WHITE, intensity=1), off_color=c, callback=self.select_light, buttons=ButtonGroup(x, y, x, y)))
            self.light_button_map[(x, y)] = i['NAME']
            x += 1
            if x > 7:
                x = 0
                y += 1

        record_buttons = []
        if self.recording_to:
            record_buttons = [
                Momentary(on_color=Color(Colors.WHITE), off_color=Color(Colors.GREEN), callback=self.record_prev, buttons=ButtonGroup('TOP', 'UP')),
                Momentary(on_color=Color(Colors.WHITE), off_color=Color(Colors.GREEN), callback=self.record_next, buttons=ButtonGroup('TOP', 'DOWN')),
                Momentary(on_color=Color(Colors.WHITE), off_color=Color(Colors.RED), callback=self.record_save, buttons=ButtonGroup('TOP', 'LEFT')),
                Momentary(on_color=Color(Colors.WHITE), off_color=Color(Colors.GREEN), callback=self.record_new_state, buttons=ButtonGroup('TOP', 'RIGHT')),
            ]

        reset_buttons = [
            # Reset pan
            Momentary(on_color=Color(Colors.BLUE), off_color=Color(Colors.WHITE), callback=self.gobo_pan_reset, buttons=ButtonGroup('RIGHT', 'VOLUME')),
            # Reset tilt
            Momentary(on_color=Color(Colors.BLUE), off_color=Color(Colors.WHITE), callback=self.gobo_tilt_reset, buttons=ButtonGroup('RIGHT', 'PAN')),
            # Reset speed
            Momentary(on_color=Color(Colors.BLUE), off_color=Color(Colors.GREEN), callback=self.gobo_speed_reset, buttons=ButtonGroup('RIGHT', 'STOP')),
            # Reset dim
            Momentary(on_color=Color(Colors.BLUE), off_color=Color(Colors.YELLOW), callback=self.gobo_dim_reset, buttons=ButtonGroup('RIGHT', 'MUTE')),
            # Reset dim speed
            Momentary(on_color=Color(Colors.BLUE), off_color=Color(Colors.ORANGE), callback=self.gobo_dim_speed_reset, buttons=ButtonGroup('RIGHT', 'SOLO')),
            # Reset all
            Momentary(on_color=Color(Colors.BLUE), off_color=Color(Colors.RED), callback=self.gobo_all_reset, buttons=ButtonGroup('RIGHT', 'RECORDARM')),
        ]

        self.lp = Launchpad()
        fade = (0.1, 0.4, 0.6, 1)
        self.pages = {
            'select_light': Page(
                include_top=True,
                include_right=True,
                controls=[
                    Momentary(on_color=Color(Colors.BLUE), off_color=Color(Colors.GREEN), callback=self._no_op, buttons=ButtonGroup('TOP', 'SESSION')),
                ] + light_buttons + reset_buttons + record_buttons
            ),
            'control_gobo': Page(
                include_top=True,
                include_right=True,
                controls=[
                    # Back to light sel
                    Momentary(on_color=Color(Colors.BLUE), off_color=Color(Colors.WHITE), callback=self.select_light, buttons=ButtonGroup('TOP', 'SESSION')),
                    # Mode indicator
                    Momentary(on_color=Color(Colors.BLUE), off_color=Color(Colors.GREEN), callback=self._no_op, buttons=ButtonGroup('TOP', 'MIXER')),
                    # pan - decrease
                    Momentary(on_color=Color(Colors.WHITE), off_color=[RGBColor(v, 0, 0) for v in reversed(fade)], callback=self.gobo_pan_decrease, buttons=ButtonGroup(0, 0, 3, 0)),
                    # pan - increase
                    Momentary(on_color=Color(Colors.WHITE), off_color=[RGBColor(0, v, 0) for v in fade], callback=self.gobo_pan_increase, buttons=ButtonGroup(4, 0, 7, 0)),
                    # tilt - decrease
                    Momentary(on_color=Color(Colors.WHITE), off_color=[RGBColor(v, 0, 0) for v in reversed(fade)], callback=self.gobo_tilt_decrease, buttons=ButtonGroup(0, 1, 3, 1)),
                    # tilt - increase
                    Momentary(on_color=Color(Colors.WHITE), off_color=[RGBColor(0, v, 0) for v in fade], callback=self.gobo_tilt_increase, buttons=ButtonGroup(4, 1, 7, 1)),
                    # Colors
                    # TODO: use real colors
                    Momentary(on_color=Color(Colors.WHITE), off_color=[Color(getattr(Colors, v)) for v in ('WHITE', 'RED', 'YELLOW', 'GREEN', 'CYAN1', 'BLUE', 'PURPLE', 'PINK')], callback=self.gobo_color, buttons=ButtonGroup(0, 2, 7, 2)),
                    # Gobo
                    Momentary(on_color=Color(Colors.WHITE), off_color=Color(Colors.PURPLE), callback=self.gobo_gobo, buttons=ButtonGroup(0, 3, 7, 3)),
                    # speed - decrease
                    Momentary(on_color=Color(Colors.WHITE), off_color=[RGBColor(v, 0, 0) for v in reversed(fade)], callback=self.gobo_speed_decrease, buttons=ButtonGroup(0, 4, 3, 4)),
                    # speed - increase
                    Momentary(on_color=Color(Colors.WHITE), off_color=[RGBColor(0, v, 0) for v in fade], callback=self.gobo_speed_increase, buttons=ButtonGroup(4, 4, 7, 4)),
                    # dim - decrease
                    Momentary(on_color=Color(Colors.WHITE), off_color=[RGBColor(v, 0, 0) for v in reversed(fade)], callback=self.gobo_dim_decrease, buttons=ButtonGroup(0, 5, 3, 5)),
                    # dim - increase
                    Momentary(on_color=Color(Colors.WHITE), off_color=[RGBColor(0, v, 0) for v in fade], callback=self.gobo_dim_increase, buttons=ButtonGroup(4, 5, 7, 5)),
                    # dim speed - decrease
                    Momentary(on_color=Color(Colors.WHITE), off_color=[RGBColor(v, 0, 0) for v in reversed(fade)], callback=self.gobo_dim_speed_decrease, buttons=ButtonGroup(0, 6, 3, 6)),
                    # dim speed - increase
                    Momentary(on_color=Color(Colors.WHITE), off_color=[RGBColor(0, v, 0) for v in fade], callback=self.gobo_dim_speed_increase, buttons=ButtonGroup(4, 6, 7, 6)),
                    # Strobe
                    Momentary(on_color=Color(Colors.WHITE), off_color=[Color(Colors.RED), Color(Colors.GREEN)], callback=self.gobo_strobe, buttons=ButtonGroup(0, 7, 1, 7)),
                ] + reset_buttons + record_buttons
            )
        }
        self.lp.push_page(self.pages['select_light'])

    def add_output(self, output):
        self.lights[output.name] = output

    def set_state(self, **params):
        all_ok = params.pop('_all', False)
        light = []
        if self.current_light:
            light = self.lights.get(self.current_light)
            if light:
                light = [light]
        elif all_ok:
            # FIXME: this is also a hack
            light = [v for v in self.lights.values() if v.__class__.__name__.endswith('Gobo')]

        for l in light:
            state = dict(l.state)
            state.update(params)
            self.data_queue['gobo_state__' + l.name] = state

    def alter_state(self, **params):
        all_ok = params.pop('_all', False)
        light = []
        if self.current_light:
            light = self.lights.get(self.current_light)
            if light:
                light = [light]
        elif all_ok:
            # FIXME: this is also a hack
            light = [v for v in self.lights.values() if v.__class__.__name__.endswith('Gobo')]

        for l in light:
            state = dict(l.state)
            for k, v in params.items():
                state[k] = max(0, min(255, state[k] + v))
            self.data_queue['gobo_state__' + l.name] = state

    def run(self, data):
        data.update(self.data_queue)
        self.data_queue = {}
        self.lp.poll()

    def stop(self):
        self.lp.reset()

    def _no_op(self, lp, type_, button, value):
        # print(type_, button, value)
        pass

    def select_light(self, lp, type_, button, value):
        if value:
            if button == 'SESSION':
                self.current_light = None
                self.lp.pop_page()
            else:
                self.current_light = self.light_button_map[button]
                self.lp.push_page(self.pages['control_gobo'])

    def gobo_pan_decrease(self, lp, type_, button, value):
        if value:
            v = 2 ** (3 - button[0])
            self.alter_state(pan=-v)

    def gobo_pan_increase(self, lp, type_, button, value):
        if value:
            v = 2 ** (button[0] - 4)
            self.alter_state(pan=v)

    def gobo_tilt_decrease(self, lp, type_, button, value):
        if value:
            v = 2 ** (3 - button[0])
            self.alter_state(tilt=-v)

    def gobo_tilt_increase(self, lp, type_, button, value):
        if value:
            v = 2 ** (button[0] - 4)
            self.alter_state(tilt=v)

    def gobo_color(self, lp, type_, button, value):
        if value:
            v = button[0] + 1
            self.set_state(color=v)

    def gobo_gobo(self, lp, type_, button, value):
        if value:
            v = button[0] + 1
            self.set_state(gobo=v)

    def gobo_speed_decrease(self, lp, type_, button, value):
        if value:
            v = 2 ** (3 - button[0])
            self.alter_state(speed=-v)

    def gobo_speed_increase(self, lp, type_, button, value):
        if value:
            v = 2 ** (button[0] - 4)
            self.alter_state(speed=v)

    def gobo_dim_decrease(self, lp, type_, button, value):
        if value:
            v = 2 ** (3 - button[0])
            self.alter_state(dim=-v)

    def gobo_dim_increase(self, lp, type_, button, value):
        if value:
            v = 2 ** (button[0] - 4)
            self.alter_state(dim=v)

    def gobo_dim_speed_decrease(self, lp, type_, button, value):
        if value:
            v = (2 ** (3 - button[0])) / 4
            self.dim_speed = max(0, self.dim_speed - v)
            print("Dim speed:", self.dim_speed, "s")

    def gobo_dim_speed_increase(self, lp, type_, button, value):
        if value:
            v = (2 ** (button[0] - 4)) / 4
            self.dim_speed += v
            print("Dim speed:", self.dim_speed, "s")

    def gobo_strobe(self, lp, type_, button, value):
        if value:
            v = button[0]
            self.set_state(strobe=v)

    def gobo_pan_reset(self, lp, type_, button, value):
        if value:
            v = 0
            self.set_state(pan=v, _all=True)

    def gobo_tilt_reset(self, lp, type_, button, value):
        if value:
            v = 0
            self.set_state(tilt=v, _all=True)

    def gobo_speed_reset(self, lp, type_, button, value):
        if value:
            v = 255
            self.set_state(speed=v, _all=True)

    def gobo_dim_reset(self, lp, type_, button, value):
        if value:
            v = 255
            self.set_state(dim=v, _all=True)

    def gobo_dim_speed_reset(self, lp, type_, button, value):
        if value:
            v = 0
            self.dim_speed = v
            print("Dim speed:", v, "s")

    def gobo_all_reset(self, lp, type_, button, value):
        if value:
            self.set_state(pan=0, tilt=0, color=0, gobo=0, speed=255, dim=255, strobe=0, _all=True)

    def set_recording_state(self, ptr=None):
        if ptr is None:
            ptr = self.recording_ptr
        if ptr < 0:
            return

        for name, data in self.recording['states'][ptr]['lights'].items():
            self.current_light = name
            self.set_state(**data)
        self.current_light = None

    def record_prev(self, lp, type_, button, value):
        if value:
            if self.recording_ptr > 0:
                self.recording_ptr -= 1
                print("Switch state:", self.recording_ptr)
                self.set_recording_state()

    def record_next(self, lp, type_, button, value):
        if value:
            if self.recording_ptr < len(self.recording['states']) - 1:
                self.recording_ptr += 1
                print("Switch state:", self.recording_ptr)
                self.set_recording_state()

    def record_save(self, lp, type_, button, value):
        if value:
            # FIXME: hack
            lights = [v for v in self.lights.values() if v.__class__.__name__.endswith('Gobo')]
            if self.recording_ptr < 0:
                self.record_new_state(lp, type_, button, value)
            print("Save state:", self.recording_ptr)
            self.recording['states'][self.recording_ptr]['dim_speed'] = self.dim_speed
            for l in lights:
                self.recording['states'][self.recording_ptr]['lights'][l.name] = l.state
            with open(self.recording_to, 'w') as fp:
                json.dump(self.recording, fp, indent=2)

    def record_new_state(self, lp, type_, button, value):
        if value:
            self.recording['states'].insert(self.recording_ptr + 1, {'lights': {}})
            self.recording_ptr += 1
            print("New state:", self.recording_ptr)




# def print_key(lp, type_, button, value):
#     print(type_, button, value)

# lp = Launchpad()
# lp.push_page()
# lp.push_page(Page(
#     include_top=False,
#     include_right=False,
#     controls=[
#         Momentary(
#             on_color=Color(Colors.GREEN),
#             off_color=Color(Colors.RED),
#             callback=print_key,
#             buttons=ButtonGroup(0, 0, 0)
#         ),
#         Toggle(
#             states=2,
#             colors=[Color(Colors.RED), Color(Colors.GREEN)],
#             callback=print_key,
#             buttons=ButtonGroup(1, 0, 1)
#         ),
#         Toggle(
#             states=4,
#             colors=[Color(Colors.OFF), Color(Colors.RED), Color(Colors.GREEN), Color(Colors.BLUE)],
#             callback=print_key,
#             buttons=ButtonGroup(2, 0, 2)
#         ),
#         Slider(
#             position=3,
#             orientation=Slider.O_VT,
#             on_colors=Color(Colors.YELLOW),
#             off_color=Color(Colors.OFF),
#             color_mode=Slider.CM_ALL,
#             callback=print_key
#         ),
#         Slider(
#             position=4,
#             orientation=Slider.O_VT,
#             on_colors=[Color(Colors.GREEN), Color(Colors.YELLOW), Color(Colors.RED)],
#             off_color=Color(Colors.OFF),
#             color_mode=Slider.CM_GROUP,
#             callback=print_key
#         ),
#         Slider(
#             position=5,
#             orientation=Slider.O_VT,
#             on_colors=[Color(Colors.GREEN), Color(Colors.YELLOW), Color(Colors.RED)],
#             off_color=Color(Colors.OFF),
#             color_mode=Slider.CM_ALL,
#             callback=print_key
#         ),
#         # MultiSlider(
#         #     position=6,
#         #     orientation=Slider.O_VT,
#         #     on_colors=[Color(Colors.GREEN), Color(Colors.YELLOW), Color(Colors.RED)],
#         #     off_color=Color(Colors.OFF),
#         #     color_mode=Slider.CM_ALL,
#         #     width=2,
#         #     mode=MultiSlider.M_CONTINUOUS,
#         #     callback=print_key
#         # )
#     ]
# ))

# c=[
#     Color(Colors.OFF),
#     Color(Colors.WHITE),
#     Color(Colors.RED),
#     Color(Colors.ORANGE),
#     Color(Colors.YELLOW),
#     Color(Colors.FOREST),
#     Color(Colors.GREEN),
#     Color(Colors.LIME),
#     Color(Colors.CYAN1),
#     Color(Colors.CYAN2),
#     Color(Colors.LTBLUE),
#     Color(Colors.MDBLUE),
#     Color(Colors.BLUE),
#     Color(Colors.PURPLE),
#     Color(Colors.LTPINK),
#     Color(Colors.PINK),
# ]
# for x in range(6, 8):
#     for y in range(0, 8):
#         lp.set_color(x, y, c.pop(0))


# try:
#     while True:
#         lp.poll()

# finally:
#     lp.reset()
