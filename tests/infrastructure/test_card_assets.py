"""cards-v2 assets: layout, frames per rarity, pack art, provisional illustrations."""
from src.infrastructure.card_assets import (
    CARDS_DIR, PLACEHOLDER_ART, card_frame, card_illustration, card_layout, pack_art,
)


class TestLayout:
    def test_layout_covers_the_five_rarities(self):
        assert set(card_layout()["frames"]) == {"COMMON", "UNCOMMON", "RARE", "EPIC", "LEGENDARY"}

    def test_every_frame_file_exists(self):
        assert all((CARDS_DIR / f["file"]).is_file() for f in card_layout()["frames"].values())

    def test_every_pack_file_exists(self):
        assert all((CARDS_DIR / p).is_file() for p in card_layout()["packs"].values())

    def test_packs_cover_the_four_themes(self):
        assert set(card_layout()["packs"]) == {"acero", "escudo", "magia", "epico"}

    def test_art_window_is_inside_the_upper_half(self):
        art = card_layout()["frames"]["COMMON"]["art"]
        assert 0.0 < art["x0"] < art["x1"] < 1.0 and 0.1 < art["y0"] < art["y1"] < 0.6

    def test_zones_present(self):
        assert {"mana", "name", "text", "attack", "block"} <= set(card_layout()["zones"])


class TestSurfaces:
    def test_frame_scaled_to_requested_size(self):
        assert card_frame("RARE", 140, 194).get_size() == (140, 194)

    def test_unknown_rarity_has_no_frame(self):
        assert card_frame("MYTHIC", 140, 194) is None

    def test_frame_is_cached(self):
        assert card_frame("EPIC", 140, 194) is card_frame("EPIC", 140, 194)

    def test_pack_art_keeps_height(self):
        assert pack_art("acero", 150).get_height() == 150

    def test_pack_art_is_taller_than_wide(self):
        art = pack_art("magia", 150)
        assert art.get_width() < art.get_height()

    def test_unknown_pack_has_no_art(self):
        assert pack_art("oscuro", 150) is None

    def test_every_card_type_has_placeholder_art(self):
        assert all(card_illustration("sin_arte", t, 100, 70) is not None for t in PLACEHOLDER_ART)

    def test_placeholder_art_fits_the_window(self):
        art = card_illustration("sin_arte", "ATTACK", 100, 70)
        assert art.get_width() <= 100 and art.get_height() <= 70
