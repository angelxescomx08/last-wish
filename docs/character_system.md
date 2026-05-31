# Character System

Players choose one of three characters before each run. Each character has five stats that define
their combat style. Stats are stored on `Character.stats` (domain) and copied to `Player` fields
when `create_combat_for_character()` builds the initial `CombatState`.

---

## Domain model

```python
@dataclass(frozen=True)
class CharacterStats:
    damage:    int   # flat bonus added to every attack card
    max_hp:    int   # starting and maximum health
    luck:      int   # extra cards drawn per turn (1 per 5 luck)
    max_mana:  int   # starting and maximum mana
    dexterity: int   # flat bonus added to every block card

@dataclass(frozen=True)
class Character:
    id:          CharacterId   # WARRIOR | MAGE | ROGUE
    name:        str           # Spanish display name
    description: str           # Spanish one-line description
    stats:       CharacterStats

ALL_CHARACTERS: list[Character]   # the three playable characters
```

Both types are `frozen=True` — they are immutable value objects.

---

## The three characters

| | El Guerrero | El Mago | El Pícaro |
|---|---|---|---|
| **Daño** | 4 | 8 | 6 |
| **Vida** | 100 | 60 | 70 |
| **Suerte** | 2 | 5 | 8 |
| **Maná** | 2 | 4 | 3 |
| **Destreza** | 4 | 1 | 2 |

Design intent:
- **Guerrero** — tanky, high block ceiling, low mana.
- **Mago** — glass cannon, most damage and mana, lowest block.
- **Pícaro** — high luck (draws more cards), balanced offence/defence.

---

## Sprites

Each character has a 32×32 sprite from the **Dungeon Crawl Stone Soup** asset pack
(CC0, `assets/dungeon-crawl-stone-soup-full/`), loaded and cached by `SpriteLoader`
in `src/infrastructure/sprite_loader.py`.

| Character | Sprite file |
|---|---|
| El Guerrero | `player/base/human_male.png` |
| El Mago | `player/base/deep_elf_male.png` |
| El Pícaro | `player/base/halfling_male.png` |

`SpriteLoader.get_player_sprite(player.name, size=128)` looks up by the Spanish display
name and returns a `pygame.Surface` scaled to `size×size` pixels (nearest-neighbour), or
`None` if the file is missing. `CombatScene` calls this each draw cycle (the result is cached
after the first load) and passes the surface to `draw_player()` via the `sprite=` keyword.

---

## How stats map to Player fields

`create_combat_for_character()` in `src/application/combat_factory.py` builds the `Player`:

```python
player = Player(
    name         = character.name,
    max_hp       = character.stats.max_hp,
    current_hp   = character.stats.max_hp,   # always starts full
    dexterity    = character.stats.dexterity,
    attack_bonus = character.stats.damage,
    luck         = character.stats.luck,
)
```

Mana is built from `character.stats.max_mana`; `draw_opening_hand()` then applies the
COMBAT_AMULET bonus on top.

---

## Mechanical effects

### Daño → `player.attack_bonus`

Added to every attack card's effective damage in `play_card()`:

```python
effective_dmg = (
    card.total_damage()
    + relic_effects.extra_attack_damage(state.relics)
    + state.player.attack_bonus
)
```

Also included in the `bonus_damage` value passed to `draw_card()` and `card_tooltip()` so the
card display and tooltip always show the true final value.

### Destreza → `player.dexterity`

Added to every block card's effective block in `play_card()`:

```python
effective_blk = card.total_block() + state.player.dexterity
state.player.block += effective_blk
```

The card widget shows `total_block() + dexterity`; the tooltip adds a breakdown line
`(base + N destreza)` when the bonus is non-zero.

### Suerte → `player.luck`

Extra cards drawn each turn (opening hand and every subsequent turn):

```python
extra = player.luck // 5
count = 5 + relic_effects.extra_draw_per_turn(relics) + extra
```

| Luck | Extra cards |
|---|---|
| 0–4 | 0 |
| 5–9 | 1 |
| 10–14 | 2 |
| 8 (Pícaro) | 1 |

### Vida → `player.max_hp` / `player.current_hp`

Both set to `character.stats.max_hp` — every run starts at full HP.

### Maná → `mana.maximum` / `mana.current`

Set to `character.stats.max_mana` before `draw_opening_hand()` applies the COMBAT_AMULET
(+1 if present). Final mana = `max_mana + 1` with the sample relic set.

---

## Starting state

`create_combat_for_character()` guarantees:
- Player is at **full HP**.
- All enemies are at **full HP** (no pre-damaged enemies).
- Discard pile is **empty** (clean start).
- Turn counter is **1**.
- Standard four relics (COMBAT_AMULET, BROKEN_TOTEM, FIRE_ORB, SPECTRAL_SHIELD).

---

## How to add a new character

1. Add a new variant to `CharacterId` in `src/domain/character.py`.
2. Define the `CharacterStats` values.
3. Append a `Character(...)` entry to `ALL_CHARACTERS`.
4. Add a sprite entry to `PLAYER_SPRITE_PATHS` in `src/infrastructure/sprite_loader.py`
   mapping `character.name` → relative path inside `assets/dungeon-crawl-stone-soup-full/`.
5. The character select scene picks up `ALL_CHARACTERS` automatically — no UI changes needed
   unless you exceed three panels.
6. Write tests in `tests/domain/test_character.py`:
   - `id` is unique across `ALL_CHARACTERS`.
   - `max_hp > 0`, `max_mana > 0`.
   - Any design invariants (e.g. tank has most HP, etc.).
7. Add a file-existence test in `tests/test_sprite_loader.py` (or update the existing
   `TestAssetFilesExist` class) to verify the new sprite path resolves on disk.
