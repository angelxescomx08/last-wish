from __future__ import annotations

import random
from dataclasses import dataclass, field

from src.domain.card import Card
from src.domain.entities import Enemy, Player, deal_damage
from src.domain.mana import Mana
from src.domain.pile import DiscardPile, DrawPile, Hand
from src.domain.relic import Relic, RelicTag, relic_total


@dataclass
class EnemyAction:
    """What one enemy did during the last enemy turn (read by the combat screen).

    ``index`` is the enemy's position in ``CombatState.enemies`` *before* dead
    enemies were removed at the end of that turn. ``hits`` holds the HP the hero
    lost on each hit, in order (0 = fully blocked or redirected).
    """
    index: int
    move_id: str = ""
    move: str = ""
    hits: list[int] = field(default_factory=list)
    cards: list[tuple[str, int, str]] = field(default_factory=list)
    debuffs: list[tuple[str, int]] = field(default_factory=list)
    healed: int = 0                     # HP the enemy (or its allies) recovered
    exploded: bool = False              # self-destructed (Seta Explosiva)


@dataclass
class CombatState:
    player: Player
    enemies: list[Enemy]
    hand: Hand
    draw_pile: DrawPile
    discard_pile: DiscardPile
    mana: Mana
    relics: list[Relic] = field(default_factory=list)
    active_powers: list[Card] = field(default_factory=list)
    turn: int = 1
    selected_card_index: int | None = None
    targeted_enemy_index: int | None = None
    cards_played_this_turn: int = 0   # resets each player turn; > 0 turns Combo on
    singular_deck: bool = False       # keyword SINGULAR: the starting deck had no repeated cards
    # Cost modifiers (see ``card_cost``)
    next_card_discount: int = 0       # "la siguiente carta cuesta 1 menos" (this turn only)
    first_card_discount: int = 0      # power: the first card of each turn costs less (whole combat)
    next_damage_bonus: int = 0        # "la siguiente carta inflige +6" (next damaging card, this turn)
    combo_always: bool = False        # power: Combo resolves without playing a card first

    # --- per-turn counters (reset in ``end_turn._begin_player_turn``) -------------
    discards_this_turn: int = 0       # cards discarded by effects; > 0 turns Despojo on
    spoils_this_turn: int = 0         # Despojo layers resolved (Garfio: the first one draws)
    attacks_this_turn: int = 0        # attack cards played (Frasco de Veneno: the first one)
    double_combo_used: bool = False   # Sombra Gemela already doubled a Combo this turn
    decoys: int = 0                   # Señuelo: enemy attacks redirected to another enemy
    counter_damage: int = 0           # Contraataque: damage back per fully blocked hit
    retain_block: bool = False        # Capa de Sombras: block is not lost at the next turn start
    turn_start_alive: int = 0         # living enemies when the turn began (Carterista)
    pickpocket_gold: int = 0          # Carterista: gold paid if an enemy dies this turn
    last_random_target: int | None = None   # id() of the last enemy hit at random (Moneda)
    lucky_coin_used: bool = False     # Moneda de la Suerte paid this turn

    # --- whole-combat effects (powers, relics) --------------------------------------
    pending_draws: int = 0            # draws asked by an effect, done right after it resolves
    poison_attacks: int = 0           # Hoja Envenenada: next attacks that apply poison
    daggers_on_draw: int = 0          # Maestra de Dagas: daggers added when a dagger is drawn
    discard_damage: int = 0           # Rapiña: damage to a random enemy per discarded card
    double_combo: int = 0             # Sombra Gemela: extra Combo resolutions per turn
    echo_every_fifth: int = 0         # Cadena Perfecta: extra casts of every 5th card in a turn
    execute_threshold: bool = False   # Asesina: attacks finish enemies under 25 % HP
    turn_rummages: list[int] = field(default_factory=list)   # Nada que Perder: discard 1, draw N
    clock_uses: int = 0               # Reloj Roto charges spent this combat
    gold_earned: int = 0              # gold won during the fight (added to the run on victory)
    enemy_log: list[EnemyAction] = field(default_factory=list)   # last enemy turn, per acting enemy
    exhausted: list[Card] = field(default_factory=list)          # cards removed for this combat

    @property
    def combo_active(self) -> bool:
        """Keyword COMBO: another card was already played this turn (or a power says always).

        Cinta Roja: on the first turn of the combat Combos are always on.
        """
        return (self.cards_played_this_turn > 0 or self.combo_always
                or (self.turn == 1 and self.has_relic(RelicTag.CRIMSON_RIBBON)))

    @property
    def spoil_active(self) -> bool:
        """Keyword SPOIL ("Despojo"): a card was discarded by an effect this turn."""
        return self.discards_this_turn > 0

    def has_relic(self, tag: RelicTag) -> bool:
        return relic_total(self.relics, tag) > 0

    def card_cost(self, card) -> int:
        """Mana ``card`` costs right now, after discounts (never below 0).

        Guante de Seda: the third card of each turn is free.
        """
        if self.cards_played_this_turn == 2 and self.has_relic(RelicTag.SILK_GLOVE):
            return 0
        discount = self.next_card_discount
        if self.cards_played_this_turn == 0:
            discount += self.first_card_discount
        return max(0, card.cost - discount)

    def void_ready(self, card) -> bool:
        """Keyword VOID would resolve if ``card`` were played now (it spends the last mana)."""
        from src.domain.keywords import void_triggers   # local: keywords is a leaf module
        return bool(card.void_effects()) and void_triggers(self.card_cost(card), self.mana.current)

    def singular_ready(self, card) -> bool:
        """Keyword SINGULAR would resolve for ``card`` in this combat."""
        return self.singular_deck and bool(card.singular_effects())

    def spoil_ready(self, card) -> bool:
        """Keyword SPOIL would resolve for ``card`` if played now."""
        return self.spoil_active and bool(card.spoil_effects())

    # ------------------------------------------------------------------
    # Shared effect helpers (used by card effects, relics and the turn pipeline)
    # ------------------------------------------------------------------

    def living_enemies(self) -> list[Enemy]:
        return [e for e in self.enemies if e.is_alive]

    def pick_random_enemy(self, rng: random.Random | None = None) -> Enemy | None:
        """A random living enemy for "al azar" effects.

        Moneda de la Suerte: hitting the same enemy as the previous random pick
        (with 2+ enemies alive) gives +1 mana, once per turn (golden: +2).
        """
        alive = self.living_enemies()
        if not alive:
            return None
        enemy = (rng or random).choice(alive)
        coin = relic_total(self.relics, RelicTag.LUCKY_COIN)
        if (coin and not self.lucky_coin_used and len(alive) > 1
                and self.last_random_target == id(enemy)):
            self.mana.gain(coin)
            self.lucky_coin_used = True
        self.last_random_target = id(enemy)
        return enemy

    def hit_random_enemy(self, amount: int, rng: random.Random | None = None) -> Enemy | None:
        """``amount`` damage to a random living enemy (block and Marcado apply)."""
        enemy = self.pick_random_enemy(rng)
        if enemy is not None:
            deal_damage(enemy, amount)
        return enemy

    def discard_from_hand(self, index: int) -> Card | None:
        """Discard the hand card at ``index`` by an effect (turns Despojo on; Rapiña hits)."""
        if not 0 <= index < self.hand.count:
            return None
        card = self.hand.cards.pop(index)
        self.discard_pile.cards.append(card)
        self.discards_this_turn += 1
        if self.discard_damage:
            self.hit_random_enemy(self.discard_damage)
        return card

    def discard_random(self, rng: random.Random | None = None) -> Card | None:
        """Discard a random card from the hand (nothing if the hand is empty)."""
        if not self.hand.cards:
            return None
        return self.discard_from_hand((rng or random).randrange(self.hand.count))

    def kills_this_turn(self) -> int:
        """Enemies that died since the turn began (dead ones stay listed until the enemy turn)."""
        return max(0, self.turn_start_alive - len(self.living_enemies()))

    def add_status_cards(self, card_id: str, count: int, pile: str,
                         rng: random.Random | None = None) -> int:
        """Put ``count`` new status cards in a pile: ``"draw"`` (shuffled in at random
        places), ``"discard"`` or ``"hand"`` (overflow goes to the discard pile).
        Returns how many were added."""
        from src.domain.status_cards import make_status_card   # local: status_cards imports card
        rng = rng or random
        added = 0
        for _ in range(max(0, count)):
            card = make_status_card(card_id)
            if card is None:
                break
            if pile == "draw":
                self.draw_pile.cards.insert(rng.randint(0, self.draw_pile.count), card)
            elif pile == "hand" and not self.hand.is_full:
                self.hand.cards.append(card)
            else:
                self.discard_pile.cards.append(card)
            added += 1
        return added
