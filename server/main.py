#!/usr/bin/env python3

import argparse

from app.lib.config import parse_config
from app.inputs import DeviceInput
from app.processors import SmoothingProcessor, BeatProcessor, IdleProcessor
from app.outputs.gobo import UKingGobo, UnnamedGobo
from app.outputs.led import RemoteStrip
from app.outputs.gui import GUI
from app.outputs.dmx import DMX


def parse_args():
    p = argparse.ArgumentParser(description="Audio reactive lights server")
    p.add_argument('-c', '--config', help="Configuration file")
    return p.parse_args()


def run(args):
    config = parse_config(filename=args.config)
    tasks = [
        DeviceInput('audioinput', config),
        SmoothingProcessor('smoothing', config),
        BeatProcessor('beat', config),
        IdleProcessor('idle', config),
    ]
    for output in config['OUTPUTS']:
        tasks.append(globals()[output['DEVICE']](config, output))
    if config['USE_GUI']:
        tasks.append(GUI('gui', config))
    # Add DMX last so it gets called last
    if config.get('DMX_DEVICE'):
        tasks.append(DMX('dmx', config))

    try:
        try:
            data = {}
            for t in tasks:
                t.start(data)

            while True:
                data = {}
                for t in tasks:
                    t.run(data)
        except KeyboardInterrupt:
            # Suppress
            pass
    finally:
        for t in tasks:
            t.stop()


if __name__ == '__main__':
    run(parse_args())