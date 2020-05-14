#!/usr/bin/env python3

import argparse
import logging

from app import NoData
from app.lib.config import parse_config
from app.lib.network import Network, NetworkTask
from app.inputs import DeviceInput
from app.processors import SmoothingProcessor, BeatProcessor, PitchProcessor, IdleProcessor
from app.outputs.dmxfixtures.gobo import UKingGobo, UnnamedGobo
from app.outputs.dmxfixtures.movinghead import TomshineMovingHead6in1
from app.outputs.dmxfixtures.laser import Generic4ColorLaser
from app.outputs.led import RemoteStrip
from app.outputs.gui import GUI
from app.outputs.dmx import DMX


logging.basicConfig(level=logging.DEBUG)


def parse_args():
    p = argparse.ArgumentParser(description="Audio reactive lights server")
    p.add_argument('-c', '--config', help="Configuration file")
    p.add_argument('-m', '--manual', help="Manual control")
    p.add_argument('-r', '--record', help="Record states to this file")
    p.add_argument('--monitor', action='store_true')
    return p.parse_args()


def run(args):
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
            DeviceInput('audioinput', config),
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

    network = Network(config, lights, monitor=args.monitor)
    tasks.insert(0, NetworkTask('netinput', config, network, 'input'))
    tasks.append(NetworkTask('netoutput', config, network, 'output'))

    try:
        try:
            data = {'network': network}
            for t in tasks:
                t.start(data)

            while True:
                data = {}
                for t in tasks:
                    try:
                        t.run(data)
                    except NoData:
                        break
        except KeyboardInterrupt:
            # Suppress
            pass
    finally:
        for t in tasks:
            t.stop()


if __name__ == '__main__':
    run(parse_args())