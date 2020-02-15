import random
import time
import itertools

from . import Output
from app.effects import Effect
from app.lib.misc import FPSCounter


# TODO: dump this in a library somewhere
def map_to_range(num, r_min, r_max=1):
    # num is assumed to be 0-1, r_min should be <1
    return ((r_max - r_min) * num) + r_min


class BasicGobo(Output):
    FUNCTIONS = {
        'pan': 1,
        'tilt': 3,
        'color': 5,
        'gobo': 6,
        'strobe': 7,
        'dim': 8,
    }

    RATES = {
        'pan': 0.75,
        'tilt': 0.75,
        'color': 0.5,
        'gobo': 0.5,
        'strobe': 10,
        'dim': 0.125,
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.last_function = {
            'pan': 0,
            'tilt': 0,
            'color': 0,
            'gobo': 0,
            'strobe': 0,
            'dim': 0,
        }
        self.state = {
            'pan': 0,
            'tilt': 0,
            'color': 0,
            'gobo': 0,
            'strobe': 0,
            'dim': 255,
            'speed': 255,
        }
        self.last_state = dict(self.state)
        self.fps = FPSCounter(f"Gobo {self.name}")
        self.effects = {}

        # if self.output_config.get('MAPPING'):
        #     # Need audio data
        #     subscribe('audio', self.handle_audio)
        #     subscribe('beat', self.handle_beat)
        #     subscribe('onset', self.handle_onset)
        #     subscribe('idle_for', self.handle_idle_for)
        #     subscribe('dead_for', self.handle_dead_for)
        #     subscribe('idle_instant', self.handle_idle_instant)
        # # Also provide a way to get state from elsewhere
        # subscribe('set_state__' + self.name, self.handle_set_state)

    def start(self, data):
        if hasattr(self, 'INITIALIZE'):
            self.state = dict(self.INITIALIZE)
            self.last_state = dict(self.state)
            self.send_dmx(data)

    def run(self, data):
        with self.fps:
            new_state = data.get('gobo_state__' + self.name)
            if new_state:
                self.state = dict(new_state)
            if self.output_config.get('MAPPING'):
                self._run_effects(data)

                fns = [
                    self._apply_dead_coasting,
                    self._apply_idle_coasting,
                    self._apply_idle_fadeout,
                    self._run_mapping,
                ]
                for fn in fns:
                    if fn(data):
                        break

            self.send_dmx(data)

    def _apply_dead_coasting(self, data):
        speed = 20
        dim = 75
        if (data.get('dead_for') or 0) >= 2:
            # If we're dead for 2s, go into dead coasting
            if self.state['speed'] != speed or self.state['dim'] != dim:
                self.state['speed'] = speed
                self.effects['dim'] = Effect(self.state['dim'], dim, 1, dim)
                self.send_dmx(data, True)
            if 'pan' not in self.effects:
                self.effects['pan'] = Effect(self.state['pan'], random.randint(0, 255), 8)
            if 'tilt' not in self.effects:
                self.effects['tilt'] = Effect(self.state['tilt'], random.randint(0, 255), 8)
            if 'color' not in self.effects:
                v = self.map_color(1, 0)
                self.effects['color'] = Effect(v, v, 8)
            if 'gobo' not in self.effects:
                v = self.map_gobo(1, 0)
                self.effects['gobo'] = Effect(v, v, 8)

            return True
        # else:
        #     # Not dead anymore
        #     for k in ('pan', 'tilt', 'color', 'gobo', 'dim'):
        #         if k in self.effects:
        #             del self.effects[k]
        #     if self.state['speed'] != 255 or self.state['dim'] != 255:
        #         self.state['speed'] = 255
        #         self.state['dim'] = 255
        #         self.send_dmx(data, True)

    def _apply_idle_coasting(self, data):
        speed = 31
        idle_pan_tilt = time.time() - max(self.last_function['pan'], self.last_function['tilt']) >= 2
        if data.get('audio_v_sum') and idle_pan_tilt:
            # Below threshold, but there's still audio
            # Only called if mapping is set
            if self.state['speed'] != speed:
                self.state['speed'] = speed
                self.send_dmx(data, True)
            if 'pan' not in self.effects:
                self.effects['pan'] = Effect(self.state['pan'], random.randint(0, 255), 5)
            if 'tilt' not in self.effects:
                self.effects['tilt'] = Effect(self.state['tilt'], random.randint(0, 255), 5)

            # Don't return true, so that mapping is still run
            # This allows pan/tilt to be updated
            # return True
        # else:
        #     for k in ('pan', 'tilt'):
        #         if k in self.effects:
        #             del self.effects[k]
        #     if self.state['speed'] != 255:
        #         self.state['speed'] = 255
        #         self.send_dmx(data, True)

    def _apply_idle_fadeout(self, data):
        if data.get('idle_for'):
            if 'dim' not in self.effects and self.state['dim'] > 0:
                self.effects['dim'] = Effect(self.state['dim'], 0, 0.5)

            return True
        # else:
        #     if 'dim' in self.effects:
        #         del self.effects['dim']
        #     self.state['dim'] = 255

    def _run_mapping(self, data):
        config = self.output_config.get('MAPPING') or []
        now = time.time()
        new_state = {}

        for directive in config:
            arg_fn = getattr(self, 'map_' + directive['function'])
            arg = None
            value = None
            threshold = None

            if data.get('audio') is not None and directive['trigger'] == 'frequency':
                value = []
                for i in directive.get('bins') or []:
                    try:
                        iter(i)
                    except TypeError:
                        value.append(data['audio'][i])
                    else:
                        for j in range(i[0], i[1] + 1):
                            value.append(data['audio'][j])
                if not value:
                    continue
                # value = sum(value) / len(value)
                value = max(value)
                threshold = directive['threshold']

            elif data.get('is_onset') and directive['trigger'] == 'onset':
                value = random.random() / 1.5
                threshold = 0

            elif data.get('is_beat') and directive['trigger'] == 'beat':
                value = random.random() / 1.5
                threshold = 0

            if value is None or threshold is None:
                continue

            arg = arg_fn(value, threshold)

            if arg is not None:
                if self.last_function[directive['function']] + self.RATES[directive['function']] < now:
                    self.last_function[directive['function']] = now
                    new_state[directive['function']] = arg

        if new_state:
            # Not dead anymore
            for k in ('pan', 'tilt', 'color', 'gobo', 'dim'):
                if k in self.effects:
                    del self.effects[k]
            if self.state['speed'] != 255 or self.state['dim'] != 255:
                self.state['speed'] = 255
                self.state['dim'] = 255
                self.send_dmx(data, True)
            self.state.update(new_state)

    def _run_effects(self, data):
        done = []
        for fn, e in self.effects.items():
            value = None
            if e.done:
                value = e.done_value
                done.append(fn)
            else:
                value = e.value

            self.state[fn] = value
            # print(f"effect {fn} {value}")

        for k in done:
            del self.effects[k]

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

    def map_pan(self, value, threshold):
        return self._map_pan_tilt('pan', value, threshold)

    def map_tilt(self, value, threshold):
        return self._map_pan_tilt('tilt', value, threshold)

    def map_color(self, value, threshold):
        if value >= threshold:
            half_color = random.random() > 0.75
            if half_color:
                return random.randint(57, 127)
            return random.randint(0, 56)

    def map_gobo(self, value, threshold):
        if value >= threshold:
            dither = random.random() > 0.75
            if dither:
                return random.randint(64, 127)
            return random.randint(0, 63)

    def map_strobe(self, value, threshold):
        # should set a high threshold for this
        if value > threshold:
            # TODO: might need a different value for some lights
            if 'strobe' not in self.effects:
                self.effects['strobe'] = Effect(255, 255, 1, 0)

    def map_dim(self, value, threshold):
        # Use effects/dead instead
        return
        # if value > threshold:
        #     if 'dim' in self.effects:
        #         del self.effects['dim']
        #     return 255
        # if 'dim' not in self.effects and self.state['dim'] > 0:
        #     self.effects['dim'] = Effect(255, 0, 0.5)

    def prep_dmx(self):
        out = dict(self.state)
        changed = {}
        for k, v in out.items():
            if v != self.last_state[k]:
                changed[k] = v
        # if changed:
        #     print(self.name, changed)
        return out

    def send_dmx(self, data, force=False):
        if self.config.get('ENABLE_LINKS'):
            # Update linked state prior to prep
            for linked in self.output_config.get('LINK') or []:
                # Prevent an infinite loop
                if linked.get('NAME') is None or linked.get('NAME') == self.output_config['NAME']:
                    # TODO: log
                    continue
                linked_state = dict(self.state)
                for fn in linked.get('INVERT') or []:
                    linked_state[fn] = 255 - linked_state[fn]
                data['gobo_state__' + linked.get('NAME')] = linked_state

        state = self.prep_dmx()
        channels = {self.CHANNEL_MAP[chan] + self.output_config.get('ADDRESS', 1) - 1: val for chan, val in state.items()}
        data.setdefault('dmx_force' if force else 'dmx', {}).update(channels)
        # TODO: send to linked
        self.last_state = dict(self.state)


class UKingGobo(BasicGobo):
    CHANNEL_MAP = {
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
        'dim': 0,
        'speed': 255,
        'mode': 0,
        'dim_mode': 0
    }

    def prep_dmx(self):
        state = super().prep_dmx()
        state['speed'] = 255 - state['speed']
        state['strobe'] = 255 - state['strobe']
        state['mode'] = 0
        state['dim_mode'] = 0
        return state


class UnnamedGobo(BasicGobo):
    CHANNEL_MAP = {
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
        'dim': 0,
        'speed': 255,
        'mode': 0,
        'dim_mode': 0,
    }

    def prep_dmx(self):
        state = super().prep_dmx()
        state['speed'] = 255 - state['speed']
        state['mode'] = 0
        state['dim_mode'] = 0
        return state