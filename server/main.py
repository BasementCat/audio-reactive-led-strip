# import time
# import signal

from app.lib.config import parse_config
# from app.lib.threads import start_threads, stop_threads, wait_threads, get_main_thread_callbacks, stop_event
from app.inputs import DeviceInput
from app.processors import SmoothingProcessor, BeatProcessor, IdleProcessor
from app.outputs.dmx import DMX
from app.outputs.gui import GUI
from app.outputs.gobo import UKingGobo, UnnamedGobo
from app.outputs.led import RemoteStrip


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
# main_thread_callbacks = list(get_main_thread_callbacks())

try:
    try:
        for t in tasks:
            t.start()

        while True:
            for t in tasks:
                t.run()
    except KeyboardInterrupt:
        # Suppress
        pass
finally:
    for t in tasks:
        t.stop()


# start_threads()
# while not stop_event.is_set():
#     if main_thread_callbacks:
#         # Assume the callbacks will take some time/delay/etc
#         # TODO: maybe let callbacks define when they'll run next so we can still delay
#         for cb in main_thread_callbacks:
#             cb()
#     else:
#         time.sleep(0.25)

# wait_threads()