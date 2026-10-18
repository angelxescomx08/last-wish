"""El Brujo: upgrades cards of the run's deck for gold (one Brujo room per floor).

Price = ``UPGRADE_PRICE[rarity] × (level + 1)``: a card's first upgrade costs the
base price of its rarity; unlimited cards get pricier with every level.
No pygame.
"""
from __future__ import annotations

from src.domain.card import Card
from src.domain.card_upgrade import apply_upgrade, can_upgrade
from src.domain.rarity import Rarity
from src.domain.run import Run

UPGRADE_PRICE: dict[Rarity, int] = {
    Rarity.COMMON:    50,
    Rarity.UNCOMMON:  75,
    Rarity.RARE:      100,
    Rarity.EPIC:      150,
    Rarity.LEGENDARY: 200,
}


def upgrade_price(card: Card, relics=()) -> int:
    """Price of the next upgrade; Martillo del Herrero halves it (rounded up)."""
    from src.domain.relic import RelicTag, relic_total
    base = UPGRADE_PRICE[card.rarity or Rarity.COMMON]
    price = base * (card.upgrade_level + 1)
    if relic_total(list(relics), RelicTag.SMITH_HAMMER):
        price = (price + 1) // 2
    return price


def can_buy_upgrade(run: Run, card: Card) -> bool:
    return can_upgrade(card) and run.gold >= upgrade_price(card, run.relics)


def buy_upgrade(run: Run, index: int) -> bool:
    """Upgrade ``run.deck[index]`` paying its price. False (nothing changes) if not possible."""
    if not 0 <= index < len(run.deck):
        return False
    card = run.deck[index]
    if not can_buy_upgrade(run, card):
        return False
    run.gold -= upgrade_price(card, run.relics)
    apply_upgrade(card)
    return True
