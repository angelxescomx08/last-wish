# Turn Pipeline

Every combat turn follows a strict two-phase pipeline:

1. **Player phase** — the player plays cards using mana, then clicks End Turn.
2. **Enemy phase** — enemies execute their intents, then the player's new turn begins.

---

## Combat start

Called once when `create_sample_combat()` builds the initial state:

```
draw_opening_hand(state)
  │
  ├─ random.shuffle(state.draw_pile.cards)
  │
  ├─ COMBAT_AMULET check
  │     bonus = bonus_starting_mana(relics)
  │     if bonus > 0:
  │         state.mana.maximum += bonus
  │         state.mana.refill()
  │
  └─ _draw_cards(state, 5 + extra_draw_per_turn(relics))
        ├─ if draw_pile empty → shuffle discard into draw_pile
        └─ pop cards until count reached or hand is full (max 10)
```

**Result with sample relics:**
- Mana: 3 + 1 (Amuleto) = **4/4**
- Hand: 5 + 1 (Tótem) = **6 cards**

---

## Player phase (per turn)

The player has full control:

- **Play card:** calls `play_card(state, card_index, target_enemy_index)`.
  - Validates index, mana, and target.
  - Applies damage (+ Orbe de Fuego bonus) to the target.
  - Applies block to the player.
  - Spends mana.
  - Moves card: POWER → `active_powers`, others → `discard_pile`.
  - Draws bonus cards (`fx.draw` summed across all effects).
- **End turn:** calls `end_player_turn(state)`.

---

## End-of-turn pipeline

```
end_player_turn(state)
  │
  ├─ _discard_hand(state)
  │     state.discard_pile.cards.extend(state.hand.cards)
  │     state.hand.cards.clear()
  │
  ├─ state.player.block = 0          ← STS rule: block resets BEFORE enemies act
  │
  ├─ _run_enemy_turn(state)
  │     │
  │     ├─ for each living enemy → _execute_intent(state, enemy)
  │     │     ├─ ATTACK:  dmg = intent.value
  │     │     │           absorbed = min(player.block, dmg)
  │     │     │           player.block -= absorbed
  │     │     │           player.hp   -= (dmg - absorbed)
  │     │     │           try_spectral_shield(state)   ← SPECTRAL_SHIELD check
  │     │     ├─ BLOCK:   enemy.block += intent.value
  │     │     └─ BUFF:    enemy.intent = ATTACK(random 10–20)
  │     │
  │     ├─ Remove dead enemies
  │     └─ Roll new intent for each living enemy
  │
  └─ _begin_player_turn(state)
        ├─ state.turn += 1
        ├─ state.mana.refill()
        ├─ state.selected_card_index = None
        └─ _draw_cards(state, 5 + extra_draw_per_turn(relics))
```

---

## STS block rule

> Player block resets to **0** at the **end of the player's turn**, **before** enemies execute their intents.

Block gained by playing skill cards **does not** carry over to absorb enemy attacks that same turn. This is intentional — it matches the Slay the Spire design. Block gained at the start of the next turn (from cards played on that turn) is the intended protection mechanism.

---

## Draw pile management

`_draw_cards(state, count)` follows this logic for each card to draw:

```
if draw_pile is empty:
    if discard_pile is also empty:
        stop drawing
    else:
        shuffle discard_pile into draw_pile
        clear discard_pile

if draw_pile is not empty and hand is not full:
    hand.cards.append(draw_pile.cards.pop())
```

The draw pile is a stack (pop from end). The discard is unordered — when reshuffled it becomes the new draw order.

---

## Intent rolling

After enemies act, each surviving enemy gets a new random intent via `_roll_intent()`:

| Roll range | Intent |
|---|---|
| 0.00 – 0.55 | ATTACK (5–15 damage) |
| 0.55 – 0.80 | BLOCK (4–10 block) |
| 0.80 – 0.92 | BUFF (ramps to ATTACK 10–20 next turn) |
| 0.92 – 1.00 | DEBUFF (no effect yet — placeholder) |
