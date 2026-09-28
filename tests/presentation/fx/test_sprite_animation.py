"""Time-based sprite animation: frame selection, looping, one-shot hold, offsets."""
import pytest

from src.presentation.fx.sprite_animation import SpriteAnimation


def _anim(**kw):
    return SpriteAnimation(["a", "b", "c"], [0.1, 0.2, 0.3], **kw)


class TestSpriteAnimation:
    def test_starts_on_first_frame(self):
        assert _anim().frame == "a"

    def test_frame_follows_durations(self):
        anim = _anim()
        anim.update(0.15)
        assert anim.frame == "b"

    def test_loops_after_total(self):
        anim = _anim()
        anim.update(0.65)
        assert anim.frame == "a"

    def test_huge_time_still_valid(self):
        anim = _anim()
        anim.update(10 ** 12 + 0.05)
        assert anim.frame in ("a", "b", "c")

    def test_one_shot_holds_last_frame(self):
        anim = _anim(loop=False)
        anim.update(5.0)
        assert (anim.frame, anim.finished) == ("c", True)

    def test_start_offset(self):
        assert _anim(start=0.35).frame == "c"

    def test_negative_dt_ignored(self):
        anim = _anim()
        anim.update(-1.0)
        assert anim.frame == "a"

    def test_mismatched_lengths_rejected(self):
        with pytest.raises(ValueError):
            SpriteAnimation(["a"], [0.1, 0.2])

    def test_empty_rejected(self):
        with pytest.raises(ValueError):
            SpriteAnimation([], [])
