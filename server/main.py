#!/usr/bin/env python3

import argparse
import logging
import multiprocessing
import time
import signal
import os

from app import NoData
from app.lib.config import parse_config
from app.lib.network import Network, NetworkTask
from app.inputs import PyAudioDeviceInput, AlsaDeviceInput
from app.processors import SmoothingProcessor, BeatProcessor, PitchProcessor, IdleProcessor
from app.outputs.dmxfixtures.gobo import UKingGobo, UnnamedGobo
from app.outputs.dmxfixtures.movinghead import TomshineMovingHead6in1
from app.outputs.dmxfixtures.laser import Generic4ColorLaser
from app.outputs.led import RemoteStrip
from app.outputs.gui import GUI
from app.outputs.dmx import DMX


logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger()
last_signal = None


def parse_args():
    p = argparse.ArgumentParser(description="Audio reactive lights server")
    p.add_argument('-c', '--config', help="Configuration file")
    p.add_argument('-m', '--manual', help="Manual control")
    p.add_argument('-r', '--record', help="Record states to this file")
    p.add_argument('-M', '--monitor', action='store_true', help="Print monitor data (except audio) to the console")
    p.add_argument('-f', '--filter', action='append', help="Filter the monitor data")
    p.add_argument('-w', '--watchdog', nargs='?', type=float, default=0, help="Watchdog - if the process hangs for this many seconds, restart it")
    return p.parse_args()


def install_sighandler():
    def _sig_handler(signo, frame):
        global last_signal
        last_signal = signo
    signal.signal(signal.SIGINT, _sig_handler)
    signal.signal(signal.SIGTERM, _sig_handler)


def run(args, watchdog=None):
    config = parse_config(filename=args.config)
    lights = []
    config['ENABLE_LINKS'] = True
    if args.manual:
        config['ENABLE_LINKS'] = False
        if args.record:
            config['RECORD'] = args.record
        if args.manual == 'launchpad':
            from app.manualcontrol.novationlaunchpad import LaunchpadInput
            tasks = [LaunchpadInput('manual/launchpad', config)]
        else:
            raise ValueError(f"Invalid manual control: {args.manual}")
    else:
        tasks = [
            globals()[config.get('INPUT_TYPE', 'Alsa') + 'DeviceInput']('audioinput', config),
            SmoothingProcessor('smoothing', config),
            BeatProcessor('beat', config),
            PitchProcessor('pitch', config),
            IdleProcessor('idle', config),
        ]
    for output in config['OUTPUTS']:
        light = globals()[output['DEVICE']](config, output)
        lights.append(light)
        tasks.append(light)
        if args.manual:
            tasks[0].add_output(tasks[-1])
    if config['USE_GUI'] and not args.manual:
        tasks.append(GUI('gui', config))
    # Add DMX last so it gets called last
    if config.get('DMX_DEVICE'):
        tasks.append(DMX('dmx', config))

    network = Network(config, lights, monitor=args.monitor, monitor_filter=args.filter)
    tasks.insert(0, NetworkTask('netinput', config, network, 'input'))
    tasks.append(NetworkTask('netoutput', config, network, 'output'))

    try:
        install_sighandler()
        data = {'network': network}
        for t in tasks:
            t.start(data)

        while last_signal is None:
            data = {}
            for t in tasks:
                try:
                    t.run(data)
                except NoData:
                    break

            if watchdog:
                watchdog.value = time.time()

        logger.info("Exiting with signal %d", last_signal)
    finally:
        for t in tasks:
            t.stop()


def run_watchdog(args):
    watchdog = multiprocessing.Value('d', time.time() + 1)
    pid = os.fork()
    if pid == 0:
        run(args, watchdog=watchdog)
    else:
        install_sighandler()
        while last_signal is None:
            if time.time() - watchdog.value >= args.watchdog:
                logger.error("Child is not responding, killing")
                os.kill(pid, signal.SIGKILL)
                return True

            res = os.waitid(os.P_PID, pid, os.WEXITED | os.WNOHANG)
            if res is not None:
                if res.si_code !=0:
                    logger.error("Child exited with code %d, restarting", res.si_code)
                    return True

        logger.info("Killing child with signal %d", last_signal)
        os.kill(pid, last_signal)
        s = time.time()
        while time.time() - s < 1:
            res = os.waitid(os.P_PID, pid, os.WEXITED | os.WNOHANG)
            if res is not None:
                break
        if res is None:
            logger.error("Killing child")
            os.kill(pid, signal.SIGKILL)


if __name__ == '__main__':
    args = parse_args()
    if args.watchdog:
        logger.info("Starting up with watchdog timer %fs", args.watchdog)
        while run_watchdog(args):
            pass
    else:
        logger.info("Starting up with no watchdog timer")
        run(args)