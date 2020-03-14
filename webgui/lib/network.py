import re
import logging
import socket
import select
import json


logger = logging.getLogger(__name__)

lights = []


def network_on_connect(sio):
    if lights:
        sio.emit('LIGHTS', {'args': lights, 'kwargs': {}})


def network_task(sio, stop_event, host='localhost', port=37737):
    sock = None
    buf = ''

    while not stop_event.is_set():
        if sock is None:
            lights[:] = []
            buf = ''
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.connect((host, port))
            except:
                logger.error("Failed to connect to %s:%d", host, port, exc_info=True)
                sock = None
                sio.sleep(1)
                continue

        r, _, _ = select.select([sock], [], [])
        if r:
            data = sock.recv(8192)
            if len(data) == 0:
                sock.close()
                sock = None
                sio.emit('QUIT', {}, broadcast=True)
                continue

            data = data.decode('utf-8')
            buf += data

        lines = re.split(r'[\r\n]+', buf)
        if re.match(r'[\r\n]+$', buf):
            lines.pop()
            buf = ''
        else:
            buf = lines.pop()

        for l in lines:
            l = l.strip()
            if not l:
                continue

            l = json.loads(l)
            c = l.pop('command')
            # print(f"emit {c} {l}")
            sio.emit(c, l, broadcast=True)

            if c == 'LIGHTS':
                lights[:] = l['args']

            if c == 'QUIT':
                sock.close()
                sock = None

        sio.sleep(0.05)
