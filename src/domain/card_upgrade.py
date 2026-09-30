"""Card upgrades (Slay the Spire style), done at the Brujo on the map.

Every card can be upgraded. Normal cards allow **one** upgrade (``Card.max_upgrades
= 1``); a card with ``max_upgrades=None`` can be upgraded without limit, and any
other number is its cap.

What an upgrade does comes from ``Card.upgrade`` (a ``CardUpgrade``) when the card
defines one — mana, damage, block, draw, mana gain, or new text / on_play — or
else from ``default_upgrade``:

* deals damage and/or gives block → +3 each, or +1/3 of the value if bigger;
* otherwise, costs mana → costs 1 less;
* otherwise (free card) → draws 1 more card.

The upgraded card is renamed "Golpe+" (then "Golpe+2", "Golpe+3"… for unlimited
cards). Pure domain code: no pygame.
"""
from __future__ import annotations

import copy
from dataclasses import replace

from src.domain.card import Card, CardUpgrade

MIN_STAT_UPGRADE: int = 3


def can_upgrade(card: Card) -> bool:
    return card.max_upgrades is None or card.upgrade_level < card.max_upgrades


def default_upgrade(card: Card) -> CardUpgrade:
    """The generic upgrade for a card without a custom ``Card.upgrade``."""
    dmg = card.base_effect.damage.resolve()
    blk = card.base_effect.block.resolve()
    if dmg > 0 or blk > 0:
        return CardUpgrade(damage=max(MIN_STAT_UPGRADE, dmg // 3) if dmg > 0 else 0,
                           block=max(MIN_STAT_UPGRADE, blk // 3) if blk > 0 else 0)
    if card.cost > 0:
        return CardUpgrade(cost=-1)
    return CardUpgrade(draw=1)


def next_upgrade(card: Card) -> CardUpgrade:
    """What the next upgrade of ``card`` will change."""
    return card.upgrade or default_upgrade(card)


def describe_upgrade(card: Card) -> str:
    """Spanish summary of the next upgrade: "+3 de daño, -1 de maná"."""
    up = next_upgrade(card)
    if up.description:
        return up.description
    parts: list[str] = []
    if up.cost:
        parts.append(f"{up.cost:+d} de maná" if card.cost + up.cost >= 0 else "coste 0")
    if up.damage:
        parts.append(f"{up.damage:+d} de daño")
    if up.block:
        parts.append(f"{up.block:+d} de escudo")
    if up.draw:
        parts.append(f"roba {up.draw} más")
    if up.mana_gain:
        parts.append(f"+{up.mana_gain} de maná al jugarla")
    if up.text:
        parts.append(up.text)
    return ", ".join(parts) or "mejora especial"


def upgraded_name(base_name: str, level: int) -> str:
    if level <= 0:
        return base_name
    return f"{base_name}+" if level == 1 else f"{base_name}+{level}"


def apply_upgrade(card: Card) -> bool:
    """Upgrade ``card`` in place by one level. Returns False if it is already at its cap."""
    if not can_upgrade(card):
        return False
    up = next_upgrade(card)
    fx = card.base_effect
    card.base_effect = replace(
        fx,
        damage=fx.damage.add_flat(up.damage) if up.damage else fx.damage,
        block=fx.block.add_flat(up.block) if up.block else fx.block,
        draw=max(0, fx.draw + up.draw),
        mana_gain=max(0, fx.mana_gain + up.mana_gain),
        on_play=up.on_play if up.on_play is not None else fx.on_play,
        text=up.text or fx.text,
    )
    card.cost = max(0, card.cost + up.cost)
    card.upgrade_level += 1
    card.name = upgraded_name(card.base_name, card.upgrade_level)
    return True


def upgraded_preview(card: Card) -> Card:
    """A copy of ``card`` with one more upgrade, for showing before paying (card untouched)."""
    preview = copy.copy(card)
    apply_upgrade(preview)
    return preview
