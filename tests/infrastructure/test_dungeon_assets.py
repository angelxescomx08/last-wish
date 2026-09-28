"""Dungeon asset pack: files present, metadata complete, surfaces pre-scaled once."""
import json

from src.infrastructure.dungeon_assets import DUNGEON_DIR, META_PATH, load_dungeon_assets


def _meta():
    return json.loads(META_PATH.read_text(encoding="utf-8"))


class TestFiles:
    def test_every_referenced_image_exists(self):
        meta = _meta()
        names = [meta["room"]["image"], meta["flame"]["image"], meta["glow"]["image"],
                 meta["tiles"]["image"], meta["props"]["image"]]
        assert all((DUNGEON_DIR / n).is_file() for n in names)

    def test_room_has_anchor_points(self):
        room = _meta()["room"]
        assert {"torches", "window_interior", "sill_y", "moonbeam", "drips", "floor_y"} <= set(room)

    def test_particle_palettes_present(self):
        assert {"rain", "splash", "ember", "dust", "drip"} <= set(_meta()["palette"])


class TestLoading:
    def test_room_is_prescaled_to_the_virtual_canvas(self):
        assert load_dungeon_assets().room.get_size() == (1280, 720)

    def test_flame_frames_match_metadata(self):
        assets = load_dungeon_assets()
        assert len(assets.flame_frames) == len(assets.flame_durations) == _meta()["flame"]["frames"]

    def test_glow_has_three_flicker_levels(self):
        assert len(load_dungeon_assets().glow_frames) == 3

    def test_pack_is_loaded_once(self):
        assert load_dungeon_assets() is load_dungeon_assets()
