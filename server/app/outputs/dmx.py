import os
import glob
import logging
import threading
import queue
import time

from dmxpy.DmxPy import DmxPy

from app.lib.threads import Thread


logger = logging.getLogger(__name__)


def find_device_file(name):
    # Name is either a path (/dev/ttyUSB0) which might change, or a device ID (0403:6001) which does not
    if name.startswith('/') or ':' not in name:
        # Assume file
        return name

    if ':' not in name:
        raise ValueError(f"Not a valid device ID: {name}")

    hexint = lambda v: int(v, 16)
    vendor, product = map(hexint, name.split(':'))

    for dev in glob.glob('/sys/bus/usb-serial/devices/*'):
        devname = os.path.basename(dev)
        with open(os.path.join(dev, '../uevent'), 'r') as fp:
            for line in fp:
                line = line.strip()
                if line and '=' in line:
                    param, value = line.split('=')
                    if param == 'PRODUCT':
                        testvendor, testproduct = map(hexint, value.split('/')[:2])
                        if testvendor == vendor and testproduct == product:
                            return os.path.join('/dev', devname)

    raise RuntimeError(f"Can't find USB device {name}")


class DMXThread(Thread):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if not self.config.get('DMX_DEVICE'):
            raise ValueError("No DMX_DEVICE in config")

        self.unrestrict_queue(4)

        self.dmx = None
        self.dmx_lock = threading.Lock()
        self.dmx_attempt = None

        self.get_dmx()

    def get_dmx(self):
        if not self.dmx and self.config.get('DMX_DEVICE') != 'sink':
            if self.dmx_attempt is None or time.time() - self.dmx_attempt > 1:
                self.dmx_attempt = time.time()
                if not self.config.get('DMX_DEVICE'):
                    if self.config.get('DMX_DEVICE') is None:
                        logger.error("No DMX device configured")
                        self.config['DMX_DEVICE'] = False
                    return

                with self.dmx_lock:
                    try:
                        self.dmx = DmxPy(find_device_file(self.config['DMX_DEVICE']))
                    except:
                        logger.error("Can't open DMX device %s", self.config['DMX_DEVICE'], exc_info=True)

        return self.dmx

    def run(self):
        # TODO: configurable? Use from config, already have fps
        delay = 1.0 / float(self.config.get('FPS', 60))
        last_send = 0
        while not self.stop_event.is_set():
            try:
                fn, args, kwargs = self.queue.get(timeout=delay)
            except queue.Empty:
                pass
            else:
                dmx = self.get_dmx()
                if dmx:
                    if fn == 'set_channels':
                        for chan, value in args[0].items():
                            dmx.setChannel(chan, value)
            if dmx and time.time() - last_send >= delay:
                # print(dmx.dmxData)
                # print("render dmx")
                dmx.render()
                last_send = time.time()
