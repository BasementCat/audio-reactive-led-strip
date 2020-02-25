import os
import json

import yaml


BASE_CONFIG = {
    # Configured outputs, see below"""
    'OUTPUTS': [],

    # Whether or not to display a PyQtGraph GUI plot of visualization"""
    'USE_GUI': True,

    # Whether to display the FPS when running (can reduce performance)"""
    'DISPLAY_FPS': True,

    # Location of the gamma correction table"""
    'LED_GAMMA_TABLE_PATH': os.path.join(os.path.dirname(__file__), 'gamma_table.npy'),

    # Sampling frequency of the microphone in Hz"""
    'MIC_RATE': 44100,

    # Desired refresh rate of the visualization (frames per second)

    # FPS indicates the desired refresh rate, or frames-per-second, of the audio
    # visualization. The actual refresh rate may be lower if the computer cannot keep
    # up with desired FPS value.

    # Higher framerates improve "responsiveness" and reduce the latency of the
    # visualization but are more computationally expensive.

    # Low framerates are less computationally expensive, but the visualization may
    # appear "sluggish" or out of sync with the audio being played if it is too low.

    # The FPS should not exceed the maximum refresh rate of the LED strip, which
    # depends on how long the LED strip is.
    'FPS': 60,

    # Frequencies below this value will be removed during audio processing"""
    'MIN_FREQUENCY': 15,

    # Frequencies above this value will be removed during audio processing"""
    'MAX_FREQUENCY': 20000,

    # Number of frequency bins to use when transforming audio to frequency domain

    # Fast Fourier transforms are used to transform time-domain audio data to the
    # frequency domain. The frequencies present in the audio signal are assigned
    # to their respective frequency bins. This value indicates the number of
    # frequency bins to use.

    # A small number of bins reduces the frequency resolution of the visualization
    # but improves amplitude resolution. The opposite is true when using a large
    # number of bins. More bins is not always better!

    # There is no point using more bins than there are pixels on the LED strip.
    'N_FFT_BINS': 24,

    # Number of past audio frames to include in the rolling window"""
    'N_ROLLING_HISTORY': 2,

    # No music visualization displayed if recorded audio volume below threshold"""
    'MIN_VOLUME_THRESHOLD': 1e-7,
}


def parse_config(filename=None):
    """Parse a configuration from the given filename, or find an appropriate config file

    Most of the configuration settings are fine at their defaults.  The one configuration
    that is generally required is the OUTPUT list - it is a list of output dictionaries
    that specifies what devices to use.  Each output dictionary requires at minimum the
    NAME, DEVICE and N_PIXELS keys.  NAME is a unique name for the output, N_PIXELS is
    the number of pixels present, and DEVICE is one of:
    * remote_strip - A remote strip on the network running the ESP firmware.
    ** HOST - the hostname or IP address of the remote device (required)
    ** PORT - the port to send UDP data to (required)
    * local_strip - A strip connected directly to the computer running this code, usually a pi
    ** LED_PIN - GPIO pin connected to the LED strip pixels (must support PWM)
    ** LED_FREQ_HZ - LED signal frequency in Hz (usually 800kHz)
    ** LED_DMA - DMA channel used for generating PWM signal (try 5)
    ** BRIGHTNESS - Brightness of LED strip between 0 and 255
    ** LED_INVERT - Set True if using an inverting logic level converter
    * blinkstick - A blinkstick pro connected to the computer running this code

    If no outputs are present, the GUI can still be used but no LEDs are controlled
    """
    filename = filename or _find_config_file()
    config = dict(BASE_CONFIG)
    if filename:
        with open(filename, 'r') as fp:
            if filename.endswith('json'):
                config.update(json.load(fp))
            else:
                config.update(yaml.load(fp))
    config['OUTPUTS'] = list(map(_parse_output, config['OUTPUTS']))

    # Figure out the max FPS
    max_fps = min(list(map(lambda v: int(((v['N_PIXELS'] * 30e-6) + 50e-6)**-1.0), filter(lambda v: 'N_PIXELS' in v, config['OUTPUTS']))) or [config['FPS']])
    if config['FPS'] > max_fps:
        raise ValueError(f"FPS must be <= {max_fps}, is {config['FPS']}")

    return config


def _find_config_file():
    # TODO: support configs in multiple locations
    for f in ('./config.json', './config.yaml', './config.yml'):
        if os.path.exists(f):
            return f


def _parse_output(output):
    if not output.get('DEVICE'):
        raise ValueError("Missing DEVICE key in output")

    fn = globals().get('_parse_output__' + output['DEVICE'])
    if not fn:
        raise ValueError("Invalid DEVICE type: " + output['DEVICE'])

    return fn(output)


def _parse_output__RemoteStrip(output):
    required_keys = ('NAME', 'HOST', 'PORT', 'N_PIXELS')
    for key in required_keys:
        if not output.get(key):
            raise ValueError(f"Missing {key} config for device type {output['DEVICE']}")
    # The remote strip firmware handles gamma correction
    return dict(output, SOFTWARE_GAMMA_CORRECTION=False)


def _parse_output__LocalStrip(output):
    required_keys = ('NAME', 'N_PIXELS')
    default_config = {
        # GPIO pin connected to the LED strip pixels (must support PWM)
        'LED_PIN': 18,
        # LED signal frequency in Hz (usually 800kHz)
        'LED_FREQ_HZ': 800000,
        # DMA channel used for generating PWM signal (try 5)
        'LED_DMA': 5,
        # Brightness of LED strip between 0 and 255
        'BRIGHTNESS': 255,
        # Set True if using an inverting logic level converter
        'LED_INVERT': True,
    }
    config = dict(default_config, **output)
    # The local strip does not do hardware dithering
    config['SOFTWARE_GAMMA_CORRECTION'] = True
    return config


def _parse_output__Blinkstick(output):
    # The blinkstick does not do hardware dithering
    return dict(output, SOFTWARE_GAMMA_CORRECTION=True)


def _parse_output__UKingGobo(output):
    # required_keys = ('NAME')
    return output


def _parse_output__UnnamedGobo(output):
    # required_keys = ('NAME')
    return output
