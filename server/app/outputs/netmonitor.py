# import os
# import glob
import logging
# import threading
# import time
# import subprocess
# import re
import socket
import select

# from dmxpy.DmxPy import DmxPy

from app import Task
# from app.lib.misc import FPSCounter


logger = logging.getLogger(__name__)


_write_queue = []
def sendmonitor(output, op, opstate=None, **data):
    out = op
    if opstate:
        out += ':' + opstate

    if output:
        out += f' {output.__class__.__name__}:{output.name}'

    if data:
        out += ' :'
        for k, v in data.items():
            out += ' ' + k + '=' + str(v)

    _write_queue.append(out.encode('utf-8'))


class NetworkMonitor(Task):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        host = self.config.get('NETWORK_MONITOR_HOST', '0.0.0.0')
        port = self.config.get('NETWORK_MONITOR_PORT', 37737)

        self.clients = []

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setblocking(0)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((host, port))
        self.sock.listen(5)

        logger.info("Network monitor listening on %s:%d", host, port)

    def run(self, data):
        r, _, _ = select.select([self.sock] + self.clients, [], [], 0)
        for s in r:
            if s is self.sock:
                newsock, addr = self.sock.accept()
                logger.info("Network monitor has new connection from %s", addr)
                self.clients.append(newsock)
            else:
                # Read and discard data
                data = b''
                try:
                    data = s.recv(8192)
                except ConnectionResetError:
                    pass
                if len(data) == 0:
                    # No data, client is dead
                    s.close()
                    self.clients.remove(s)

        for c in self.clients:
            for line in _write_queue:
                c.send(line + b'\n')
        _write_queue[:] = []

    def stop(self):
        for c in self.clients:
            c.send(b'QUIT\n')
            c.close()
        self.sock.close()
