import queue
import random
import time

from . import OutputThread
from app.lib.threads import send_to
from app.lib.misc import FPSCounter


# TODO: dump this in a library somewhere
def map_to_range(num, r_min, r_max=1):
    # num is assumed to be 0-1, r_min should be <1
    return ((r_max - r_min) * num) + r_min


class BasicGoboThread(OutputThread):
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

        if self.output_config.get('LINK') and not self.output_config.get('MAPPING'):
            # We don't actually need audio data so don't configure as an output
            self.is_output = False

    def run(self):
        if hasattr(self, 'INITIALIZE'):
            self.state = dict(self.INITIALIZE)
            self.last_state = dict(self.state)
            self.send_dmx()

        fps = FPSCounter(f"Gobo {self.name}")

        while not self.stop_event.is_set():
            with fps:
                try:
                    fn, args, kwargs = self.queue.get(timeout=0.25)
                    if fn == 'set_state':
                        self.state = args[0]
                        self.send_dmx()
                        self.last_state = dict(self.state)
                        continue
                    elif fn == 'onset':
                        data = True
                    elif fn == 'audio':
                        data = args[0]
                    else:
                        continue
                    now = time.time()
                except queue.Empty:
                    pass
                else:
                    config = self.output_config.get('MAPPING') or []
                    if not config:
                        continue
                    for directive in config:
                        arg_fn = getattr(self, 'map_' + directive['function'])
                        arg = None
                        value = None
                        threshold = None
                        if fn == 'audio' and directive['trigger'] == 'frequency':
                            value = []
                            for i in directive.get('bins') or []:
                                try:
                                    iter(i)
                                except TypeError:
                                    value.append(data[i])
                                else:
                                    for j in range(i[0], i[1] + 1):
                                        value.append(data[j])
                            if not value:
                                continue
                            # value = sum(value) / len(value)
                            value = max(value)
                            threshold = directive['threshold']

                        elif fn == 'onset' and directive['trigger'] == 'onset':
                            value = random.random() / 1.5
                            threshold = 0

                        if value is None or threshold is None:
                            continue

                        arg = arg_fn(value, threshold)

                        if arg is not None:
                            if self.last_function[directive['function']] + self.RATES[directive['function']] < now:
                                self.last_function[directive['function']] = now
                                self.state[directive['function']] = arg

                self.send_dmx()
                self.last_state = dict(self.state)

                for linked in self.output_config.get('LINK') or []:
                    # Prevent an infinite loop
                    if linked.get('NAME') is None or linked.get('NAME') == self.output_config['NAME']:
                        # TODO: log
                        continue
                    linked_state = dict(self.state)
                    for fn in linked.get('INVERT') or []:
                        linked_state[fn] = 255 - linked_state[fn]
                    send_to(linked.get('NAME'), 'set_state', linked_state)

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
        # TODO: turn off after a short period
        if value > threshold:
            return int(map_to_range(value, threshold) * 255)
        return 0

    def map_dim(self, value, threshold):
        # TODO: not useful unless it can be timed
        # return 255
        if value > threshold:
            return 255
        return int(map_to_range(value, 0, threshold) * 255)

    def prep_dmx(self):
        # changed = {}
        # for k, v in self.state.items():
        #     if v != self.last_state[k]:
        #         changed[k] = v
        # if changed:
        #     print(self.name, changed)
        return dict(self.state)

    def send_dmx(self):
        state = self.prep_dmx()
        send_to('dmx', 'set_channels', {self.CHANNEL_MAP[chan] + self.output_config.get('ADDRESS', 1) - 1: val for chan, val in state.items()})


class UKingGoboThread(BasicGoboThread):
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
        'strobe': 8,
        'dim': 255,
        'speed': 255,
        'mode': 0,
        'dim_mode': 0
    }

    def prep_dmx(self):
        state = super().prep_dmx()
        state['speed'] = 255 - state['speed']
        state['mode'] = 0
        state['dim_mode'] = 0
        return state


class UnnamedGoboThread(BasicGoboThread):
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
        'dim': 255,
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