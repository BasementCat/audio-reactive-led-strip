import socket
import select
import logging
import json
import re


logger = logging.getLogger(__name__)


monitor_queue = []
def send_monitor(output, op, opstate=None, opname=None, **state):
    monitor_queue.append({
        'type': output.__class__.__name__ if output else None,
        'name': output.name if output else None,
        'op': op,
        'op_state': opstate,
        'op_name': opname,
        'state': state
    })


class Network(object):
    def __init__(self, config, lights=None, monitor=False):
        self.config = config
        self.lights = lights or []
        self.monitor = monitor

        host = self.config.get('NETWORK_HOST', '0.0.0.0')
        port = self.config.get('NETWORK_PORT', 37737)

        self.clients = []

        self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_sock.setblocking(0)
        self.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_sock.bind((host, port))
        self.server_sock.listen(5)

        self.input_queue = {}

        logger.info("Network listening on %s:%d", host, port)

    def start(self, data):
        pass

    def stop(self):
        if self.clients:
            for c in self.clients:
                self.send_command(c, 'QUIT')
                c.close()
            self.clients = []
        if self.server_sock:
            self.server_sock.close()
            self.server_sock = None

    def send_command(self, sock, command, *args, **kwargs):
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
            self.clients.remove(sock)

    def send_error(self, sock, errcode, errarg, errstr):
        self.send_command(sock, 'ERROR', code=errcode, argument=errarg, error=errstr)

    def run_input(self, data):
        r, _, _ = select.select([self.server_sock] + self.clients, [], [], 0)
        for s in r:
            if s is self.server_sock:
                newsock, addr = self.server_sock.accept()
                logger.info("Network input has new connection from %s", addr)
                self.clients.append(newsock)

                if self.config.get('SUSPENDED'):
                    if len(self.config['SUSPENDED']) == len(self.lights):
                        suspended_state = True
                    else:
                        suspended_state = self.config['SUSPENDED']
                else:
                    suspended_state = False

                self.send_command(newsock, 'LIGHTS', *[
                    {
                        'type': l.__class__.__name__,
                        'name': l.name,
                        'functions': list(getattr(l, 'FUNCTIONS', {}).keys()),
                        'state': getattr(l, 'state', {}),
                        'speeds': getattr(l, 'SPEEDS', {}),
                        'enums': getattr(l, 'ENUMS', {}),
                    }
                    for l in self.lights
                ], suspended=data.get('SUSPENDED', suspended_state))
            else:
                data = b''
                try:
                    data = s.recv(8192)
                except ConnectionResetError:
                    pass
                if len(data) == 0:
                    # No data, client is dead
                    s.close()
                    self.clients.remove(s)
                else:
                    key = s.getpeername()
                    self.input_queue.setdefault(key, '')
                    self.input_queue[key] += data.decode('utf-8')
                    commands = re.split(r'[\r\n]+', self.input_queue[key])
                    if re.match(r'[\r\n]+$', self.input_queue[key]):
                        # Everything is a command, last element is empty
                        commands.pop()
                        self.input_queue[key] = ''
                    else:
                        # The last element is not full
                        self.input_queue[key] = commands.pop()

                    for c in commands:
                        c = c.strip()
                        if not c:
                            continue

                        try:
                            c = json.loads(c)
                        except:
                            logger.error("Failed to parse JSON command", exc_info=True)
                            continue

                        try:
                            fn = getattr(self, '_command_' + c['command'].lower())
                        except KeyError:
                            self.send_error(s, 'nocommand', None, "No command was specified")
                        except AttributeError:
                            self.send_error(s, 'badcommand', c['command'], "Invalid command")
                        else:
                            try:
                                fn(s, *c.get('args', []), **c.get('kwargs', {}))
                            except Exception as e:
                                self.send_error(s, 'general', e.__class__.__name__, str(e))

    def run_output(self, data):
        # TODO: only send to monitoring clients
        if self.monitor:
            for v in monitor_queue:
                # TODO: allow filtering
                if v.get('op') == 'AUDIO':
                    continue
                print('MONITOR', v)
        if monitor_queue:
            for c in self.clients:
                self.send_command(c, 'MONITOR', *monitor_queue)
            monitor_queue[:] = []

    def _command_echo(self, s, *args, **kwargs):
        self.send_command(s, 'echo_response', *args, **kwargs)

    def _command_suspend(self, s, *names, **kwargs):
        state = kwargs.get('state', True)
        lights = list(filter(lambda v: v.name in names, self.lights)) if names else self.lights
        if not names:
            self.config['SUSPENDED'] = [l.name for l in lights] if state else []
        else:
            if state:
                self.config['SUSPENDED'] = list(set(self.config.get('SUSPENDED', [])) | set([l.name for l in lights]))
            else:
                self.config['SUSPENDED'] = list(set(self.config.get('SUSPENDED', [])) - set([l.name for l in lights]))

        send_monitor(None, 'SUSPENDED', state if not names else self.config['SUSPENDED'])
        self.send_command(s, 'OK')

    def _command_unsuspend(self, s, *names, **kwargs):
        kwargs = dict(kwargs, state=False)
        self._command_suspend(s, *names, **kwargs)

    def _command_state(self, s, *names, **kwargs):
        lights = list(filter(lambda v: v.name in names, self.lights)) if names else self.lights
        states = []
        for l in lights:
            if not hasattr(l, 'state'):
                if names:
                    states.append({'light': l.name, 'state': None})
                continue
            states.append({'light': l.name, 'state': l.state})
        self.send_command(s, 'STATE', *states)

    def _command_blackout(self, s, *names, **kwargs):
        lights = list(filter(lambda v: v.name in names, self.lights)) if names else self.lights
        out = []
        for l in lights:
            if not hasattr(l, 'state'):
                if names:
                    out.append({'light': l.name, 'result': None})
                continue

            if hasattr(l, 'FUNCTIONS'):
                l.state = {k: 0 for k in l.FUNCTIONS.keys()}

            if hasattr(l, 'INITIALIZE'):
                l.state.update(l.INITIALIZE)

            out.append({'light': l.name, 'result': True})

        self.send_command(s, 'OK', *out)

    def _command_set(self, s, *names, **props):
        relative = props.pop('_relative', False)
        lights = list(filter(lambda v: v.name in names, self.lights)) if names else self.lights
        out = []
        for l in lights:
            if not hasattr(l, 'state'):
                if names:
                    out.append({'light': l.name, 'result': None})
                continue

            if relative:
                # add the value in props to the current state
                for k, v in props.items():
                    if k in l.state:
                        props[k] = min(255, max(0, l.state[k] + v))

            # TODO: per light/type, define what props must be sent immediately
            if 'speed' in props or 'dim' in props:
                l.state.update({
                    'speed': props.get('speed', l.state['speed']),
                    'dim': props.get('dim', l.state['dim']),
                })
                l.send_dmx({}, force=True)

            l.state.update(props)
            out.append({'light': l.name, 'result': True})

        self.send_command(s, 'OK', *out)


class NetworkTask(object):
    def __init__(self, name, config, network, position, *args, **kwargs):
        self.name = name
        self.config = config
        self.network = network
        self.position = position

    def start(self, data):
        self.network.start(data)

    def stop(self):
        self.network.stop()

    def run(self, data):
        getattr(self.network, 'run_' + self.position)(data)
