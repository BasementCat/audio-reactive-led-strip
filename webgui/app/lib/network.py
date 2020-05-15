import re
import logging
import socket
import select
import json
import time
import threading
import queue

from .tasks import Thread


logger = logging.getLogger(__name__)


class Client(queue.Queue):
    def __init__(self, id, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.id = id
        self.last_seen = time.time()

    def ping(self):
        self.last_seen = time.time()

    @property
    def age(self):
        return time.time() - self.last_seen
    


class NetworkThread(Thread):
    def setup(self):
        self.sock = None
        self.buf = ''
        self.lights = []
        self.lock = threading.Lock()
        self.client_queues = {}
        self.connect()

    def send_to_server(self, command, *args, **kwargs):
        if not self.sock:
            return
        data = json.dumps({'command': command, 'args': args, 'kwargs': kwargs}).encode('utf-8') + b'\n'
        with self.lock:
            sent = 0
            while sent < len(data):
                sent += self.sock.send(data[sent:])

    def send_to_client(self, command, *args, **kwargs):
        remove = []
        for client in self.client_queues.values():
            if client.age > 3:
                remove.append(client.id)
            else:
                client.put({'command': command, 'args': args, 'kwargs': kwargs})
        for id in remove:
            del self.client_queues[id]

    def get_for_client(self, client_id, timeout=1):
        out = []
        if client_id in self.client_queues:
            client = self.client_queues[client_id]
        else:
            client = self.client_queues[client_id] = Client(client_id)
            client.put({'command': 'LIGHTS', 'args': self.lights, 'kwargs': {}})

        client.ping()
        try:
            out.append(client.get(timeout=timeout))
            while True:
                out.append(client.get(block=False))
        except queue.Empty:
            pass

        return out

    def get_lights(self):
        return self.lights

    def connect(self):
        if self.sock:
            self.sock.close()
            self.sock = None
        self.buf = ''

        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # TODO: configurable
            self.sock.connect(('localhost', 37737))
            return True
        except:
            logger.error("Failed to connect to %s:%d", host, port, exc_info=True)
            self.sock = None
            return False

    def loop(self):
        if not self.sock:
            if not self.connect():
                time.sleep(1)
                return

        # # Send pending commands to the server
        # for command in self.to_server_queue:
        #     sent = 0
        #     while sent < len(command):
        #         sent += self.sock.send(command[sent:])
        # self.to_server_queue = []

        # Read the socket to get commands from the server, add to the buffer
        read_ready, _, _ = select.select([self.sock], [], [], 1)
        if read_ready:
            data = self.sock.recv(8192)
            if len(data) == 0:
                self.sock.close()
                self.sock = None
                self.send_to_client('QUIT')
                return

            data = data.decode('utf-8')
            self.buf += data

        # Parse the buffer into commands
        lines = re.split(r'[\r\n]+', self.buf)
        if re.match(r'[\r\n]+$', self.buf):
            lines.pop()
            self.buf = ''
        else:
            self.buf = lines.pop()

        for line in lines:
            line = line.strip()
            if not line:
                continue

            line = json.loads(line)
            command = line.pop('command')
            # print(f"emit {command} {line}")
            self.send_to_client(command, *line.get('args', []), **line.get('kwargs', {}))

            if command == 'LIGHTS':
                self.lights = line['args']

            if command == 'QUIT':
                self.sock.close()
                self.sock = None


# def network_on_connect(sio):
#     if lights:
#         sio.emit('LIGHTS', {'args': lights, 'kwargs': {}})
