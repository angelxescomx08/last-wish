# Turn Pipeline

Every combat turn follows a strict two-phase pipeline:

1. **Player phase** — the player plays cards using mana, then clicks End Turn.
2. **Enemy phase** — enemies execute their intents, then the player's new turn begins.

---

## Combat start

Called once when `create_combat_for_character()` (or `create_sample_combat()`) builds the initial state:

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
  └─ _draw_cards(state, 5 + extra_draw_per_turn(relics) + player.luck // 5)
        ├─ if draw_pile empty → shuffle discard into draw_pile
        └─ pop cards until count reached or hand is full (max 10)
```

**Example with all four sample relics and a Guerrero (luck=2):**
- Mana: 2 + 1 (Amuleto) = **3/3**
- Luck bonus: 2 // 5 = **0 extra cards**
- Hand: 5 + 1 (Tótem) + 0 = **6 cards**

**Example with a Mago (luck=5):**
- Mana: 4 + 1 (Amuleto) = **5/5**
- Luck bonus: 5 // 5 = **1 extra card**
- Hand: 5 + 1 (Tótem) + 1 = **7 cards**

---

## Player phase (per turn)

The player has full control:

- **Play card:** calls `play_card(state, card_index, target_enemy_index)`.
  - Validates index, mana, and target.
  - Computes effective damage: `card.total_damage() + extra_attack_damage(relics) + player.attack_bonus`.
  - Computes effective block: `card.total_block() + player.dexterity`.
  - Applies effective damage to the target enemy (minus enemy block absorption).
  - Applies effective block to the player.
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
  ├─ _run_enemy_turn(state)          ← block still active here — absorbs damage
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
        ├─ state.player.block = 0   ← block resets at START of new turn
        ├─ state.turn += 1
        ├─ state.mana.refill()
        ├─ state.selected_card_index = None
        └─ _draw_cards(state, 5 + extra_draw_per_turn(relics) + player.luck // 5)
```

---

## Block rule

> Player block resets to **0** at the **start of the player's next turn**, after enemies have already acted.

Block gained by playing skill cards **does** absorb enemy attacks that same turn — this is the intended mechanic. At the beginning of the following player turn, block is cleared so the player starts fresh.

Note: dexterity still applies when the block card is played — the increase happens at play time, not at reset time.

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

## Character stat effects on draw

The `player.luck` field (set from `Character.stats.luck` at combat creation) adds extra cards each turn:

| Luck value | Extra cards per turn |
|---|---|
| 0–4 | 0 |
| 5–9 | 1 |
| 10–14 | 2 |
| … | … |

Formula: `extra = player.luck // 5`

---

## Death detection

After `end_player_turn(state)` returns, `CombatScene` checks `state.player.is_alive` via its
`death_occurred` property. If `False`, `SceneManager` pushes `DeathScene` on the next update tick.
The `_death_acknowledged` flag on `CombatScene` prevents the push from firing more than once.

---

## Intent rolling

After enemies act, each surviving enemy gets a new random intent via `_roll_intent()`:

| Roll range | Intent |
|---|---|
| 0.00 – 0.55 | ATTACK (5–15 damage) |
| 0.55 – 0.80 | BLOCK (4–10 block) |
| 0.80 – 0.92 | BUFF (ramps to ATTACK 10–20 next turn) |
| 0.92 – 1.00 | DEBUFF (no effect yet — placeholder) |
