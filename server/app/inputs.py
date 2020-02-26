import time
import sys
import socket
import logging
import select
import re

import numpy as np
import pyaudio

from app import Task
from app.lib.misc import FPSCounter


logger = logging.getLogger(__name__)


class Input(Task):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fps = FPSCounter("Audio input: " + self.name)
        self.frames_per_buffer = int(self.config['MIC_RATE'] / self.config['FPS'])


class DeviceInput(Input):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.p = pyaudio.PyAudio()
        valid_input_devices = {}

        for i in range(self.p.get_device_count()):
            info = self.p.get_device_info_by_index(i)
            if info.get('maxInputChannels') > 0:
                valid_input_devices[i] = info.get('name')

        device_num = None
        try:
            device = int(self.config.get('INPUT_DEVICE'))
            device_num = device if device in valid_input_devices else None
        except (TypeError, ValueError):
            device = self.config.get('INPUT_DEVICE')
            for k, v in valid_input_devices.items():
                if device in v:
                    device_num = k
                    break

        if not device_num:
            print(f"Invalid device {device} - valid devices are:")
            for k in sorted(valid_input_devices.keys()):
                print(f"{k}: {valid_input_devices[k]}")
            sys.exit(1)

        self.stream = self.p.open(format=pyaudio.paInt16,
                        channels=1,
                        rate=self.config['MIC_RATE'],
                        input=True,
                        frames_per_buffer=self.frames_per_buffer,
                        input_device_index=device_num
                        )
        self.overflows = 0
        self.prev_ovf_time = time.time()

    def run(self, data):
        with self.fps:
            try:
                y = np.fromstring(self.stream.read(self.frames_per_buffer, exception_on_overflow=False), dtype=np.int16)
                y = y.astype(np.float32)
                self.stream.read(self.stream.get_read_available(), exception_on_overflow=False)
                data['raw_audio'] = y
            except IOError:
                self.overflows += 1
                if time.time() > self.prev_ovf_time + 1:
                    self.prev_ovf_time = time.time()
                    print('Audio buffer has overflowed {} times'.format(self.overflows))

    def stop(self):
        self.stream.stop_stream()
        self.stream.close()
        self.p.terminate()


# _write_queue = []
# def sendmonitor(output, op, opstate=None, **data):
#     out = op
#     if opstate:
#         out += ':' + opstate

#     if output:
#         out += f' {output.__class__.__name__}:{output.name}'

#     if data:
#         out += ' :'
#         for k, v in data.items():
#             out += ' ' + k + '=' + str(v)

#     _write_queue.append(out.encode('utf-8'))


class NetworkInput(Task):
    def __init__(self, config, *args, lights=None, **kwargs):
        super().__init__(config, *args, **kwargs)
        self.lights = lights or []
        host = self.config.get('NETWORK_INPUT_HOST', '0.0.0.0')
        port = self.config.get('NETWORK_INPUT_PORT', 37736)

        self.clients = []

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setblocking(0)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((host, port))
        self.sock.listen(5)

        self.queue = {}

        logger.info("Network input listening on %s:%d", host, port)

    def run(self, data):
        r, _, _ = select.select([self.sock] + self.clients, [], [], 0)
        for s in r:
            if s is self.sock:
                newsock, addr = self.sock.accept()
                logger.info("Network input has new connection from %s", addr)
                self.clients.append(newsock)

                for l in self.lights:
                    newsock.send(f'LIGHT {l.__class__.__name__} {l.name}\n'.encode('utf-8'))
                # TODO: send whether suspended
            else:
                # Read and discard data
                data = s.recv(8192)
                if len(data) == 0:
                    # No data, client is dead
                    s.close()
                    self.clients.remove(s)
                else:
                    key = s.getpeername()
                    self.queue.setdefault(key, '')
                    self.queue[key] += data.decode('utf-8')
                    commands = re.split(r'[\r\n]+', self.queue[key])
                    if re.match(r'[\r\n]+$', self.queue[key]):
                        # Everything is a command, last element is empty
                        commands.pop()
                        self.queue[key] = ''
                    else:
                        # The last element is not full
                        self.queue[key] = commands.pop()

                    for c in commands:
                        c = c.strip()
                        if not c:
                            continue
                        args = c.split()
                        command = args.pop(0)
                        try:
                            getattr(self, '_command_' + command.lower())(s, *args)
                        except AttributeError:
                            s.send(b'ERROR badcommand ' + command.encode('utf-8') + b' Invalid Command\n')

        # for c in self.clients:
        #     for line in _write_queue:
        #         c.send(line + b'\n')
        # _write_queue[:] = []

    def _command_echo(self, s, *args):
        s.send(b' '.join(map(lambda v: v.encode('utf-8'), args)) + b'\n')

    def _command_suspend(self, s, *args):
        state = True
        if args:
            try:
                state = bool(int(args[0]))
            except:
                s.send(b'ERROR badarg ' + args[0].encode('utf-8') + b' Bad argument\n')
                return
        self.config['SUSPENDED'] = state
        s.send(b'OK\n')

    def _command_unsuspend(self, s, *args):
        self._command_suspend(s, 0)

    def _command_state(self, s, *names):
        lights = list(filter(lambda v: v.name in names, self.lights)) if names else self.lights
        for l in lights:
            if not hasattr(l, 'state'):
                if names:
                    s.send(b'ERROR badarg ' + l.name.encode('utf-8') + b' Light has no state\n')
                continue
            s.send(b'STATE ' + l.name.encode('utf-8'))
            for k, v in l.state.items():
                s.send(b' ' + k.encode('utf-8') + b'=' + str(v).encode('utf-8'))
            s.send(b'\n')

    def _command_blackout(self, s, *names):
        lights = list(filter(lambda v: v.name in names, self.lights)) if names else self.lights
        for l in lights:
            if not hasattr(l, 'state'):
                if names:
                    s.send(b'ERROR badarg ' + l.name.encode('utf-8') + b' Light has no state\n')
                continue

            if hasattr(l, 'FUNCTIONS'):
                l.state = {k: 0 for k in l.FUNCTIONS.keys()}

            if hasattr(l, 'INITIALIZE'):
                l.state.update(l.INITIALIZE)

        s.send(b'OK\n')

    def _command_set(self, s, *args):
        names = []
        props = {}
        for item in args:
            if '=' in item:
                k, v = item.split('=', 1)
                try:
                    v = int(v)
                except:
                    s.send(b'ERROR badarg ' + item.encode('utf-8') + b' Value is not an integer\n')
                    return
                props[k] = v
            else:
                names.append(item)

        lights = list(filter(lambda v: v.name in names, self.lights)) if names else self.lights
        for l in lights:
            if not hasattr(l, 'state'):
                if names:
                    s.send(b'ERROR badarg ' + l.name.encode('utf-8') + b' Light has no state\n')
                continue

            l.state.update(props)

        s.send(b'OK\n')

    def stop(self):
        for c in self.clients:
            c.send(b'QUIT\n')
            c.close()
        self.sock.close()
