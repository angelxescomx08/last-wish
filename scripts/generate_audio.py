"""Rebuild Last Wish's original effects and music without external dependencies.

Run: python scripts/generate_audio.py
Every sound is synthesized locally; no recordings or third-party samples.
"""
from __future__ import annotations

import array
import math
from pathlib import Path
import random
import sys
import wave

RATE = 44100
ROOT = Path(__file__).resolve().parents[1]
# Duration and peak amplitude; frequent interactions sit below combat/rewards.
EFFECTS = {
    'card': (0.16, 0.10),
    'attack': (0.25, 0.19),
    'block': (0.29, 0.15),
    'death': (0.52, 0.16),
    'end_turn': (0.24, 0.10),
    'hit': (0.23, 0.18),
    'win': (0.76, 0.18),
    'nav': (0.07, 0.055),
    'confirm': (0.25, 0.085),
    'cancel': (0.19, 0.07),
    'purchase': (0.42, 0.13),
    'open_pack': (0.54, 0.14),
    'reward': (0.66, 0.15),
    'error': (0.23, 0.08),
    'travel': (0.46, 0.10),
}
NOISE_CUTOFFS = {
    'card': 1400, 'attack': 1050, 'block': 850, 'death': 550,
    'end_turn': 700, 'hit': 600, 'win': 1100, 'nav': 700,
    'confirm': 900, 'cancel': 1100, 'purchase': 1250,
    'open_pack': 1600, 'reward': 1050, 'error': 500, 'travel': 800,
}


def envelope(t: float, duration: float, attack: float = 0.008) -> float:
    if t <= 0 or t >= duration:
        return 0.0
    rise = math.sin(min(1.0, t / attack) * math.pi / 2) ** 2
    fall = math.sin(min(1.0, (duration - t) / 0.035) * math.pi / 2) ** 2
    return rise * fall


def resonance(t: float, frequency: float, decay: float) -> float:
    """Short wood/leather body, with softened inharmonic upper modes."""
    if t < 0:
        return 0.0
    return sum(weight * math.sin(math.tau * frequency * ratio * t)
               * math.exp(-t * decay * (1 + mode * 0.7))
               for mode, (ratio, weight) in enumerate(((1, 1), (2.41, 0.18), (3.87, 0.035))))


def pluck(t: float, frequency: float, duration: float = 0.42) -> float:
    """Consonant short strings for confirmations and positive outcomes."""
    if t <= 0 or t >= duration:
        return 0.0
    value = sum(weight * math.sin(math.tau * frequency * harmonic * t)
                * math.exp(-t * (8 + harmonic * 3))
                for harmonic, weight in ((1, 1), (2, 0.20), (3, 0.065)))
    return value * envelope(t, duration, 0.01)


def tap(t: float, frequency: float, duration: float = 0.13) -> float:
    return resonance(t, frequency, 34) * envelope(t, duration, 0.004)


def card(t, duration, noise, pitch):
    brush = noise * math.sin(math.pi * t / duration) ** 2
    return brush + 0.19 * tap(t, 195 * pitch) + 0.1 * tap(t - 0.057, 270 * pitch, 0.1)


def attack(t, duration, noise, pitch):
    brush = noise * 0.68 * math.exp(-((t - 0.06) / 0.037) ** 2)
    impact = resonance(t - 0.075, 112 * pitch, 23) * envelope(t - 0.075, 0.17)
    return brush + 0.62 * impact


def block(t, duration, noise, pitch):
    body = resonance(t, 245 * pitch, 18)
    glint = 0.13 * resonance(t - 0.012, 510 * pitch, 26)
    return 0.6 * body + glint + 0.21 * noise * math.exp(-35 * t)


def death(t, duration, noise, pitch):
    breath = noise * math.sin(math.pi * t / duration) ** 1.5 * math.exp(-3 * t)
    return breath + 0.20 * resonance(t, 79 * pitch, 12)


def end_turn(t, duration, noise, pitch):
    return tap(t, 220 * pitch) + 0.68 * tap(t - 0.09, 310 * pitch)


def hit(t, duration, noise, pitch):
    return 0.75 * resonance(t, 92 * pitch, 28) + 0.50 * noise * math.exp(-26 * t)


def win(t, duration, noise, pitch):
    notes = ((0, 293.66), (0.095, 349.23), (0.19, 440.0), (0.29, 587.33))
    return sum(0.85 ** index * pluck(t - delay, frequency * pitch, 0.46)
               for index, (delay, frequency) in enumerate(notes))


def nav(t, duration, noise, pitch):
    return 0.6 * tap(t, 255 * pitch, duration) + noise * 0.15 * math.exp(-55 * t)


def confirm(t, duration, noise, pitch):
    return pluck(t, 261.63 * pitch, 0.24) + 0.55 * pluck(t - 0.055, 392 * pitch, 0.19)


def cancel(t, duration, noise, pitch):
    return noise * math.sin(math.pi * t / duration) ** 2 + 0.17 * tap(t, 180 * pitch)


def purchase(t, duration, noise, pitch):
    coins = sum(0.7 ** index * resonance(t - delay, frequency * pitch, 22)
                * envelope(t - delay, duration - delay, 0.006)
                for index, (delay, frequency) in enumerate(((0, 420), (0.062, 560), (0.14, 630))))
    return coins + 0.22 * noise * math.exp(-15 * t)


def open_pack(t, duration, noise, pitch):
    tear = sum(math.exp(-((t - center) / 0.028) ** 2) for center in (0.065, 0.13, 0.205, 0.25))
    return 0.8 * noise * tear + 0.24 * pluck(t - 0.27, 392 * pitch, 0.26)


def reward(t, duration, noise, pitch):
    return sum(0.8 ** index * pluck(t - index * 0.105, frequency * pitch)
               for index, frequency in enumerate((293.66, 349.23, 440)))


def error(t, duration, noise, pitch):
    return tap(t, 155 * pitch) + 0.58 * tap(t - 0.085, 140 * pitch) + noise * 0.08 * math.exp(-18 * t)


def travel(t, duration, noise, pitch):
    footsteps = 0.42 * tap(t, 140 * pitch) + 0.3 * tap(t - 0.19, 170 * pitch)
    air = 0.7 * noise * math.sin(math.pi * t / duration) ** 2
    return footsteps + air


GENERATORS = {
    'card': card, 'attack': attack, 'block': block, 'death': death,
    'end_turn': end_turn, 'hit': hit, 'win': win, 'nav': nav,
    'confirm': confirm, 'cancel': cancel, 'purchase': purchase,
    'open_pack': open_pack, 'reward': reward, 'error': error, 'travel': travel,
}


def synthesize(name: str, variant: int) -> list[float]:
    duration, peak = EFFECTS[name]
    rng = random.Random(f'last-wish:felt-wood:{name}:{variant}')
    pitch = (0.965, 1.0, 1.035)[variant]
    count = round(duration * RATE)
    alpha = 1 - math.exp(-math.tau * NOISE_CUTOFFS[name] / RATE)
    filtered = smoothed = 0.0
    samples = []
    generate = GENERATORS[name]
    for i in range(count):
        t = i / RATE
        filtered += alpha * (rng.uniform(-1, 1) - filtered)
        smoothed += alpha * (filtered - smoothed)
        samples.append(generate(t, duration, smoothed * 3, pitch) * envelope(t, duration))
    mean = sum(samples) / count
    samples = [(sample - mean) * envelope(i / RATE, duration)
               for i, sample in enumerate(samples)]
    scale = peak / max(abs(sample) for sample in samples)
    samples = [sample * scale for sample in samples]
    samples[0] = samples[-1] = 0.0
    return samples


def write_wav(path: Path, samples, channels: int = 1) -> None:
    pcm = array.array('h', (round(max(-1.0, min(1.0, sample)) * 32767) for sample in samples))
    if sys.byteorder != 'little':
        pcm.byteswap()
    with wave.open(str(path), 'wb') as output:
        output.setparams((channels, 2, RATE, 0, 'NONE', 'not compressed'))
        output.writeframes(pcm.tobytes())


def main() -> None:
    destination = ROOT / 'assets' / 'audio'
    destination.mkdir(parents=True, exist_ok=True)
    preview = [0.0] * round(RATE * 0.3)
    for name in EFFECTS:
        for variant in range(3):
            samples = synthesize(name, variant)
            write_wav(destination / f'{name}_{variant}.wav', samples)
            if variant == 0:
                preview.extend(sample * 0.8 for sample in samples)
                preview.extend([0.0] * round(RATE * 0.35))
        print(f'{name}: 3 variants, {EFFECTS[name][0]:.2f}s, peak {20 * math.log10(EFFECTS[name][1]):.1f} dBFS', flush=True)
    write_wav(destination / 'preview.wav', preview)
    from generate_music import write_theme
    write_theme(destination)


if __name__ == '__main__':
    main()
