from __future__ import annotations

import random

from src.application import relic_effects
from src.application.drawing import draw_cards
from src.domain.card_pool import hidden_dagger
from src.application import enemy_ai, enemy_roster
from src.domain.combat import CombatState, EnemyAction
from src.domain.entities import (ENTANGLED, HERO_TIMED_DEBUFFS, MARKED, POISON, WEAK, Enemy, Intent,
                                 IntentType, add_status, deal_damage, enemy_hit_damage,
                                 status_stacks, tick_status)
from src.domain.tuning import TUNING

_HAND_DRAW_SIZE: int = 5
ENEMY_DEBUFF_TURNS: int = 2    # an enemy DEBUFF makes the hero Débil for this many turns


def cards_per_turn(state: CombatState) -> int:
    """Nominal turn draw; actual draws are limited by deck and hand capacity."""
    return _HAND_DRAW_SIZE + relic_effects.extra_draw_per_turn(state.relics)


def end_player_turn(state: CombatState) -> None:
    """Full end-of-turn pipeline: discard → enemies act → new player turn.

    Block resets at the START of the player's next turn (inside
    _begin_player_turn), so block accumulated this turn absorbs enemy attacks.
    """
    _discard_hand(state)
    _run_enemy_turn(state)
    _begin_player_turn(state)


def draw_opening_hand(state: CombatState) -> None:
    """Apply combat-start relic effects and draw the opening hand.

    Bolsa de Dagas shuffles its daggers in first; Botas Silenciosas draw extra;
    then the usual start-of-turn hand effects (Bolsillo Roto, Nada que Perder).
    """
    for _ in range(relic_effects.dagger_pouch_count(state.relics)):
        state.draw_pile.cards.append(hidden_dagger())
    random.shuffle(state.draw_pile.cards)
    bonus_mana = relic_effects.bonus_starting_mana(state.relics)
    if bonus_mana > 0:
        state.mana.maximum += bonus_mana
        state.mana.refill()
    state.turn_start_alive = len(state.living_enemies())
    draw_cards(state, cards_per_turn(state) + relic_effects.opening_extra_draw(state.relics))
    _after_hand_drawn(state)


# ---------------------------------------------------------------------------
# Pipeline steps
# ---------------------------------------------------------------------------

def _discard_hand(state: CombatState) -> None:
    # Hilo de Araña: ending the turn with an empty hand gives block (it absorbs this enemy turn).
    if state.hand.count == 0:
        state.player.block += relic_effects.spider_thread_block(state.relics)
    relic_effects.settle_pickpocket(state)
    # Status cards still in hand act (Espora: Veneno); ethereal ones fade instead of discarding.
    for card in list(state.hand.cards):
        if card.on_turn_end_in_hand is not None:
            card.on_turn_end_in_hand(state)
    for card in state.hand.cards:
        (state.exhausted if card.ethereal else state.discard_pile.cards).append(card)
    state.hand.cards.clear()
    # End of the hero's turn: one turn of Débil / Vulnerable / Frágil wears off;
    # "this turn" bonuses expire.
    for name in HERO_TIMED_DEBUFFS:
        state.player.status_effects = tick_status(state.player.status_effects, name)
    state.next_card_discount = 0
    state.next_damage_bonus = 0
    state.pickpocket_gold = 0
    for enemy in state.enemies:                     # Marcado lasts only your turn
        enemy.status_effects = [se for se in enemy.status_effects if se.name != MARKED]


def _run_enemy_turn(state: CombatState) -> None:
    state.enemy_log = []
    for enemy in state.enemies:          # block lasts until the enemies act again; reset all
        enemy.block = 0                  # first, so block an ally gives this turn is kept
    for index, enemy in enumerate(state.enemies):
        if enemy.is_alive:
            _tick_status_effects(enemy)   # poison/burn deal damage before acting
            if not enemy.is_alive:        # killed by status? skip action
                relic_effects.spread_poison(state)   # Colmillo de Víbora
                continue
            state.enemy_log.append(_execute_intent(state, enemy, index))
            enemy.status_effects = tick_status(enemy.status_effects, WEAK)   # lasts its turn
            enemy_roster.after_action(enemy)

    # Remove defeated enemies before rolling new intents
    state.enemies = [e for e in state.enemies if e.is_alive]

    for enemy in state.enemies:
        enemy.intent = _next_intent(state, enemy)


def _next_intent(state: CombatState, enemy: Enemy) -> Intent:
    """Pattern enemies (bosses, ``enemy_roster``) follow their pattern; others roll at random."""
    if enemy_ai.has_pattern(enemy):
        return enemy_ai.next_intent(enemy, state.player, state.enemies)
    return _roll_intent(enemy)


def _execute_intent(state: CombatState, enemy: Enemy, index: int = 0) -> EnemyAction:
    """Resolve the enemy's intent, then its extras (block, buffs, debuffs, status cards)."""
    intent = enemy.intent
    action = EnemyAction(index=index, move_id=intent.move_id, move=intent.move)
    named = bool(intent.move)          # a boss move: extras instead of the generic behaviour
    match intent.intent_type:
        case IntentType.ATTACK:
            for _ in range(max(1, intent.hits)):
                if not enemy.is_alive or not state.player.is_alive:
                    break
                action.hits.append(_enemy_attack(state, enemy, enemy_hit_damage(enemy, state.player)))
            if intent.lifesteal and enemy.is_alive:          # Murciélago Vampiro
                action.healed += _heal(enemy, sum(action.hits))

        case IntentType.BLOCK:
            enemy.block += intent.value

        case IntentType.BUFF if not named:
            # Buff: ramp up damage for the following attack
            enemy.intent = Intent(IntentType.ATTACK, random.randint(10, 20))

        case IntentType.DEBUFF if not named:
            # The hero is weakened for their next 2 turns (Panacea: immune).
            if not relic_effects.immune_to_debuffs(state.relics):
                add_status(state.player.status_effects, WEAK, ENEMY_DEBUFF_TURNS, is_buff=False)
                action.debuffs.append((WEAK, ENEMY_DEBUFF_TURNS))

        case _:
            pass

    if intent.block > 0:
        enemy.block += intent.block
    for name, stacks in intent.buffs:
        if stacks > 0:
            add_status(enemy.status_effects, name, stacks, is_buff=True)
    if intent.debuffs and not relic_effects.immune_to_debuffs(state.relics):   # Panacea
        for name, stacks in intent.debuffs:
            if stacks > 0:
                add_status(state.player.status_effects, name, stacks, is_buff=False)
                action.debuffs.append((name, stacks))
    for card_id, count, pile in intent.cards:
        added = state.add_status_cards(card_id, count, pile)
        if added:
            action.cards.append((card_id, added, pile))
    _ally_extras(state, enemy, intent, action)
    if intent.self_destruct and enemy.is_alive:              # Seta Explosiva
        enemy.current_hp = 0
        action.exploded = True
    return action


def _heal(enemy: Enemy, amount: int) -> int:
    """Heal ``enemy`` up to its max HP. Returns the HP recovered."""
    gained = max(0, min(amount, enemy.max_hp - enemy.current_hp))
    enemy.current_hp += gained
    return gained


def _ally_extras(state: CombatState, enemy: Enemy, intent: Intent, action: EnemyAction) -> None:
    """Support moves: block / statuses for the other living enemies, heals for all of them."""
    allies = [e for e in state.enemies if e.is_alive and e is not enemy]
    for ally in allies:
        if intent.ally_block > 0:
            ally.block += intent.ally_block
        for name, stacks in intent.ally_buffs:
            if stacks > 0:
                add_status(ally.status_effects, name, stacks, is_buff=True)
    if intent.heal_allies > 0:
        for e in [enemy] + allies:
            action.healed += _heal(e, intent.heal_allies)


def _enemy_attack(state: CombatState, enemy: Enemy, dmg: int) -> int:
    """One hit on the hero (block, Señuelo, Contraataque, death saves). Returns HP lost."""
    if _redirect_to_decoy(state, enemy, dmg):
        return 0
    absorbed = min(state.player.block, dmg)
    state.player.block = max(0, state.player.block - absorbed)
    lost = 0
    if not TUNING.invincible:          # Pruebas: invincible hero
        lost = min(state.player.current_hp, dmg - absorbed)
        state.player.current_hp -= lost
    # Contraataque: a hit fully blocked deals damage back to the attacker.
    if dmg > 0 and absorbed == dmg and state.counter_damage:
        deal_damage(enemy, state.counter_damage)
    relic_effects.try_revive(state)
    return lost


def _redirect_to_decoy(state: CombatState, attacker: Enemy, dmg: int) -> bool:
    """Señuelo: the attack hits another living enemy instead of the hero (if there is one)."""
    if state.decoys <= 0:
        return False
    others = [e for e in state.enemies if e.is_alive and e is not attacker]
    if not others:
        return False
    state.decoys -= 1
    deal_damage(random.choice(others), dmg)
    return True


def _tick_status_effects(enemy: Enemy) -> None:
    """Apply per-turn status effects and reduce their stacks by 1."""
    for se in enemy.status_effects:
        if se.name == POISON:
            enemy.current_hp = max(0, enemy.current_hp - se.stacks)
            se.stacks -= 1
    enemy.status_effects = [se for se in enemy.status_effects if se.stacks > 0]


def _roll_intent(enemy: Enemy) -> Intent:
    """Simple weighted random intent for the next turn."""
    roll = random.random()
    if roll < 0.55:
        return Intent(IntentType.ATTACK, random.randint(5, 15))
    elif roll < 0.80:
        return Intent(IntentType.BLOCK, random.randint(4, 10))
    elif roll < 0.92:
        return Intent(IntentType.BUFF, 0)
    else:
        return Intent(IntentType.DEBUFF, 0)


def _begin_player_turn(state: CombatState) -> None:
    if state.retain_block:           # Capa de Sombras: this turn the block is kept
        state.retain_block = False
    else:
        state.player.block = 0       # block resets at the START of the new turn
    state.turn += 1
    _reset_turn_counters(state)
    state.mana.maximum += relic_effects.max_mana_per_turn(state.relics)   # Fuente Eterna
    state.mana.refill()
    state.selected_card_index = None
    state.targeted_enemy_index = None
    _poison_hero(state)
    _trigger_powers(state)
    # Enredado: draw 1 card less per stack, this turn only.
    tangled = status_stacks(state.player.status_effects, ENTANGLED)
    state.player.status_effects = [se for se in state.player.status_effects if se.name != ENTANGLED]
    draw_cards(state, cards_per_turn(state) - tangled)
    _after_hand_drawn(state)
    relic_effects.spread_poison(state)
    enemy_roster.react_to_deaths(state.enemies, state.player)


def _poison_hero(state: CombatState) -> None:
    """Veneno on the hero: lose its stacks in HP (block does not help), then 1 stack wears off."""
    stacks = status_stacks(state.player.status_effects, POISON)
    if stacks <= 0:
        return
    if not TUNING.invincible:
        state.player.current_hp = max(0, state.player.current_hp - stacks)
        relic_effects.try_revive(state)
    state.player.status_effects = tick_status(state.player.status_effects, POISON)


def _reset_turn_counters(state: CombatState) -> None:
    state.cards_played_this_turn = 0  # Combo needs a card played earlier this turn
    state.discards_this_turn = 0      # Despojo needs a discard earlier this turn
    state.spoils_this_turn = 0
    state.attacks_this_turn = 0
    state.double_combo_used = False
    state.decoys = 0
    state.counter_damage = 0
    state.pickpocket_gold = 0
    state.last_random_target = None
    state.lucky_coin_used = False
    state.turn_start_alive = len(state.living_enemies())


def _after_hand_drawn(state: CombatState) -> None:
    """Once the hand is drawn: Bolsillo Roto (discard 1, draw 1) and Nada que Perder
    (discard 1, draw 2). Each discard turns Despojo on for the turn."""
    for draws in [1] * relic_effects.torn_pocket_rummages(state.relics) + list(state.turn_rummages):
        if state.discard_random() is not None:
            draw_cards(state, draws)


def _trigger_powers(state: CombatState) -> None:
    """Powers in play with an ``on_turn_start`` effect act (golden powers: twice)."""
    for power in list(state.active_powers):
        for fx in power.all_effects():
            if fx.on_turn_start is not None:
                for _ in range(power.casts()):
                    fx.on_turn_start(state)
                    draws, state.pending_draws = state.pending_draws, 0
                    draw_cards(state, draws)
