"""Audio quality, variation, playback limits and unavailable-device regressions."""
import array
import wave
from pathlib import Path
from unittest.mock import Mock

import pygame
import pytest

from src.infrastructure.audio import SoundPlayer

ASSETS = Path(__file__).resolve().parents[2] / 'assets' / 'audio'
EFFECTS = ('card', 'attack', 'block', 'death', 'end_turn', 'hit', 'win')


@pytest.fixture(autouse=True)
def stop_playback():
    if pygame.mixer.get_init():
        pygame.mixer.stop()
    yield
    if pygame.mixer.get_init():
        pygame.mixer.stop()


@pytest.mark.parametrize('name', EFFECTS)
def test_effects_are_quiet_click_free_and_varied(name):
    variants = []
    for variant in range(3):
        with wave.open(str(ASSETS / f'{name}_{variant}.wav'), 'rb') as sound:
            assert sound.getframerate() == 44100
            assert sound.getsampwidth() == 2
            assert sound.getnchannels() == 1
            assert 0.05 <= sound.getnframes() / sound.getframerate() <= 0.8
            samples = array.array('h', sound.readframes(sound.getnframes()))
        assert samples[0] == samples[-1] == 0
        assert 0 < max(abs(s) for s in samples) <= 32767 * 0.25
        assert max(abs(b - a) for a, b in zip(samples, samples[1:])) < 32767 * 0.15
        variants.append(samples.tobytes())
    assert len(set(variants)) == 3


@pytest.mark.parametrize('name', EFFECTS)
def test_play_methods_work(name):
    player = SoundPlayer()
    assert player._ok
    getattr(player, f'play_{name}')()


def test_no_audio_device_is_a_safe_no_op(monkeypatch):
    monkeypatch.setattr(pygame.mixer, 'get_init', lambda: None)
    monkeypatch.setattr(pygame.mixer, 'init', Mock(side_effect=pygame.error('no device')))
    player = SoundPlayer()
    for name in EFFECTS:
        getattr(player, f'play_{name}')()


def test_rapid_repeats_do_not_stack(monkeypatch):
    player = SoundPlayer()
    channel = Mock()
    monkeypatch.setattr(pygame.mixer, 'find_channel', lambda: channel)
    monkeypatch.setattr(pygame.time, 'get_ticks', lambda: 1000)
    player.play_attack()
    player.play_attack()
    assert channel.play.call_count == 1


def test_later_plays_use_different_variants(monkeypatch):
    player = SoundPlayer()
    channel = Mock()
    monkeypatch.setattr(pygame.mixer, 'find_channel', lambda: channel)
    ticks = iter((1000, 1200, 1400))
    monkeypatch.setattr(pygame.time, 'get_ticks', lambda: next(ticks))
    for _ in range(3):
        player.play_card()
    assert len({id(call.args[0]) for call in channel.play.call_args_list}) == 3


def test_full_mixer_does_not_interrupt_existing_audio(monkeypatch):
    player = SoundPlayer()
    monkeypatch.setattr(pygame.mixer, 'find_channel', lambda: None)
    player.play_card()


def test_missing_assets_are_a_safe_no_op(monkeypatch, tmp_path):
    import src.infrastructure.audio as audio
    monkeypatch.setattr(audio, '_ASSETS', tmp_path)
    player = SoundPlayer()
    for name in EFFECTS:
        getattr(player, f'play_{name}')()


def test_three_active_voices_prevent_more_overlap(monkeypatch):
    player = SoundPlayer()
    active_sound = Mock()
    active_sound.get_num_channels.return_value = 3
    player._sounds = {'card': [active_sound]}
    find_channel = Mock()
    monkeypatch.setattr(pygame.mixer, 'find_channel', find_channel)
    player.play_card()
    find_channel.assert_not_called()


def test_stopped_mixer_is_a_safe_no_op(monkeypatch):
    player = SoundPlayer()
    monkeypatch.setattr(pygame.mixer, 'get_init', lambda: None)
    for name in EFFECTS:
        getattr(player, f'play_{name}')()

def test_music_starts_once_and_loops(monkeypatch):
    import src.infrastructure.audio as audio
    player = SoundPlayer()
    load = Mock()
    play = Mock()
    monkeypatch.setattr(pygame.mixer.music, 'load', load)
    monkeypatch.setattr(pygame.mixer.music, 'play', play)
    player.start_music()
    player.start_music()
    load.assert_called_once_with(str(audio._ASSETS / 'last_wish_theme.wav'))
    play.assert_called_once_with(loops=-1, fade_ms=1200)


def test_independent_volumes_apply_immediately(monkeypatch):
    player = SoundPlayer()
    music_volume = Mock()
    monkeypatch.setattr(pygame.mixer.music, 'set_volume', music_volume)
    player.set_volumes(0.2, 0.6)
    assert player._sounds['card'][0].get_volume() == pytest.approx(0.2, abs=0.01)
    music_volume.assert_called_once_with(0.6)


def test_muted_effects_do_not_consume_channels(monkeypatch):
    player = SoundPlayer()
    player.set_volumes(0, 0.35)
    find = Mock()
    monkeypatch.setattr(pygame.mixer, 'find_channel', find)
    player.play_card()
    find.assert_not_called()


def test_music_failure_keeps_effects_working(monkeypatch):
    player = SoundPlayer()
    monkeypatch.setattr(pygame.mixer.music, 'load', Mock(side_effect=pygame.error('missing')))
    player.start_music()
    assert player._ok
    player.play_card()


def test_completion_cue_waits_for_busy_effects(monkeypatch):
    player = SoundPlayer()
    win = Mock()
    win.get_num_channels.return_value = 3
    player._sounds = {'win': [win]}
    channel = Mock()
    monkeypatch.setattr(pygame.mixer, 'find_channel', lambda: channel)
    monkeypatch.setattr(pygame.time, 'get_ticks', lambda: 1000)
    player.play_win()
    channel.play.assert_not_called()
    win.get_num_channels.return_value = 0
    player.update()
    player.update()
    channel.play.assert_called_once_with(win)
