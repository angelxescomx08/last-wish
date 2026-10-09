"""Game fonts: Pixel Operator (CC0) built into LastWish/LastWish8 + Tiny5 for long card names.

Covers the files and licences on disk, every Spanish letter and every UI symbol present in the
built fonts (``scripts/build_game_font.py``; rebuilt and compared; fontTools is a dev dependency, never skipped),
size snapping (whole multiples of the pixel grid, monotonic, huge sizes), hard-edged rendering
(no semi-transparent pixels, 32-bit alpha surface, background variant), font objects shared
between sizes, the system-font fallback without the files, Tiny5 for card names, and every
card name fitting its plate on the base card.
"""
from __future__ import annotations

import pygame
import pytest
from fontTools.ttLib import TTFont

from src.infrastructure import fonts as F
from src.infrastructure.fonts import FONT_8, FONT_16, FONT_DIR, FONT_TINY, FontRegistry, pixel_size

SPANISH = "áéíóúÁÉÍÓÚñÑüÜ¿¡"
SYMBOLS = "→←↑↓↔−▲✓≤≥≈⚙⛑"


class TestFiles:
    @pytest.mark.parametrize("name", [FONT_16, FONT_8, FONT_TINY, "LastWish-Bold.ttf", "LastWish8-Bold.ttf"])
    def test_present(self, name):
        assert (FONT_DIR / name).is_file()

    def test_licences(self):
        assert "CC0" in (FONT_DIR / "source" / "LICENSE.txt").read_text(encoding="utf-8")
        assert "Open Font License" in (FONT_DIR / "Tiny5-OFL.txt").read_text(encoding="utf-8")

    @pytest.mark.parametrize("name", [FONT_16, FONT_8, "LastWish-Bold.ttf", "LastWish8-Bold.ttf"])
    def test_every_letter_and_symbol(self, name):
        cmap = TTFont(str(FONT_DIR / name)).getBestCmap()
        assert all(ord(ch) in cmap for ch in SPANISH + SYMBOLS)

    def test_tiny_has_spanish(self):
        cmap = TTFont(str(FONT_DIR / FONT_TINY)).getBestCmap()
        assert all(ord(ch) in cmap for ch in SPANISH)

    def test_ui_symbols_covered(self):
        """Every non-ASCII character in the source is in the built font."""
        from pathlib import Path
        cmap = TTFont(str(FONT_DIR / FONT_16)).getBestCmap()
        root = Path(F.__file__).parent.parent
        used = {ch for p in root.rglob("*.py") for ch in p.read_text(encoding="utf-8") if ord(ch) > 126}
        missing = {ch for ch in used if ord(ch) not in cmap}
        assert missing == set()


class TestSnapping:
    @pytest.mark.parametrize("size", range(1, 120))
    def test_whole_grid(self, size):
        name, px = pixel_size(size)
        grid = 16 if name == FONT_16 else 8
        assert px % grid == 0 and px >= grid

    def test_cap_grows_with_size(self):
        cap = {FONT_16: 9 / 16, FONT_8: 7 / 8}
        caps = [pixel_size(s)[1] * cap[pixel_size(s)[0]] for s in range(1, 120)]
        assert caps == sorted(caps)

    @pytest.mark.parametrize("size,expected", [(8, (FONT_8, 8)), (11, (FONT_8, 8)), (12, (FONT_16, 16)),
                                               (17, (FONT_16, 16)), (18, (FONT_8, 16)), (24, (FONT_16, 32)),
                                               (31, (FONT_8, 24)), (40, (FONT_8, 32))])
    def test_boundaries(self, size, expected):
        assert pixel_size(size) == expected

    def test_huge(self):
        name, px = pixel_size(10 ** 6)
        assert name == FONT_8 and px % 8 == 0 and px > 10 ** 5


class TestRendering:
    def test_shared_objects(self):
        reg = FontRegistry()
        assert reg.get(12) is reg.get(16) and reg.get(12) is not reg.get(20)

    @pytest.mark.parametrize("size", [8, 13, 16, 20, 26, 34, 40, 72])
    def test_hard_edges(self, size):
        img = FontRegistry().get(size).render("Último: ¿Daño? → ñ", True, (255, 240, 200))
        assert img.get_flags() & pygame.SRCALPHA
        alphas = {img.get_at((x, y))[3] for y in range(img.get_height()) for x in range(img.get_width())}
        assert alphas <= {0, 255} and 255 in alphas

    def test_background_variant(self):
        img = FontRegistry().get(16).render("Hola", False, (255, 255, 255), (0, 0, 0))
        assert img.get_width() > 0

    def test_cap_heights(self):
        reg = FontRegistry()
        assert reg.get(16).render("A", False, (255, 255, 255)).get_bounding_rect().height == 9
        assert reg.get(20).render("A", False, (255, 255, 255)).get_bounding_rect().height == 14

    def test_fallback_without_files(self, tmp_path):
        reg = FontRegistry(font_dir=tmp_path)
        assert not reg.pixel and reg.get(14).size("Hola")[0] > 0
        assert reg.tiny(8).size("Hola")[0] > 0

    def test_tiny(self):
        reg = FontRegistry()
        tiny = reg.tiny(8)
        assert tiny.size("Abanico de Cuchillas")[0] < reg.get(8).size("Abanico de Cuchillas")[0]
        assert reg.tiny(9) is tiny and reg.tiny(16) is not tiny

    def test_every_card_name_fits_its_plate(self):
        from src.domain.card import CardClass
        from src.domain.card_pool import card_factories_for_classes
        from src.infrastructure.card_assets import card_layout
        from src.presentation.ui import card_widget as cw
        reg = FontRegistry()
        plate = cw._rect(card_layout()["zones"]["name"], cw.CARD_W, cw.CARD_H)
        names = {f().name for f in card_factories_for_classes(set(CardClass))}
        assert all(min(reg.bold(8).size(n)[0], reg.tiny(8).size(n)[0]) <= plate.w - 4 for n in names)

    def test_bold_is_thicker_same_grid(self):
        reg = FontRegistry()
        regular = reg.get(10).render("Inflige", False, (255, 255, 255))
        bold = reg.bold(10).render("Inflige", False, (255, 255, 255))

        def ink(s):
            return sum(s.get_at((x, y))[3] > 0 for y in range(s.get_height()) for x in range(s.get_width()))
        assert ink(bold) > ink(regular) * 1.3
        assert bold.get_height() == regular.get_height()

    @pytest.mark.parametrize("size", [1, 8, 11, 12, 17, 18, 24, 31, 40, 10 ** 4])
    def test_bold_snaps_like_regular(self, size):
        reg = FontRegistry()
        assert reg.bold(size).get_linesize() == reg.get(size).get_linesize()

    def test_bold_shared_and_hard(self):
        reg = FontRegistry()
        assert reg.bold(12) is reg.bold(16)
        img = reg.bold(20).render("Daño ¡ñ!", True, (255, 255, 255))
        assert {img.get_at((x, y))[3] for y in range(img.get_height()) for x in range(img.get_width())} <= {0, 255}

    def test_bold_fallback(self, tmp_path):
        assert FontRegistry(font_dir=tmp_path).bold(14).size("Hola")[0] > 0


class TestBuildScript:
    def test_rebuild_matches_assets(self, tmp_path, monkeypatch):
        import importlib.util
        from pathlib import Path
        script = Path(F.__file__).resolve().parents[2] / "scripts" / "build_game_font.py"
        spec = importlib.util.spec_from_file_location("build_game_font", script)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        (tmp_path / "source").mkdir()
        for name in ("PixelOperator.ttf", "PixelOperator8.ttf", "PixelOperator-Bold.ttf",
                     "PixelOperator8-Bold.ttf"):
            (tmp_path / "source" / name).write_bytes((FONT_DIR / "source" / name).read_bytes())
        monkeypatch.setattr(mod, "FONTS", tmp_path)
        mod.main()
        for name in (FONT_16, FONT_8, "LastWish-Bold.ttf", "LastWish8-Bold.ttf"):
            built, shipped = TTFont(str(tmp_path / name)), TTFont(str(FONT_DIR / name))
            assert built.getBestCmap() == shipped.getBestCmap()


# ---------------------------------------------------------------------------
# Original FontRegistry tests (lazy loading and cache by requested size) — still valid
# ---------------------------------------------------------------------------

class TestFontRegistryConstruction:
    def test_creates_without_error(self):
        assert FontRegistry() is not None

    def test_cache_starts_empty(self):
        assert len(FontRegistry()._cache) == 0


class TestFontRegistryGet:
    def test_returns_font_object(self):
        assert isinstance(FontRegistry().get(12), pygame.font.Font)

    def test_same_size_returns_cached_instance(self):
        reg = FontRegistry()
        assert reg.get(14) is reg.get(14)

    def test_different_sizes_different_instances(self):
        reg = FontRegistry()
        assert reg.get(10) is not reg.get(20)

    def test_cache_grows(self):
        reg = FontRegistry()
        reg.get(8)
        reg.get(11)
        reg.get(14)
        assert len(reg._cache) == 3

    def test_small_size(self):
        assert FontRegistry().get(8) is not None

    def test_large_size(self):
        assert FontRegistry().get(48) is not None

    def test_zero_size_does_not_crash(self):
        assert FontRegistry().get(0) is not None and FontRegistry().get(-5) is not None
