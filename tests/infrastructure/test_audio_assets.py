"""Numerical quality checks for the shipped original interface sounds and music."""
import array
import math
from pathlib import Path
import sys
import wave

import pytest


ASSETS = Path(__file__).resolve().parents[2] / 'assets' / 'audio'
INTERFACE_EFFECTS = (
    'nav', 'confirm', 'cancel', 'purchase', 'open_pack', 'reward', 'error', 'travel',
)


def read_pcm(path):
    with wave.open(str(path), 'rb') as sound:
        parameters = sound.getparams()
        samples = array.array('h', sound.readframes(sound.getnframes()))
    if sys.byteorder != 'little':
        samples.byteswap()
    return parameters, samples


@pytest.mark.parametrize('name', INTERFACE_EFFECTS)
def test_interface_effects_have_soft_transients_and_three_distinct_variants(name):
    recordings = []
    for variant in range(3):
        parameters, samples = read_pcm(ASSETS / f'{name}_{variant}.wav')
        assert (parameters.framerate, parameters.sampwidth, parameters.nchannels) == (44100, 2, 1)
        assert 0.05 <= parameters.nframes / parameters.framerate <= 0.8
        assert samples[0] == samples[-1] == 0
        assert 0.025 < max(abs(sample) for sample in samples) / 32767 <= 0.25
        assert max(abs(b - a) for a, b in zip(samples, samples[1:])) / 32767 < 0.15
        recordings.append(samples.tobytes())
    assert len(set(recordings)) == 3


def test_theme_is_a_complete_stereo_composition_with_headroom_and_no_loop_click():
    parameters, samples = read_pcm(ASSETS / 'last_wish_theme.wav')
    assert (parameters.framerate, parameters.sampwidth, parameters.nchannels) == (44100, 2, 2)
    assert 35 <= parameters.nframes / parameters.framerate <= 60
    left, right = samples[0::2], samples[1::2]
    assert left != right
    for channel in (left, right):
        assert 0.1 < max(abs(sample) for sample in channel) / 32767 <= 0.55
        rms = math.sqrt(sum(sample * sample for sample in channel) / len(channel)) / 32767
        assert 0.04 < rms < 0.18
        assert abs(sum(channel) / len(channel)) / 32767 < 0.001
        # Music crosses the seam while playing; matching silence would hide a gap.
        assert abs(channel[-1] - channel[0]) / 32767 < 0.005
        seam_window = channel[-441:] + channel[:441]
        assert max(abs(sample) for sample in seam_window) > 100
        # Compare the boundary slope with the immediately adjacent samples.
        # A legitimate pluck several milliseconds later can have a faster slope.
        edge_steps = (channel[-1] - channel[-2], channel[0] - channel[-1],
                      channel[1] - channel[0])
        assert max(abs(b - a) for a, b in zip(edge_steps, edge_steps[1:])) / 32767 < 0.001
    # A loop contains an evolving arrangement, not one short tone duplicated.
    second = parameters.framerate * parameters.nchannels
    assert len({samples[offset:offset + second].tobytes()
                for offset in range(0, len(samples) - second, second)}) >= 30

