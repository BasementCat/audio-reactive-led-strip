import time
import signal

from app.lib.config import parse_config
from app.lib.threads import start_threads, stop_threads, wait_threads, get_main_thread_callbacks, stop_event
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

# Install the signal handler before starting threads
# If we get the signal before starting, the threads will immediately exit
def _signal_handler(signo, frame):
    stop_threads()
signal.signal(signal.SIGINT, _signal_handler)
signal.signal(signal.SIGTERM, _signal_handler)

start_threads()
while not stop_event.is_set():
    if main_thread_callbacks:
        # Assume the callbacks will take some time/delay/etc
        # TODO: maybe let callbacks define when they'll run next so we can still delay
        for cb in main_thread_callbacks:
            cb()
    else:
        time.sleep(0.25)

wait_threads()