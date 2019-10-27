# import time
# import signal

from app.lib.config import parse_config
from app.inputs import DeviceInput
from app.processors import SmoothingProcessor, BeatProcessor, IdleProcessor
from app.outputs.gobo import UKingGobo, UnnamedGobo
from app.outputs.led import RemoteStrip
from app.outputs.gui import GUI
from app.outputs.dmx import DMX


config = parse_config()
tasks = [
    DeviceInput('audioinput', config),
    SmoothingProcessor('smoothing', config),
    BeatProcessor('beat', config),
    IdleProcessor('idle', config),
]
for output in config['OUTPUTS']:
    tasks.append(globals()[output['DEVICE']](config, output))
if config['USE_GUI']:
    tasks.append(GUI('gui', config))
# Add DMX last so it gets called last
if config.get('DMX_DEVICE'):
    tasks.append(DMX('dmx', config))

try:
    try:
        data = {}
        for t in tasks:
            t.start(data)

        while True:
            data = {}
            for t in tasks:
                t.run(data)
    except KeyboardInterrupt:
        # Suppress
        pass
finally:
    for t in tasks:
        t.stop()
