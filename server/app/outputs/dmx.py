import os
import glob
import logging
import threading
import time
import subprocess
import re

from dmxpy.DmxPy import DmxPy

from app import Task
from app.lib.misc import FPSCounter


logger = logging.getLogger(__name__)
hexint = lambda v: int(v, 16)


def find_device_file__linux(vendor, product):
    if not os.path.exists('/sys') or not os.path.isdir('/sys'):
        return None
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


def find_device_file__macos(vendor, product):
    devices = []
    curdevice = {}

    res = subprocess.check_output(['ioreg', '-p', 'IOUSB', '-l', '-b']).decode('utf-8')
    for line in res.split('\n'):
        line = line.strip()
        if not line:
            continue

        match = re.match(u'^\+-o (.+)\s+<', line)
        if match:
            if curdevice:
                devices.append(curdevice)
                curdevice = {}
            continue

        match = re.match(u'^[\|\s]*"([\w\d\s]+)"\s+=\s+(.+)$', line)
        if match:
            k, v = match.groups()
            if v.startswith('"'):
                v = v[1:-1]
            else:
                try:
                    v = int(v)
                except:
                    pass
            curdevice[k] = v

    if curdevice:
        devices.append(curdevice)

    for d in devices:
        if d.get('idVendor') == vendor and d.get('idProduct') == product:
            return '/dev/tty.usbserial-' + d['USB Serial Number']


def find_device_file(name):
    # Name is either a path (/dev/ttyUSB0) which might change, or a device ID (0403:6001) which does not
    if name.startswith('/') or ':' not in name:
        # Assume file
        return name

    if ':' not in name:
        raise ValueError(f"Not a valid device ID: {name}")

    vendor, product = map(hexint, name.split(':'))

    for fn in (find_device_file__linux, find_device_file__macos):
        try:
            file = fn(vendor, product)
            if file:
                return file
        except:
            logger.debug("Failure in find device file", exc_info=True)

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

    def run(self, data):
        dmx = self.get_dmx()
        if dmx:
            if data.get('dmx_force'):
                with self.fps:
                    for chan, val in data['dmx_force'].items():
                        dmx.setChannel(chan, val)
                    dmx.render()
            if data.get('dmx'):
                for chan, val in data['dmx'].items():
                    dmx.setChannel(chan, val)
            if time.time() - self.last_send >= self.delay:
                self.last_send = time.time()
                with self.fps:
                    dmx.render()
