import json
import argparse
import time
import socket
import select
import logging
import queue

from py_dream_cheeky.button import DreamCheekyButtonThread, ButtonEventType


logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger()


def run_effects(sock, effects):
    for e in effects:
        if 'suspend' in e:
            send_command(sock, 'SUSPEND', *e['lights'], state=e['suspend'])
            # print("Suspending", e['lights'], e['suspend'])
        if 'props' in e:
            if e.get('duration'):
                send_command(sock, 'EFFECT', *e['lights'], **{
                    prop: {'start': 'current', 'end': value, 'duration': e['duration'], 'overwrite': True}
                    for prop, value in e['props'].items()
                })
                # print("Set effect for props current ->", e['props'], e['duration'], "on lights", e['lights'])
            else:
                send_command(sock, 'SET', *e['lights'], **e['props'])
                # print("Set state", e['props'], "on lights", e['lights'])
        if e.get('wait') and e.get('duration'):
            time.sleep(e['duration'])


def load_config():
    with open('config.json', 'r') as fp:
        return json.load(fp)


def connect(config):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((config['HOST'], config['PORT']))
        sock.setblocking(0)
        return sock
    except:
        logger.error("Failed to connect to %s:%d", config['HOST'], config['PORT'], exc_info=True)
        return None


def sock_read(sock):
    r, _, _ = select.select([sock], [], [], 0.01)
    data = b''
    if r:
        try:
            data = sock.recv(8192)
        except ConnectionResetError:
            return False
        if len(data) == 0:
            # No data, client is dead
            sock.close()
            return False
    return data


def send_command(sock, command, *args, **kwargs):
    data = {
        'command': command,
        'args': args,
        'kwargs': kwargs
    }
    out = json.dumps(data).encode('utf-8') + b'\n'
    sent = 0
    try:
        while sent < len(out):
            sent += sock.send(out[sent:])
    except socket.error:
        logger.error("Got error from socket %s", sock, exc_info=True)
        sock.close()
        return False
    return True


def run(config, button):
    event_queue = button.get_event_queue()
    click_state = 0
    hold_state = 0
    sock = None

    while True:
        if sock is None:
            sock = connect(config)
            if sock is None:
                time.sleep(1)
                try:
                    while True:
                        event_queue.get(block=False)
                except queue.Empty:
                    pass
                continue

        res = sock_read(sock)
        if res is False or b'QUIT' in res:
            sock = None
            continue

        try:
            event = event_queue.get(timeout=0.01)
        except queue.Empty:
            continue

        if event.type == ButtonEventType.LID_OPEN:
            run_effects(sock, config['EFFECTS'].get('LID_OPEN', []))
        elif event.type == ButtonEventType.BUTTON_CLICK:
            hold_state = 0
            if config['EFFECTS'].get('BUTTON_CLICK'):
                run_effects(sock, config['EFFECTS']['BUTTON_CLICK'][click_state])
                click_state = (click_state + 1) % len(config['EFFECTS']['BUTTON_CLICK'])
        elif event.type == ButtonEventType.BUTTON_HOLD:
            click_state = 0
            if config['EFFECTS'].get('BUTTON_HOLD'):
                run_effects(sock, config['EFFECTS']['BUTTON_HOLD'][hold_state])
                hold_state = (hold_state + 1) % len(config['EFFECTS']['BUTTON_HOLD'])
        elif event.type == ButtonEventType.LID_CLOSE:
            run_effects(sock, config['EFFECTS'].get('LID_CLOSE', []))


def main():
    config = load_config()
    button = DreamCheekyButtonThread(enqueue_events=True)
    button.start()
    try:
        try:
            run(config, button)
        finally:
            button.stop()
    except KeyboardInterrupt:
        # suppress this
        pass


main()
