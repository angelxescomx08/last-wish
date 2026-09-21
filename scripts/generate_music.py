"""Original 16-bar chamber-fantasy loop: 'Embers of the Last Wish'.

84 BPM, D minor, 4/4, 45.714 seconds; synthesized lyre, breathy reed,
soft string harmony, bass, hand drum and brushes. Notes and room tails wrap
around the exact loop duration, so the final bar resolves into the first
without a gap or an abrupt reverb cutoff. No third-party samples are used.

Run directly, or rebuild all sounds with python scripts/generate_audio.py.
"""
from __future__ import annotations

import array
import math
from pathlib import Path
import random

from generate_audio import RATE, ROOT, write_wav

BPM = 84
BEAT = 60 / BPM
BARS = 16
FRAMES = round(BARS * 4 * BEAT * RATE)
DURATION = FRAMES / RATE
# Voicings travel between minor/add9 and open major chords, resolving A to D.
CHORDS = (
    (50, 57, 65, 64), (46, 53, 57, 62), (48, 53, 57, 67), (48, 55, 62, 64),
    (43, 50, 58, 62), (46, 53, 58, 62), (45, 52, 57, 60), (45, 52, 55, 62),
    (50, 57, 65, 64), (46, 53, 57, 62), (48, 53, 57, 67), (48, 55, 62, 64),
    (43, 50, 58, 62), (46, 53, 58, 62), (45, 52, 57, 60), (45, 52, 55, 61),
)
BASS = (38, 34, 41, 36, 31, 34, 33, 33) * 2
# Each tuple is (beat within bar, MIDI note, length in beats). Space between
# phrases lets UI feedback remain clear; the second eight bars answer the first.
MELODY = (
    ((0.5, 69, 0.75), (1.5, 65, 0.75), (2.5, 64, 0.5), (3.25, 62, 0.6)),
    ((0.5, 65, 0.75), (1.5, 69, 1.1), (3.0, 74, 0.7)),
    ((0.25, 72, 1.0), (1.75, 69, 0.75), (2.75, 67, 0.9)),
    ((0.5, 64, 1.5), (2.5, 62, 0.7)),
    ((0.5, 67, 0.75), (1.5, 70, 0.75), (2.5, 74, 1.0)),
    ((0.25, 72, 0.75), (1.25, 70, 0.75), (2.25, 69, 1.2)),
    ((0.5, 67, 0.65), (1.5, 64, 0.75), (2.5, 60, 0.75)),
    ((0.5, 62, 0.75), (1.75, 64, 1.25)),
    ((0.25, 62, 0.5), (1.0, 65, 0.5), (1.75, 69, 1.0), (3.0, 74, 0.65)),
    ((0.5, 72, 0.75), (1.5, 69, 0.5), (2.25, 65, 1.2)),
    ((0.5, 69, 0.75), (1.5, 67, 0.75), (2.5, 65, 1.0)),
    ((0.5, 64, 1.0), (2.0, 67, 0.6), (3.0, 64, 0.6)),
    ((0.5, 70, 0.65), (1.5, 69, 0.65), (2.5, 67, 1.0)),
    ((0.5, 65, 0.7), (1.5, 62, 0.7), (2.5, 65, 0.7)),
    ((0.25, 64, 0.7), (1.25, 69, 0.7), (2.25, 72, 1.0)),
    ((0.5, 73, 0.75), (1.75, 69, 0.8), (3.0, 64, 0.6)),
)


def note_envelope(t, duration, attack, release):
    rise = math.sin(min(1.0, t / attack) * math.pi / 2) ** 2
    fall = math.sin(min(1.0, (duration - t) / release) * math.pi / 2) ** 2
    return rise * fall


def tone(instrument, frequency, duration, seed):
    """Generate a bounded, smooth voice with an instrument-specific spectrum."""
    rng = random.Random(seed)
    noise = 0.0
    for index in range(round(duration * RATE)):
        t = index / RATE
        phase = math.tau * frequency * t
        if instrument == 'lyre':
            spectrum = (math.sin(phase) * math.exp(-2.7 * t)
                        + 0.33 * math.sin(phase * 2) * math.exp(-6 * t)
                        + 0.14 * math.sin(phase * 3) * math.exp(-9 * t)
                        + 0.05 * math.sin(phase * 4) * math.exp(-14 * t))
            value = spectrum * note_envelope(t, duration, 0.008, 0.16)
        elif instrument == 'reed':
            vibrato = 0.12 * (1 - math.cos(math.tau * 4.7 * t)) * min(1.0, t / 0.3)
            noise += 0.13 * (rng.uniform(-1, 1) - noise)
            spectrum = (math.sin(phase + vibrato) + 0.12 * math.sin(phase * 2)
                        + 0.055 * math.sin(phase * 3) + 0.035 * noise)
            value = spectrum * note_envelope(t, duration, 0.09, 0.2)
        elif instrument == 'strings':
            spectrum = (math.sin(phase) + 0.32 * math.sin(phase + math.tau * 0.19 * t)
                        + 0.11 * math.sin(phase * 2) + 0.025 * math.sin(phase * 3))
            value = spectrum * note_envelope(t, duration, 0.7, 1.0)
        elif instrument == 'bass':
            spectrum = math.sin(phase) + 0.15 * math.sin(phase * 2)
            value = spectrum * math.exp(-1.05 * t) * note_envelope(t, duration, 0.035, 0.35)
        elif instrument == 'drum':
            # Integrated downward pitch bend makes a rounded skin impact.
            phase = math.tau * (55 * t + 1.65 * (1 - math.exp(-25 * t)))
            noise += 0.055 * (rng.uniform(-1, 1) - noise)
            value = (math.sin(phase) * math.exp(-17 * t) + noise * math.exp(-30 * t))
            value *= note_envelope(t, duration, 0.006, 0.07)
        else:
            noise += 0.16 * (rng.uniform(-1, 1) - noise)
            value = noise * math.sin(math.pi * t / duration) ** 2
        yield value


def add_voice(channels, start, midi, duration, gain, pan, instrument, seed):
    frequency = 440 * 2 ** ((midi - 69) / 12)
    left_gain = gain * math.cos((pan + 1) * math.pi / 4)
    right_gain = gain * math.sin((pan + 1) * math.pi / 4)
    start_frame = round(start * RATE)
    left, right = channels
    for offset, sample in enumerate(tone(instrument, frequency, duration, seed)):
        frame = (start_frame + offset) % FRAMES
        left[frame] += sample * left_gain
        right[frame] += sample * right_gain


def arrange_bar(channels, bar):
    rng = random.Random(f'embers:bar:{bar}')
    start = bar * 4 * BEAT
    chord = CHORDS[bar]
    for index, note in enumerate(chord):
        add_voice(channels, start - 0.12, note, 4 * BEAT + 1.3,
                  0.026, (index - 1.5) * 0.36, 'strings', f'pad:{bar}:{index}')
    add_voice(channels, start, BASS[bar], 3.4 * BEAT, 0.16, 0, 'bass', f'bass:{bar}')
    for step in range(8):
        note = chord[(0, 2, 1, 3, 2, 1, 3, 1)[step]] + (12 if step in (3, 6) else 0)
        add_voice(channels, start + step * 0.5 * BEAT + rng.uniform(-0.01, 0.01),
                  note, 1.45, 0.075 * rng.uniform(0.86, 1.06),
                  -0.32 if step % 2 == 0 else 0.3, 'lyre', f'lyre:{bar}:{step}')
    for index, (beat, note, length) in enumerate(MELODY[bar]):
        add_voice(channels, start + beat * BEAT, note, length * BEAT,
                  0.071 if bar < 8 else 0.076, 0.06, 'reed', f'melody:{bar}:{index}')
    for beat, gain in ((0, 0.072), (2.5, 0.043)):
        add_voice(channels, start + beat * BEAT, 36, 0.28, gain, -0.06, 'drum', f'drum:{bar}:{beat}')
    for beat in (0.5, 1.5, 2.5, 3.5):
        add_voice(channels, start + beat * BEAT, 60, 0.11,
                  0.041 if beat in (1.5, 3.5) else 0.026,
                  0.4, 'brush', f'brush:{bar}:{beat}')


def add_room(channels):
    """Circular taps retain room energy at the loop boundary on both channels."""
    left, right = channels
    dry_left, dry_right = array.array('f', left), array.array('f', right)
    # Diffuse early reflections and quiet musical echoes, all from the dry mix.
    for seconds, level, crossfeed in ((0.071, 0.11, True), (0.137, 0.08, False),
                                     (BEAT * 0.75, 0.17, True), (BEAT * 1.5, 0.08, False)):
        shift = round(seconds * RATE)
        source_left, source_right = (dry_right, dry_left) if crossfeed else (dry_left, dry_right)
        for frame in range(FRAMES):
            source = (frame - shift) % FRAMES
            left[frame] += source_left[source] * level
            right[frame] += source_right[source] * level


def master(channels):
    """Remove DC and leave generous headroom; retain the musical dynamics."""
    means = tuple(sum(channel) / FRAMES for channel in channels)
    peak = max(max(abs(sample - mean) for sample in channel)
               for channel, mean in zip(channels, means))
    scale = 0.48 / peak
    stereo = array.array('f')
    for left, right in zip(*channels):
        stereo.append((left - means[0]) * scale)
        stereo.append((right - means[1]) * scale)
    return stereo


def write_theme(destination: Path):
    channels = (array.array('f', [0.0]) * FRAMES, array.array('f', [0.0]) * FRAMES)
    for bar in range(BARS):
        arrange_bar(channels, bar)
        if bar % 4 == 3:
            print(f'Music: arranged {bar + 1}/{BARS} bars', flush=True)
    add_room(channels)
    stereo = master(channels)
    write_wav(destination / 'last_wish_theme.wav', stereo, channels=2)
    preview_duration = 16
    preview = array.array('f', stereo[:RATE * preview_duration * 2])
    for frame in range(RATE * preview_duration):
        gain = note_envelope(frame / RATE, preview_duration, 0.3, 1.6)
        preview[frame * 2] *= gain
        preview[frame * 2 + 1] *= gain
    write_wav(destination / 'music_preview.wav', preview, channels=2)
    rms = math.sqrt(sum(sample * sample for sample in stereo) / len(stereo))
    print(f'Embers of the Last Wish: {DURATION:.3f}s, {BPM} BPM, D minor, stereo, '
          f'peak -6.4 dBFS, RMS {20 * math.log10(rms):.1f} dBFS', flush=True)


if __name__ == '__main__':
    destination = ROOT / 'assets' / 'audio'
    destination.mkdir(parents=True, exist_ok=True)
    write_theme(destination)
