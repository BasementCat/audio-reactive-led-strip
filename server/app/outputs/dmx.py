import os
import glob
import logging
import threading
import time

from dmxpy.DmxPy import DmxPy

from app import Task
from app.lib.pubsub import subscribe
from app.lib.misc import FPSCounter


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


class DMX(Task):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if not self.config.get('DMX_DEVICE'):
            raise ValueError("No DMX_DEVICE in config")

        self.dmx = None
        self.dmx_lock = threading.Lock()
        self.dmx_attempt = None
        self.delay = 1.0 / float(self.config.get('FPS', 60))
        self.last_send = 0
        self.fps = FPSCounter('DMX')

        self.get_dmx()

        subscribe('dmx', self.handle)

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

    def handle(self, data):
        dmx = self.get_dmx()
        if dmx:
            for chan, val in data.items():
                dmx.setChannel(chan, val)

    def run(self):
        if time.time() - self.last_send >= self.delay:
            self.last_send = time.time()
            with self.fps:
                dmx = self.get_dmx()
                if dmx:
                    dmx.render()
