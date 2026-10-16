"""Combat history data (``application/combat_log``): entries, cap, version, hero/enemy texts. No pygame."""
from __future__ import annotations

from src.application.combat_log import HERO, MAX_ENTRIES, CombatLog, LogEntry, LogTarget, hero_entry
from src.application.play_card import play_card
from src.domain.card import CardClass
from src.domain.card_pool import card_factories_for_classes
from src.domain.elements import Element, apply_element
from tests.application.test_play_card import _attack_card, _make_state


def _mage(card_id):
    return next(f for f in card_factories_for_classes({CardClass.MAGE}) if f.card_id == card_id)()


class TestLog:
    def test_add_and_version(self):
        log = CombatLog()
        log.turn(1)
        log.effect(1, "frozen", "X está Congelado", "Pierde su turno.")
        assert len(log) == 2 and log.version == 2 and log.entries[0].title == "Turno 1"

    def test_cap_keeps_the_newest(self):
        log = CombatLog(3)
        for i in range(10):
            log.turn(i)
        assert [e.turn for e in log.entries] == [7, 8, 9]

    def test_default_cap_and_huge_fight(self):
        log = CombatLog()
        for i in range(10 ** 4):
            log.turn(i)
        assert len(log) == MAX_ENTRIES and log.version == 10 ** 4

    def test_enemy_sentences(self):
        log = CombatLog()
        log.enemy(2, "attack_1", "Cultista ataca", "1 golpe · ¡todo bloqueado!", 0)
        log.enemy(2, "attack_2", "Gólem ataca", "2 golpes · pierdes 9 de vida", 9)
        a, b = log.entries
        assert a.lines == ("1 golpe.", "¡Todo bloqueado!") and a.value_kind == ""
        assert b.lines == ("2 golpes.", "Pierdes 9 de vida.") and (b.value, b.value_kind) == (9, "loss")


class TestHeroEntry:
    def test_attack(self):
        card = _attack_card(7)
        s = _make_state([card], enemy_hp=50)
        names = [e.name for e in s.enemies]
        result = play_card(s, 0, 0)
        e = hero_entry(1, card, result, names, s.enemies, 0)
        assert e.kind == "hero" and e.title.startswith("Jugaste") and (e.value, e.value_kind) == (7, "damage")
        assert e.lines[0] == "Enemigo: −7 de vida" and e.card is card and e.icon == "damage"

    def test_kill_is_noted(self):
        card = _attack_card(80)
        s = _make_state([card], enemy_hp=5)
        names = [x.name for x in s.enemies]
        e = hero_entry(1, card, play_card(s, 0, 0), names, s.enemies, 0)
        assert e.lines[0].endswith("(muere)")

    def test_element_and_reaction_lines(self):
        card = _mage("mg_gota")
        s = _make_state([card], enemy_hp=60)
        apply_element(s, s.enemies[0], Element.FIRE, 3)
        names = [x.name for x in s.enemies]
        result = play_card(s, 0, 0)
        e = hero_entry(1, card, result, names, s.enemies, 0, list(s.reaction_log))
        assert "Aplicaste 2 de Agua al enemigo" in e.lines
        assert any(l.startswith("¡Vapor! en Enemigo: 10 de daño") for l in e.lines) and e.icon == "water"

    def test_block_only(self):
        card = _mage("mg_burbuja")
        s = _make_state([card])
        e = hero_entry(1, card, play_card(s, 0), [x.name for x in s.enemies], s.enemies, 8)
        assert (e.value, e.value_kind) == (8, "block") and "Ganaste 8 de escudo" in e.lines

    def test_nothing_visible(self):
        card = _mage("mg_catalizador")
        s = _make_state([card])
        e = hero_entry(1, card, play_card(s, 0), [x.name for x in s.enemies], s.enemies, 0)
        assert e.lines == ("Sin efecto visible",) and e.value == 0

    def test_entries_are_frozen(self):
        e = LogEntry("turn", 1, "hourglass", "Turno 1")
        try:
            e.turn = 2
        except Exception:
            return
        raise AssertionError("LogEntry must be immutable")


class TestTargets:
    def _play(self, card, enemy_hp=50, target=0, setup=None):
        s = _make_state([card], enemy_hp=enemy_hp)
        if setup:
            setup(s)
        names = [x.name for x in s.enemies]
        before = [{se.name: se.stacks for se in x.status_effects} for x in s.enemies]
        block = s.player.block
        result = play_card(s, 0, target)
        return hero_entry(1, card, result, names, s.enemies, s.player.block - block, list(s.reaction_log),
                          statuses_before=before, target=target, hero_name="El Mago")

    def test_attack_names_its_target(self):
        e = self._play(_attack_card(9))
        (t,) = e.targets
        assert (t.name, t.hp, t.aimed, t.died) == ("Enemigo", 9, True, False)
        assert e.source == HERO and e.source_name == "El Mago" and e.verb == "attack_2"

    def test_kill_marks_the_target(self):
        assert self._play(_attack_card(99), enemy_hp=5).targets[0].died

    def test_status_and_reaction_on_the_target(self):
        e = self._play(_mage("mg_gota"), enemy_hp=60,
                       setup=lambda s: apply_element(s, s.enemies[0], Element.FIRE, 3))
        assert e.targets[0].reactions == ("Vapor",)
        e = self._play(_mage("mg_gota"), enemy_hp=60)
        assert e.targets[0].statuses == (("Agua", 2),)

    def test_aimed_target_listed_even_without_damage(self):
        e = self._play(_mage("mg_avivar"))
        assert [t.name for t in e.targets] == ["Enemigo"] and e.targets[0].aimed

    def test_self_skill_targets_the_hero(self):
        e = self._play(_mage("mg_burbuja"), target=None)
        assert e.targets == (LogTarget("El Mago", HERO, block=8),) and e.verb == "block"

    def test_power_targets_the_hero(self):
        e = self._play(_mage("mg_archimago"), target=None)
        assert e.targets[0].portrait == HERO and e.verb == "buff"

    def test_enemy_entry_targets(self):
        log = CombatLog()
        log.enemy(1, "attack_1", "X ataca", "1 golpe", 3, source="X",
                  targets=(LogTarget("El Mago", HERO, hp=3),))
        e = log.entries[0]
        assert (e.source, e.verb, e.targets[0].hp) == ("X", "attack_1", 3)
