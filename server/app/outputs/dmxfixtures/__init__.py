import random
import time

from app.outputs import Output
from app.effects import Effect
from app.lib.misc import FPSCounter
from app.lib.network import send_monitor


class BasicDMX(Output):
    """\
    Basic DMX light

    Properties:
    FUNCTIONS: Dict mapping function names to DMX channels
        Common functions are:
            strobe - strobe control (on/off/speed)
            dim - Dimming
            pan/tilt/speed - for moving head lights
            color - For lights with a color gobo
            gobo - For lights with a pattern gobo
            red/green/blue - RGB lights
            white/amber/uv - Lights w/ additional colors
    RATES: Dict mapping each function to how often it's allowed to change
    SPEEDS: For each function, how long does that function take to change (based on the set speed) - pair of min/max values, or single value if it is not dependent upon speed
    ENUMS: For functions with fixed sets of values, a dictionary of function name -> value name -> value range pair
    INITIALIZE: Dict of initial function values
    INVERT: List of properties to invert
    CLEAR_EFFECTS_ON_NEW_STATE: List of properties to remove effects for when a
        new state is generated in the mapping (use __all__ to clear all effects)
    RESET_ON_NEW_STATE: List of properties to reset to their value in INITIALIZE
        (or 0 if not present) when a new state is generated in the mapping
    MULTI_PROP_MAP: Dict mapping a multi-value property to the list of correct functions
    """

    FUNCTIONS = {}
    RATES = {}
    SPEEDS = {}
    ENUMS = {}
    INITIALIZE = {}
    INVERT = []
    CLEAR_EFFECTS_ON_NEW_STATE = []
    RESET_ON_NEW_STATE = []
    MULTI_PROP_MAP = {}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.INITIALIZE = dict(self.INITIALIZE, **self.output_config.get('INITIALIZE', {}))
        self.last_function = {k: 0 for k in list(self.RATES.keys()) + list(self.FUNCTIONS.keys())}
        self.state = {k: 0 for k in self.FUNCTIONS.keys()}
        self.state.update(self.INITIALIZE)
        self.last_state = dict(self.state)
        self.auto_state = dict(self.state)
        self.last_auto_state = dict(self.state)
        self.fps = FPSCounter(f"{self.__class__.__name__} {self.name}")
        self.effects = {}
        self.state_effect = None
        self.state_effects = self.get_state_effects()

    def start(self, data):
        self.state.update(self.INITIALIZE)
        self.last_state = dict(self.state)
        self.auto_state = dict(self.state)
        self.last_auto_state = dict(self.state)
        self.send_dmx(data)

    def get_state_effects(self):
        """\
        Return a list of state effects to run after effects but before mapping. The
        objects should inherit from effects.StateEffect.
        """
        return []

    def run(self, data):
        with self.fps:
            new_state = data.get('push_state__' + self.name)
            if new_state:
                self.auto_state = dict(new_state)
            # Normally, lights without a mapping won't have effects, unless added via non-automation
            self._run_effects(data)
            if self.output_config.get('MAPPING'):
                if self.state_effect:
                    if not self.state_effect.applicable(self, data):
                        send_monitor(self, 'STATE_EFFECT', opstate='DONE', opname=self.state_effect.__class__.__name__)
                        self.state_effect.unapply(self, data)
                        self.state_effect = None
                        self.send_dmx(data, True)
                    else:
                        self.state_effect.run(self, data)

                for e in self.state_effects:
                    if e is self.state_effect:
                        break
                    if e.applicable(self, data):
                        if self.state_effect:
                            send_monitor(self, 'STATE_EFFECT', opstate='DONE', opname=self.state_effect.__class__.__name__)
                            self.state_effect.unapply(self, data)
                        self.state_effect = e
                        e.apply(self, data)
                        self.send_dmx(data, True)
                        send_monitor(self, 'STATE_EFFECT', opstate='NEW', opname=self.state_effect.__class__.__name__)
                        break

                self._run_mapping(data)

            self.send_dmx(data)

    def add_effect(self, k, effect, overwrite=False):
        if overwrite or k not in self.effects:
            send_monitor(self, 'EFFECT', opstate='NEW', opname=k, **effect.args)
            self.effects[k] = effect

    def _run_effects(self, data):
        done = []
        for fn, e in self.effects.items():
            dest = self.auto_state if e.automation else self.state
            value = None
            if e.done:
                value = e.done_value
                done.append(fn)
            else:
                value = e.value

            if fn in self.MULTI_PROP_MAP:
                dest.update(dict(zip(self.MULTI_PROP_MAP[fn], value)))
            else:
                dest[fn] = value

        for k in done:
            send_monitor(self, 'EFFECT', opstate='DONE', opname=k, **self.effects[k].args)
            del self.effects[k]

    def _run_mapping(self, data):
        config = self.output_config.get('MAPPING') or []
        now = time.time()
        new_state = {}

        for directive in config:
            arg_fn = getattr(self, 'map_' + directive['function'], None)
            if not arg_fn:
                # TODO: log this? It's a misconfiguration
                continue
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

            elif data.get('audio') is not None and directive['trigger'] == 'frequency_all':
                if directive.get('bins'):
                    value = []
                    for bin_info in directive['bins']:
                        bucket = []
                        if isinstance(bin_info, list):
                            for idx in range(bin_info[0], bin_info[1] + 1):
                                bucket.append(data['audio'][idx])
                        else:
                            bucket.append([data['audio'][bin_info]])
                        value.append(bucket)
                else:
                    value = data['audio']
                threshold = directive.get('threshold', 0)

            elif data.get('is_onset') and directive['trigger'] == 'onset':
                value = random.random() / 1.5
                threshold = 0

            elif data.get('is_beat') and directive['trigger'] == 'beat':
                value = random.random() / 1.5
                threshold = 0

            elif data.get('pitch') and directive['trigger'] == 'pitch':
                value = data['pitch']
                threshold = directive.get('threshold', 0)

            if value is None or threshold is None:
                continue

            arg = arg_fn(directive['trigger'], value, threshold)

            if arg is not None:
                if self.last_function[directive['function']] + self.RATES.get(directive['function'], 0) < now:
                    self.last_function[directive['function']] = now
                    if directive['function'] in self.MULTI_PROP_MAP:
                        new_state.update(dict(zip(self.MULTI_PROP_MAP[directive['function']], arg)))
                    else:
                        new_state[directive['function']] = arg

        if new_state:
            # Not dead anymore
            if '__all__' in self.CLEAR_EFFECTS_ON_NEW_STATE:
                self.effects = {}
            else:
                for k in self.CLEAR_EFFECTS_ON_NEW_STATE:
                    if k in self.effects:
                        del self.effects[k]
            for k in self.RESET_ON_NEW_STATE:
                v = self.INITIALIZE.get(k, 0)
                if self.auto_state[k] != v:
                    self.auto_state[k] = v
                self.send_dmx(data, True)

            self.auto_state.update(new_state)

    def prep_dmx(self):
        # If this light is not suspended, copy the auto state to the real state
        if self.name not in self.config.get('SUSPENDED', []):
            self.state.update(self.auto_state)
        out = dict(self.state)
        changed = {}
        for k, v in out.items():
            if v != self.last_state[k]:
                changed[k] = v
        if changed:
            # print(changed)
            send_monitor(self, 'STATE', **changed)

        for k in self.INVERT:
            out[k] = 255 - out[k]
        return out

    def send_dmx(self, data, force=False):
        if self.config.get('ENABLE_LINKS'):
            # Update linked state prior to prep
            for linked in self.output_config.get('LINK') or []:
                # Prevent an infinite loop
                if linked.get('NAME') is None or linked.get('NAME') == self.output_config['NAME']:
                    # TODO: log
                    continue
                # Only push the auto state
                linked_state = dict(self.auto_state)
                for fn in linked.get('INVERT') or []:
                    linked_state[fn] = 255 - linked_state[fn]
                data['push_state__' + linked.get('NAME')] = linked_state

        state = self.prep_dmx()
        channels = {self.FUNCTIONS[chan] + self.output_config.get('ADDRESS', 1) - 1: val for chan, val in state.items()}
        data.setdefault('dmx_force' if force else 'dmx', {}).update(channels)
        self.last_auto_state = dict(self.auto_state)
        self.last_state = dict(self.state)
