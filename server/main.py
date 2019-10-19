from app.lib.config import parse_config
from app.lib.threads import start_threads, wait_threads, get_main_thread_callbacks
from app.inputs import DeviceInputThread
from app.processors import SmoothingProcessorThread
from app.outputs.dmx import DMXThread
from app.outputs.gui import GUIThread
from app.outputs.gobo import UKingGoboThread, UnnamedGoboThread
from app.outputs.led import RemoteStripThread


config = parse_config()
DeviceInputThread('input', config)
SmoothingProcessorThread('smoothing', config)
# TESTING
from app.processors import BeatProcessorThread
BeatProcessorThread('beat', config)

if config.get('DMX_DEVICE'):
    DMXThread('dmx', config)
for output in config['OUTPUTS']:
    globals()[output['DEVICE'] + 'Thread'](config, output)
# RemoteStripThread('remote', config)
# if config['USE_GUI']:
#     GUIThread('gui', config)
main_thread_callbacks = list(get_main_thread_callbacks())
start_threads()
try:
    while True:
        for cb in main_thread_callbacks:
            cb()
except KeyboardInterrupt:
    wait_threads()