# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Last Wish** is a roguelike card game built with pygame, managed with uv. Python 3.13+ required.

The combat system uses a **BigValue** arithmetic engine (inspired by Balatro's Chips × Mult model) that
supports arbitrary-precision integers with no overflow risk — values up to 10^1000 and beyond are exact.

---

## Commands

```bash
# Run the game
uv run main.py

# Run the full test suite (mandatory before any merge)
uv run pytest tests/ -v

# Run a single test file
uv run pytest tests/test_numbers.py -v

# Add a runtime dependency
uv add <package> --system-certs

# Add a dev-only dependency
uv add <package> --dev --system-certs
```

---

## Change Workflow — mandatory for every change

**Before finishing any change:**

1. **Run the full test suite**: `uv run pytest tests/ -v` — 0 failures required.
2. **Add or update tests** in the corresponding `tests/test_<module>.py` file.
   - Cover the new behaviour, boundary values (0, 1, max, max+1), and large numbers.
3. **Update this file** if the change affects architecture, a module's responsibility, a relic mechanic, a public API, or the BigValue resolution formula.

No exceptions. A change without passing tests is not done.

---

## Language Convention

- **Code**: all identifiers, comments, variable names, class names, and file names must be in **English**.
- **UI / dialog text**: every string rendered on screen (menus, dialogs, card names, player messages) must be in **Spanish**.

---

## Architecture

The project follows Clean Architecture with SOLID principles. Layers must not be crossed — outer layers depend on inner ones, never the reverse.

```
src/
  domain/        # Pure business logic — no pygame, no I/O
  application/   # Use cases — orchestrate domain objects, no pygame
  infrastructure/# pygame utilities + user-preference persistence
  presentation/  # Screens, UI widgets, scene manager
main.py          # Entry point — wires layers and owns the game loop
tests/           # pytest unit tests — one file per module
```

### Dependency rule (enforced)

```
presentation  →  application  →  domain
infrastructure  →  (used by presentation only)
```

- **Domain** has zero pygame imports.
- **Use cases** never call pygame; they receive and return domain objects.
- **Screens** call use cases; they never touch domain logic directly.

### pygame loop (in main.py)

```python
clock = pygame.time.Clock()
prefs = load_preferences()
scene_manager = SceneManager(MainMenuScene(fonts), fonts, prefs)
while running:
    dt = clock.tick(60) / 1000.0
    for event in pygame.event.get():
        scene_manager.handle_event(event)
    scene_manager.update(dt)
    scene_manager.draw(viewport.surface)
    if prefs.show_fps:                       # FPS overlay (top-right corner)
        ...
    viewport.present(screen)
    pygame.display.flip()
```

Scenes are pushed/popped on a stack managed by `SceneManager`; each scene implements `handle_event`, `update(dt)`, and `draw(surface)`. `SceneManager` also holds `_prefs: UserPreferences` and calls `save_preferences()` when `SettingsScene` clears.

---

## File Map

### Domain layer — `src/domain/`

Every file in this layer is pygame-free and has a corresponding test file.

| File | Class / data | Responsibility |
|---|---|---|
| `numbers.py` | `BigValue`, `Operation` | Arbitrary-precision arithmetic: base + flat additions + multipliers |
| `card.py` | `Card`, `CardEffect`, `CardModifier`, `CardType`, `ModifierTag` | A card with stacked effect chain and modifier list. `CardEffect.needs_target` forces an enemy target; `CardEffect.hits_all_enemies` marks area effects (UI hint only) |
| `relic.py` | `Relic`, `RelicTag`, `RELIC_RARITY`, `relic_total(relics, tag, amount)` | Passive items with a tag identifying their mechanic (34 tags). `Relic.rarity` defaults to `RELIC_RARITY[tag]` (Common if untagged). `relic_total` = amount × chroma per active relic with that tag (domain code uses it directly) |
| `rarity.py` | `Rarity`, `RARITY_LABEL`, `rarity_weight`, `rarity_odds`, `luck_chroma_multiplier`, `weighted_sample` | Five tiers shared by cards and relics (`CardRarity` is an alias). Luck-weighted tier odds and chroma boost |
| `character.py` | `Character`, `CharacterStats`, `CharacterId`, `ALL_CHARACTERS` | Three playable characters with stat profiles (damage, max_hp, luck, max_mana, dexterity) |
| `entities.py` | `Player`, `Enemy`, `Intent`, `IntentType`, `StatusEffect`, `deal_damage`, `status_stacks`, `enemy_hit_damage`, `vulnerable`, `frail`, `POISON`, `MARKED`, `WEAK`, `VULNERABLE`, `FRAIL`, `ENTANGLED`, `STRENGTH`, `BLADES`, `STATUS_TEXT` | Combat participants and their intents. `Player` carries `dexterity`, `attack_bonus`, `luck`. **Every hit on an enemy goes through `deal_damage(enemy, amount)`** (Marcado bonus, then block absorbs; returns HP lost) |
| `pile.py` | `DrawPile`, `DiscardPile`, `Hand` | Card containers with `count` and `is_full` |
| `gacha.py` | `PullKind`, `PULLS`, `PRICE_GROWTH`, `pull_price(kind, pulls)`, `tier_weight`, `pull_odds(kind, luck, tiers)`, `roll_pull(items, kind, rng, rarity_of, luck)` | Gachapón rules: normal / stellar pull odds and rising prices (see *Gachapón*) |
| `status_cards.py` | `spore()`, `mold()`, `make_status_card(id)`, `STATUS_CARD_FACTORIES` | Status cards enemies add to the piles for one combat (Espora, Moho) |
| `mana.py` | `Mana` | Mana resource with `spend`, `gain`, `refill`, `can_afford` |
| `combat.py` | `CombatState` | Single source of truth for the entire battle state. Effect helpers: `pick_random_enemy` / `hit_random_enemy` (every "al azar" effect; Moneda de la Suerte), `discard_from_hand` / `discard_random` (every effect discard: counts for Despojo, Rapiña hits), `kills_this_turn`, `spoil_ready`, `has_relic` |
| `map_node.py` | `MapNode`, `RoomType` | Single node on the run map: id, room_type, row, col, connections, visited, available |
| `game_map.py` | `GameMap` | Floor map: nodes dict, boss_id, rows, cols; `available_nodes()`, `mark_visited()` |
| `run.py` | `Run` | Persistent state across rooms: character, seed, floor, gold, hp, deck, relics, map; `add_card`, `add_relic`, `apply_combat_result` |
| `card_pool.py` | `PackTheme`, `PackDef`, `ALL_PACKS`, `starter_deck`, `CARD_CLASS_BY_ID`, `CARD_CLASS_LABEL`, `CardFactory`, `card_factories_for_theme(theme, classes=None)`, `card_factories_for_classes(classes)`, `class_for_character(id)`, `PACK_SIZE` | 4 card packs (ACERO/ESCUDO/MAGIA/EPICO), pack definitions with gold costs, `starter_deck(character_id)` (neutral 10-card deck; La Pícara: own 9-card deck — 4× Puñalada 6 dmg, 4× Esquiva 6 block, 1× Finta 1 mana 4 dmg + Combo +4 block); every pool card has a class (see *Card classes*) |

### Application layer — `src/application/`

| File | Public API | Responsibility |
|---|---|---|
| `relic_effects.py` | `extra_draw_per_turn`, `extra_attack_damage`, `bonus_starting_mana`, `try_spectral_shield`, `bonus_gold_reward`, `post_combat_heal`, `max_hp_bonus` | Pure query functions — read relics, return bonuses or mutate state |
| `play_card.py` | `play_card(state, card_index, target_enemy_index)` → `PlayResult`; `requires_target(card)`, `target_kind(card)` → `TargetKind` (`ENEMY` / `ALL_ENEMIES` / `SELF`) | Validate and execute playing a card from hand. Applies `player.attack_bonus` to attack damage and `player.dexterity` to block. `target_kind` tells the UI what a card will act on |
| `end_turn.py` | `end_player_turn(state)`, `draw_opening_hand(state)` | Full turn pipeline. Draw count = 5 + relic bonus (luck does not affect draws) |
| `gacha.py` | `gacha_price(run, kind)`, `can_pull`, `gacha_odds`, `pull(run, kind)` → `PullResult`, `accept(run, result)`, `decline(result)` | Pay and roll a gachapón relic (seeded by run seed + pull count); the hero then keeps or declines it |
| `card_preview.py` | `CardBonus(attack, block).for_card(card)`, `run_card_bonus(run)` (character + Pruebas + relics), `combat_card_bonus(state)`, `NO_BONUS` | The numbers a card shows **outside the hand** (rewards, packs, deck/pile viewers, El Brujo) = the same effective values as in combat. Every screen that shows a card must pass these bonuses |
| `luck.py` | `luck_report(run)` → `LuckReport` (luck now vs the character's own, relic sources, tier odds, golden chance per card/relic/pack, `rare_or_better()`, `gacha(kind, base=)`, `extra_card`, `summary()`), `golden_chance(kind, luck)`, `at_least(odds, tier)` | What luck does to every drop, for the screens that show it |
| `hero_stats.py` | `hero_sheet(run, state=None)` → `HeroSheet` (`stats: list[HeroStat]`, gold, floor, deck size/by type, relic count, golden card/relic and Épica+ odds, statuses, turn); `HeroStat(key, name, icon, value, base, sources, effect, current, reference)` with `bonus` and `breakdown()` ("Base 6 · Orbe de Fuego +2"); `StatSource(label, amount)` | Data of the hero sheet: per-relic contributions measured by calling each `relic_effects` query with that relic alone, "Pruebas" and "Este combate" (live `CombatState` values) as sources |
| `enemy_ai.py` | `BOSSES`, `FLOOR1_BOSSES`, `create_boss(ai, floor)`, `next_intent(enemy, player)`, `has_pattern`, `intent_hit_damage` | Pattern AI of the floor-1 bosses (see *Floor-1 bosses*) |
| `combat_manager.py` | `create_sample_combat()` → `CombatState` | Builds the sample battle (used for dev/testing), calls `draw_opening_hand` |
| `combat_factory.py` | `create_combat_for_character(character)` → `CombatState`; `create_combat_from_run(run, enemies)` → `CombatState` | Builds battles from a selected character or a live run; `create_combat_from_run` starts with no relics |
| `map_generator.py` | `generate_map(seed, floor)` → `GameMap` | Seeded map generation with **orthogonal-only edges** (horizontal = same row adjacent col; vertical = same col adjacent row). Rows = min(7 + (floor-1)//2, 12), cols = min(5 + (floor-1)//3, 8), paths = min(3 + (floor-1)//3, 6). Horizontal edges are bidirectional (player can walk sideways before ascending). Nodes with no upward connection are optional side rooms. |
| `run_manager.py` | `create_run(character, seed)` → `Run`; `generate_enemies`, `generate_boss`, `apply_combat_victory(run, hp, enemies, bonus_gold=0)`, `gain_gold(run, amount)` → interest (every gold *gain* goes through it: combat victories and events), `generate_event_gold`, `pick_treasure_relic`, `pick_treasure_relics` (2 with Llave Maestra), `pick_boss_relics`, `shop_price(run, base)`, `advance_floor` | Full roguelike run lifecycle: create, populate rooms, advance floors |
| `card_rewards.py` | `allowed_card_classes(run)`; `pick_reward_cards(run, room_id, count=3)` → `list[Card]`; `pick_pack_cards(run, theme, count=5)` → `list[Card]`; `lucky_cards(run, seed, exclude)` | Seeded card reward selection after combat and pack opening, filtered to the run's allowed classes (packs topped up from other themes if ever short), plus luck's "Cartas de la suerte" at the end (`Card.lucky_drop`). Seeds use `zlib.crc32(room_id)` (stable across runs) |

### Infrastructure layer — `src/infrastructure/`

| File | Responsibility |
|---|---|
| `colors.py` | Named `pygame.Color` constants for the entire project |
| `fonts.py` | `FontRegistry` — lazy font cache, keyed by point size |
| `viewport.py` | Screen scaling for the virtual 1280×720 canvas |
| `preferences.py` | `UserPreferences` dataclass (`show_fps: bool`); `load_preferences()` / `save_preferences()` — JSON persistence in `preferences.json` at project root |
| `dungeon_assets.py` | `load_dungeon_assets()` → `DungeonAssets` (cached once): pre-lit room pre-scaled to 1280×720, flame frames, 3 additive glow frames, `meta` from `assets/dungeon/dungeon.json`; `None` if files are missing |
| `card_assets.py` | `card_layout()` (zones from `assets/cards-v2/layout.json`), `card_frame(rarity, w, h)`, `pack_art(theme, height)`, `card_back(w, h)` (crystal back from `assets/Card Sprites/Card Back`), `card_illustration(card_id, card_type, w, h)` (`assets/cards-v2/art/<id>.png` or a provisional icon by type) — all cached; frames scaled with smoothscale |
| `enemy_sprites.py` | Animated enemy sheets from `assets/enemies/<id>_sheet.png/json` (written by `scripts/generate_enemy_sprites.py` and `scripts/generate_boss_*.py`). `ENEMY_SHEET_IDS` (name → id, `"Espectro"` → `wraith`, bosses → `mycelid`/`weaver`/`knight`), `BOSS_SHEET_IDS`; boss data on `EnemySheet`: `strike_seconds(anim)`, `animation_for_move(move_id, fallback)`, `is_boss`, `blade_frames`, `top`, `enemy_sheet_id`, `load_enemy_sheet(id)` (cached; cells scaled ×2 nearest) → `EnemySheet` (`size`, `anchor`, `animations`, `frames`, `frame(anim, elapsed)`, `seconds(anim)`), `sheet_for_enemy(name)`; `None` when missing |
| `ui_icons.py` | `ui_icon(name, scale=2)` (cached, nearest) / `has_ui_icon(name)` from `assets/ui/icons.png` + `icons.json` (written by `scripts/generate_ui_icons.py`): intent icons 18 px (`attack_1`…`attack_4`, `defend`, `buff`, `debuff`, `cards`, `unknown`, `lethal`), status/keyword icons 14 px (one per status, `status_buff`/`status_debuff` fallbacks, `block`, `junk_card`, `combo`, `singular`, `void`, `spoil`, `exhaust`, `ethereal`, `unplayable`, `damage`, `draw`, `mana`, `heal`); `None` when missing |
| `ui_kit.py` | HUD kit from `assets/ui/kit.png` + `kit.json` (written by `scripts/generate_ui_kit.py`): `kit_piece(name, scale=2)`, `kit_slice(name, w, h, scale=2)` (9-slice / 3-slice with **tiled** edges and centre, exact size, cached), `has_kit`, `kit_names`. Pieces: `panel`, `btn_{bronze,gold}_{idle,hover,press,off}`, `orb_back/frame/glass`, `orb_liquid_0..7`, `pile_draw/discard/empty`, `topbar`, `trim`, `ribbon` |
| `gacha_assets.py` | `load_gacha_assets()` → `GachaAssets` (cached, ×2 nearest): machine, glass overlay, crank frames, pile capsules, prize capsules per tier (drop size; stage size closed/top/bottom), coin, chute flap, `meta`; `point(name)` / `rect(name)` anchors; `None` when missing |
| `sprite_loader.py` | `SpriteLoader` — lazy nearest-neighbour cache for 32×32 PNG sprites from `assets/dungeon-crawl-stone-soup-full/`. `get_player_sprite(name, size=128, *, elapsed, animation="idle")` and `get_enemy_sprite(name, size=96)` look up by Spanish display name and return `pygame.Surface \| None`. Hero sheets (192 px + 96 px cells, picked by display size) per hero id: `HERO_IDS` (name → `warrior`/`mage`/`rogue`), `HEROES`, `hero_id_for(name)`, `has_hero_sprites(name)`, `get_player_animation_frames(anim, size, hero)`, `hero_animation_seconds(anim, hero)`, `hero_strike_seconds(hero)` (attack time until the blade connects, from the sheet's `events.attack.strike_frame`; 0 when absent), `IDLE_CYCLE_SECONDS` (shared 1.6 s); warrior aliases `HERO_CELL`, `HERO_SHEETS`, `HERO_ANIMATIONS` |

### Presentation layer — `src/presentation/`

| File | Responsibility |
|---|---|
| `scenes/main_menu_scene.py` | Main menu: Jugar/Continuar, Ajustes, Pruebas, Salir. Sets `requested_action: MenuAction`. Drawn with the kit: baked dungeon room (`DungeonBackdrop`) + smooth vignette, the three heroes idling on the floor, glowing gilded title + ribbon subtitle, iron panel with 330×48 kit buttons (gold = selected with pointing arrows and glow, bronze = rest, one icon each), key caps, fade-in from black |
| `scenes/settings_scene.py` | Settings screen: toggle "Mostrar FPS" (Activado/Desactivado). Mutates `UserPreferences` in-place; sets `cleared: bool`. SceneManager saves to disk on exit |
| `scenes/character_select_scene.py` | Character panel grid with stat bars; seed text input (click to focus, type digits). Sets `confirmed` / `back_to_menu`; exposes `seed: int` property |
| `scenes/combat_scene.py` | Main battle screen: input, layout, hover, tooltip dispatch (hovering an intent or a status badge shows just that: `_detail_at`/`_detail_tooltip`; `_incoming_damage()` feeds the lethal glow and the HP preview; `_announce_actions` fills the enemy action banners at end of turn). `is_boss` constructor param; `combat_won` property; `state` property. Hand fan (`_hand_layout`, `CardPose`) with tweened card motion, hover zoom, draw-pile fly-in and discard fly-out; card play through `CardPlayInput` (drag / click / keys), targeting arrow and reticles |
| `scenes/death_scene.py` | Death screen: Nueva Partida / Menú Principal. Sets `requested_action: DeathAction` |
| `scenes/map_scene.py` | STS-style node map. Signals `selected_node: MapNode \| None` |
| `scenes/combat_reward_scene.py` | Gold display + 3 card choices after a non-boss combat. Signals `cleared: bool`, `chosen_card: Card \| None` |
| `scenes/treasure_scene.py` | Show one relic or several (Llave Maestra): click a box to pick, take or skip. Accepts a `Relic` or `list[Relic]`. Signals `cleared: bool`, `took_relic: bool`, `chosen_relic: Relic \| None` |
| `scenes/shop_scene.py` | 3 relics + 3 packs; prices via `run_manager.shop_price` (Máscara del Ladrón). Signals `selected_pack: PackTheme \| None`, `cleared: bool` |
| `scenes/pack_opening_scene.py` | Animated opening (intro → idle float → click → charge with imploding sparks → tear: flash, shake, top strip flies off, particle explosion, light rays → cards dealt face-down → flipped one by one with rarity bursts; rare+ get an anticipation glow, legendary gold confetti) then 5-card pick-1 with rarity halos/sparkles and an outro for the chosen card. Any click/Space skips the animation. Ctor kwargs `theme` (PackTheme value, picks pack art + colours) and `seed`. `phase`, `is_animating`, `skip_animation()`, `choose(i)`. Signals `cleared: bool` (after the outro), `chosen_card: Card \| None` |
| `scenes/gacha_scene.py` | Gachapón room: two pull buttons with live prices, odds table, and the show (coin → crank → drop → present → open → reveal → collect) with pooled particles. `start_pull(kind)`, `advance()`, `skip_to_reveal()`, `phase`, `result`. Signals `cleared` |
| `scenes/event_scene.py` | Spanish narrative + gold pickup "Recoger" button. Signals `cleared: bool` |
| `scenes/boss_reward_scene.py` | 3-phase boss reward: gold → epic pack → relic choice. Signals `cleared: bool`, `open_pack_requested: bool`, `chosen_relic: Relic \| None` |
| `ui/card_widget.py` | `draw_card(…, bonus_damage=0, bonus_block=0)`, `draw_card_at(surface, card, center, fonts, *, scale, angle, …, outline)` (free placement: scale quantised to 5 %, tilt rotated once and cached) and `render_card_surface(…)` — cards-v2 rarity frame + illustration + dynamic text (cost, name, effect lines, ATK/DEF with effective values); each visual state cached (LRU 256) |
| `ui/card_play.py` | `CardPlayInput`, `Mode`, `PlayRequest` — pygame-free Slay the Spire style card-play state machine: pick, drag, aim, release, sticky click, keyboard (1–9, ←/→/Tab, Enter), cancel (right click / ESC) |
| `ui/targeting.py` | `draw_arrow(surface, start, end, *, hot, phase)` chevron arrow (pure curve helpers `control_point`, `sample_curve`, `segment_placements`, `head_placement`; cached pre-rotated pixel sprites) and `draw_reticle(surface, rect, color, t)` |
| `ui/entity_widget.py` | `draw_player(…, incoming_loss=, t=, hitboxes=)`, `draw_enemy(…, framed=True, intent_damage=, lethal=, t=, hitboxes=)` (`framed=False`: no body panel, used by animated enemies). STS-style intent `draw_intent` (big icon — the sword grows with total damage — + number "4×3" + small extra icons; red glow + skull when `lethal`), `intent_number`, `intent_extras`, `intent_label` (text fallback); status badges = icon + stacks (`status_rects`); block = shield with number on the HP bar (blue rim); hero HP bar blinks the HP the coming attacks take + "−N" chip. `hitboxes` gets `"intent"` and `"statuses"` rects for hover |
| `ui/glossary.py` | Keyword glossary: `Term` (name, rule, icon, colour), `STATUS_TERMS`, `KEYWORD_TERMS`, `EXHAUST`/`ETHEREAL`/`UNPLAYABLE`/`SHIELD`, `terms_in(texts, exclude=, include_shield=)`, `status_icon`, `status_term`; shared text colours (`KEYWORD` gold, `DAMAGE` red, `BLOCK` blue, `POISON_INK` green, `MANA`) |
| `ui/rich_text.py` | Colour-coded rule text: `spans(text, base)`, `render_lines(text, font, max_w, base)` (wrapped, cached), `render_line` — "N de daño"/"N de vida" red, escudo/bloqueo blue, maná light blue, Veneno green, glossary terms gold. Used by tooltips, card faces and banners |
| `ui/action_banner.py` | `ActionBanners` (one per acting enemy, stacked at y 372, fade in / hold 2.1 s / fade out) and `describe_action(name, intent, action)` → (icon, "Caballero Hueco usa Danza de Espadas", "2 golpes · pierdes 3 de vida · …") |
| `ui/dungeon_backdrop.py` | `DungeonBackdrop(seed, budget)` — combat background: one blit of the baked room, flickering torches (flame animation + additive glow), particles for embers, window rain + sill splashes, ceiling drips, moonbeam dust. `update(dt)`, `draw(surface)`, `particle_count`; `budget` scales particles (0 = off) |
| `fx/particles.py` | `EmitterConfig`, `ParticleSystem` — reusable pooled particles (parallel lists, swap-remove, dt clamp), gravity/wobble/colour-over-life, streak trails, clip rect, `floor_y` + `burst` into an `on_floor` child system, `prewarm()` |
| `fx/bursts.py` | `BurstParticles` — pooled one-shot particles in screen px, each with its own palette/size/drag/gravity and style (`SQUARE`, `SPARK` streak, `GLOW` additive): `emit`, `burst` (radial), `implode` (ring → centre), `update`, `draw`; `soft_glow(color, radius)` cached additive light, `scaled(color, k)` |
| `fx/enemy_animator.py` | `EnemyAnimator(sheet, seed, phase)` — one animated enemy: `play(name, delay=, hits=)`, `strike_times(anim, hits)`, `style` (`EnemyFxStyle` from `STYLES[sheet_id]`: palettes and cue points per enemy), `blades`/`target` (floating swords of the Caballero Hueco, thrown one per hit during `command`) (attack/hurt/cast/death; death latches), `update(dt)`, `draw(surface, anchor)` (floor shadow, pulsing additive floor glow, frame, own pooled particles: ambient wisps, claw sparks at `strike_time()`, ectoplasm on hurt, implode + rune motes on cast, soul motes while dissolving), `action`, `busy`, `dead`, `death_done` |
| `fx/card_fx.py` | "Ready" effect for cards whose keyword condition holds (Combo, Singular, Vacío, Despojo): `ready_keywords(card, combo, singular, void, spoil)`, `READY_STYLES` (label, colour, light, icon per keyword), `draw_ready_back` (breathing aura behind; colours cycle when several are ready), `draw_ready_front` (comets running round the edge with trails, corner flares, bobbing "¡COMBO!" badge with icon; follows tilt and scale), `perimeter_point`, `comet_positions`, `current_color`. Shapes no chroma uses, so it reads on top of the golden sheen/halo/motes |
| `ui/luck_badge.py` | `draw_luck_badge(surface, anchor, pos, report, fonts)`, `luck_line(report)` — kit plate "Suerte N ▲ · Rara o mejor X % · dorada Y % · carta extra Z %" (green when relics raise luck); shop, pack opening, card reward |
| `fx/hero_fx.py` | `HeroFx(strike, seed)` — code-drawn hero only: `play(action, delay=)`, `update(dt)`, `draw_shadow(surface, center)` (before the sprite), `draw(surface, center)` (pooled particles: blade sparks at `strike`, dust kick, ward shards, ember burst on hurt, rising gold on cast, dust when kneeling in death) |
| `fx/sprite_animation.py` | `SpriteAnimation` — time-based frames with per-frame durations, loop or hold, start offset |
| `ui/gold_hud.py` | `GoldHud` (one instance in `SceneManager`): plate + spinning pixel coin + big outlined amount that counts towards the real gold, `+N`/`−N` labels, sparkles and border flash on change; `sync`, `update(dt, amount)`, `draw(surface, anchor, pos)`, `rect`; `format_gold`, `DEFAULT_POS` |
| `ui/hud_widget.py` | Kit-drawn combat HUD: `draw_relics` (iron slots, rarity rim, hover lift), `draw_mana(…, orb=)`, `draw_pile_widget(…, hovered=)` (card-back stack + count badge, `PILE_W/PILE_H`), `draw_end_turn_button(…, hovered, pressed, enabled, ready, t)` (gold button, hourglass, key E; pulses when `ready`, "TURNO ENEMIGO" when disabled), `draw_turn_counter` (red ribbon) |
| `ui/pixel_ui.py` | Kit widgets: `draw_panel`, `draw_button(surface, rect, label, fonts, *, style="bronze"/"gold", state, icon, key, t, glow, size)` (hover lift + light sweep, press sinks, glow aura), `button_state`, `draw_keycap`, `draw_topbar`, `draw_trim`, `draw_ribbon`, `outlined`; `ManaOrb` (`update(dt, mana)`, `error()`, `draw`): liquid cut at the mana level with a moving crest, splash + drops on spend, glow + motes on refill, shake + red rim when a card can't be paid |
| `ui/hero_sheet.py` | `HeroSheetOverlay(sheet, fonts)` — "Héroe" screen: animated hero portrait, name, HP bar, statuses; one row per stat (icon, big number, base/bonus bar with pips, sources, sentence); tiles for gold, floor, deck (bar per type), relics, turn. Bars fill one after another and spark. `fill(i)`, `closed` (Esc, C, X, click outside) |
| `ui/tooltip.py` | Multi-panel tooltips (STS style): `TooltipContent(title, lines, icon, subtitle, tag, accent, panels)` + `TooltipPanel(title, lines, icon, color, tag, key)`; `all_text()`. Lines may start with `[[icon]]`; lines starting with two spaces are dim notes. `card_tooltip` (keyword panels with "¡Activo!", Agotar/Injugable/Etérea, modifiers, chroma), `enemy_tooltip(enemy, hit, player)` (intent panel + one panel per status), `intent_tooltip`, `intent_lines` (hits, total, Fuerza/Débil/Vulnerable breakdown, block absorbed, lethal), `status_tooltip`/`status_panel` (duration of timed hero debuffs), `player_tooltip(player, incoming)`, `relic_tooltip`, `pile_tooltip`, `mana_tooltip`; glossary panels added for every term mentioned. `draw_tooltip(…, beside=rect)` renders the stack once (cached by content), 2 columns when too tall, kept on screen; returns its rect |
| `ui/pile_viewer.py` | Modal overlay for browsing a pile's cards |

---

## BigValue Arithmetic

`BigValue` stores a `base: int` and an ordered list of `Operation` steps.

**Resolution formula (exact integer arithmetic, no floats):**
```
chips  = base + Σ(all "+" ops)
result = chips × Π(all "×" ops)
```

This mirrors Balatro's Chips × Mult model. Python `int` is arbitrary-precision — values like 10^1000 are computed exactly.

### Builder API (each call returns a new BigValue)

```python
BigValue(6)                                   # resolve → 6
BigValue(6).add_flat(4)                       # chips=10 → 10
BigValue(6).add_multiplier(2)                 # chips=6, mult=2 → 12
BigValue(6).add_flat(4).add_multiplier(2)     # chips=10, mult=2 → 20
BigValue(4).add_multiplier(2)                 # → 8  (Chroma Fuego pattern)
BigValue(10).merge(BigValue(5).add_mult(3))   # resolved(10)+5=15, ×3 → 45
```

### Key invariants

| Expression | Result | Why |
|---|---|---|
| `BigValue(n).add_flat(0).resolve()` | `n` | Adding 0 is identity |
| `BigValue(n).add_multiplier(1).resolve()` | `n` | Multiplying by 1 is identity |
| `BigValue(n).add_multiplier(0).resolve()` | `0` | Zero multiplier collapses everything |
| `BigValue(0).add_multiplier(10**100).resolve()` | `0` | Zero base × anything = 0 |

### format_int suffixes

| Range | Suffix | Example |
|---|---|---|
| < 10³ | (none) | `999` |
| ≥ 10³ | K | `1.5K` |
| ≥ 10⁶ | M | `2.0M` |
| ≥ 10⁹ | B | `1.0B` |
| ≥ 10¹² | T | `1.0T` |
| ≥ 10¹⁵ | Q | `1.0Q` |
| ≥ 10¹⁸ | E | `100.0E` |

Values above 10¹⁸ still display correctly (e.g. 10^1000 → `"...E"`).

---

## Relic System

Relics are stored in `CombatState.relics: list[Relic]`. Each `Relic` carries a `tag: RelicTag | None` that identifies its mechanic. Effects are computed on-demand by pure functions in `src/application/relic_effects.py` — there are no callbacks, observers, or hidden side-effects.

### Four relics in the sample combat

| Name | Tag | Effect | When applied |
|---|---|---|---|
| Amuleto de Combate | `COMBAT_AMULET` | +1 mana maximum permanently | `draw_opening_hand()` at combat start |
| Tótem Roto | `BROKEN_TOTEM` | +1 card drawn per turn | `draw_opening_hand()` and `_begin_player_turn()` |
| Orbe de Fuego | `FIRE_ORB` | +2 flat damage on every attack played | `play_card()` when `card.total_damage() > 0` |
| Escudo Espectral | `SPECTRAL_SHIELD` | Survive a fatal hit at 1 HP (one-time use) | `_execute_intent()` after ATTACK damage |

### Four relics from the roguelike run

| Name | Tag | Effect | When applied |
|---|---|---|---|
| Piedra de Energía | `ENERGY_STONE` | +1 card drawn per turn (stacks with BROKEN_TOTEM) | `draw_opening_hand()` and `_begin_player_turn()` |
| Anillo de Oro | `GOLD_RING` | +15 gold after each combat | `apply_combat_victory()` in run_manager |
| Corazón de Hierro | `IRON_HEART` | +15 max HP (applied when relic is acquired) | `pick_treasure_relic()` / `pick_boss_relics()` |
| Poción de Sangre | `BLOOD_POTION` | Heal 8 HP after each combat | `post_combat_heal()` in run_manager |

### How to add a new relic

1. Add a new variant to `RelicTag` in `src/domain/relic.py`.
2. Add a query function in `src/application/relic_effects.py`.
3. Call it at the right point in `end_turn.py` or `play_card.py`.
4. Pass any UI hint (`bonus_damage`, etc.) from the scene to the widget/tooltip.
5. Add the relic to `create_sample_combat()` in `combat_manager.py`.
6. Write tests in `tests/test_relic.py`, `tests/test_relic_effects.py`, and the relevant use-case test file.

---

## Turn Pipeline

```
draw_opening_hand(state)         ← called once at combat start
  ├── random.shuffle(draw_pile)
  ├── COMBAT_AMULET: mana.maximum += 1; mana.refill()
  └── _draw_cards(5 + extra_draw_per_turn(relics))

end_player_turn(state)           ← called each time player ends their turn
  ├── _discard_hand()            discard all hand cards
  ├── _run_enemy_turn()          block still active — absorbs enemy damage
  │     ├── _execute_intent() for each living enemy
  │     │     └── ATTACK: apply damage → try_spectral_shield()
  │     └── _roll_intent()       random new intent for next turn
  └── _begin_player_turn()
        ├── state.player.block = 0  ← block resets at START of new turn
        ├── state.turn += 1
        ├── state.mana.refill()
        └── _draw_cards(5 + extra_draw_per_turn(relics))
```

**Block rule:** Block resets to 0 at the **start of the player's next turn**, after enemies have already acted. Block gained during the player's turn **does** absorb enemy attacks that same turn.

---

## Character System

Three playable characters are defined in `src/domain/character.py`. Each has five stats that map to
Player fields and affect combat calculations:

| Stat | Player field | Effect |
|---|---|---|
| `damage` | `attack_bonus` | Flat bonus added to every attack card's effective damage |
| `max_hp` | `max_hp` / `current_hp` | Starting and maximum HP |
| `luck` | `luck` | Better drop odds: golden cards/relics/packs and higher relic tiers (see Luck & rarity) |
| `max_mana` | `mana.maximum` | Starting mana pool (before COMBAT_AMULET adds 1) |
| `dexterity` | `dexterity` | Flat bonus added to every block card's effective block |

The three characters (La Guerrera / El Mago / La Pícara) differ in these values so each offers a different playstyle.

### Scene flow

```
MainMenuScene
  → [Jugar]      → CharacterSelectScene
                      → [confirm]  → create_run() → MapScene
                                       → [COMBAT]    → CombatScene
                                                          → [combat_won] → CombatRewardScene → MapScene
                                                          → [death]      → DeathScene
                                                                               → [Nueva Partida] → CharacterSelectScene
                                                                               → [Menú]          → MainMenuScene
                                       → [TREASURE]  → TreasureScene → MapScene
                                       → [SHOP]      → ShopScene
                                                          → [pack]       → PackOpeningScene → ShopScene → MapScene
                                       → [EVENT]     → EventScene → MapScene
                                       → [BOSS]      → CombatScene(is_boss=True)
                                                          → [combat_won] → BossRewardScene
                                                                               → [open_pack]  → PackOpeningScene → BossRewardScene
                                                                               → [cleared]    → advance_floor() → MapScene
                      → [ESC]      → MainMenuScene
  → [Ajustes]    → SettingsScene → MainMenuScene (saves preferences on exit)
  → [Salir]      → quit
```

`SceneManager` in `main.py` stores `_run: Run | None` and `_prefs: UserPreferences`, and drives all transitions. After each
`update()` call it inspects the top scene's flags and pushes/pops scenes accordingly. Flags are
reset immediately after being consumed.

---

## Roguelike Run System

A full roguelike run persists state across rooms via the `Run` domain object and the `run_manager` / `map_generator` use cases.

### Run object (`src/domain/run.py`)

`Run` is the single source of truth for everything that survives between rooms:

| Field | Type | Description |
|---|---|---|
| `character` | `Character` | Selected character (immutable after run start) |
| `seed` | `int` | RNG seed for deterministic map and reward generation |
| `floor` | `int` | Current floor (starts at 1, increments after boss) |
| `gold` | `int` | Current gold amount |
| `player_max_hp` | `int` | Maximum HP (can increase from relics) |
| `player_current_hp` | `int` | Current HP (persists across rooms) |
| `deck` | `list[Card]` | Full card collection (draw pile is rebuilt from this each combat) |
| `relics` | `list[Relic]` | Acquired relics (active from the moment they are added) |
| `current_map` | `GameMap` | The current floor's node map |
| `current_room_id` | `str \| None` | ID of the room the player is currently in |
| `gacha_pulls` | `int` | Gachapón pulls made this run (every pull raises the next price) |
| `interest_earned` | `int` | Gold paid by Interés Compuesto this run (the manager notes the growth on the gold counter) |
| `last_interest` | `int` | Interest paid by the latest `gain_gold` (0 if none; reward screens show it) |

Mutation methods: `add_card(card)`, `add_relic(relic)`, `apply_combat_result(hp_after)`.

### Seeded map generation (`src/application/map_generator.py`)

`generate_map(seed, floor) → GameMap` produces a deterministic crossword-style map:

- **Seed formula**: `6364136223846793005 × seed + 1442695040888963407 × floor`
- **Dimensions**: rows = `min(7 + (floor-1)//2, 12)`, cols = `min(5 + (floor-1)//3, 8)`
- **Paths**: `min(3 + (floor-1)//3, 6)` independent paths from row 0 to boss row
- **Orthogonal edges only**: horizontal edges connect same-row adjacent-column nodes (bidirectional); vertical edges connect same-column adjacent-row nodes (directed upward).
- When a path shifts column it adds a horizontal edge in the current row, then ascends vertically. The pre-boss row walks horizontally to `boss_col` before the final vertical step.
- Horizontal neighbours become available when any adjacent node in their row is visited — the player can walk sideways before ascending. Nodes with no upward connection are optional side rooms that can be skipped.
- Mid-rows receive TREASURE, SHOP, and EVENT nodes; all other non-boss rooms are COMBAT

### Room types (`src/domain/map_node.py`)

| `RoomType` | Scene | Outcome |
|---|---|---|
| `COMBAT` | `CombatScene` | Fight enemies → `CombatRewardScene` (pick 1 of 3 cards, earn gold) |
| `TREASURE` | `TreasureScene` | Take or skip a free relic |
| `SHOP` | `ShopScene` → `PackOpeningScene` | Spend gold to buy a card pack (pick 1 of 5 cards) |
| `EVENT` | `EventScene` | Narrative event with gold reward |
| `BOSS` | `CombatScene(is_boss=True)` | Fight boss → `BossRewardScene` (gold + epic pack + relic choice) |
| `WARLOCK` | `WarlockScene` | Upgrade cards for gold (one per floor) |
| `GACHA` | `GachaScene` | Pay for random relics; prices rise with every pull (one per floor) |

### Card packs (`src/domain/card_pool.py`)

Four pack themes are available in the shop. Each pack shows 5 cards; the player picks 1.

| `PackTheme` | Cost | Focus |
|---|---|---|
| `ACERO` | 75 gold | Attack cards |
| `ESCUDO` | 75 gold | Block / defense cards |
| `MAGIA` | 75 gold | Special / utility cards |
| `EPICO` | 150 gold | High-power mixed cards |

`starter_deck()` returns the initial 10-card deck used when creating a new run.
`card_factories_for_theme(theme)` returns a list of zero-argument callables that produce the cards belonging to that theme — used by `pick_pack_cards()`.

### Chromas — golden cards and relics (`src/domain/chroma.py`)

Generic system: `Chroma` enum + `ChromaDef` registry (`CHROMA_DEFS`). Only
`GOLDEN` exists: `effect_multiplier=2`, `card_drop_chance=0.05`,
`relic_drop_chance=0.08`, Spanish notes (`card_note`, `relic_note`,
`short_note`) and an optional `on_card_played(state, card)` hook for future
chromas with unusual behaviour. `Card.chroma` / `Relic.chroma` (None = normal).

* Cards: printed stats stay normal; the card is **cast `card.casts()` times**
  (golden: twice). `play_card` pays once, then `_resolve_cast` runs each full
  cast (damage + attack bonuses, block + dexterity, mana, every `on_play`,
  draws, combo layer), then the chroma hook. It counts as one card played.
  `PlayResult` carries per-cast snapshots (`cast_hits`, `cast_enemy_hp`,
  `cast_enemy_block`, `cast_player_block`). `CombatScene` **replays** the casts:
  the card flies to a stage (`_CAST_STAGE`), each cast fires `_CAST_GAP` apart
  (hero attack, hit number, HP/block drawn step by step via `_shown_enemies`,
  gold burst, "Lanzamiento k/n", "¡x2!"), then lingers `_CAST_OUTRO`. While
  `presentation_busy`, input is ignored and `combat_won`/`death_occurred` wait,
  so a kill is seen before victory (any normal killing blow also holds
  `_KILL_HOLD`). The face shows
  "DORADA  x2"; the tooltip note says it is cast 2 times.
* Relics: every numeric `relic_effects` bonus is multiplied (`_sum`); the
  Spectral Shield gets `effect_multiplier()` charges (`Relic.times_triggered`).
* Drops: `roll_chroma(rng, for_relic=…)` on reward/pack cards (own rng, so the
  offered cards do not change) and on treasure/boss/shop relics.
* UI: `src/presentation/fx/chroma_fx.py` (`STYLES` per chroma) — gilded frame and
  "DORADA" plate baked into the card face, sweeping sheen + twinkles + pulsing
  halo on cards (`draw_card`, `draw_card_at`, pack reveal) and `draw_chroma_box`
  for relic bar, relic viewer, shop, treasure and boss reward. Titles use
  `chroma_title` ("Golpe · Dorada"); tooltips add the note. The legacy
  `ModifierTag.CHROMA` placeholder is unrelated and unused by this system.

### Golden packs

`PackDef.chroma` (shop offers roll `roll_chroma(kind="pack")`). A pack's
`effect_multiplier` is how many cards you keep: golden = pick 2
(`PackOpeningScene(chroma=…)`, `chosen_cards`; "Terminar" keeps what was picked).
The pack art is gilded with sheen and motes, titled "Sobre de X · Dorado".

### Keywords (`src/domain/keywords.py`)

Hearthstone-style named rules: `Keyword` + `KEYWORD_DEFS` (name, rule text).
**Combo** (Rogue cards only): `CardEffect.combo` is an extra layer that resolves
when `CombatState.cards_played_this_turn > 0` (`combo_active`; reset each player
turn, incremented by every successful `play_card`). `Card.total_*(combo=True)`,
`active_effects(combo)`, `keywords()`; `combo_text(card)` describes the layer.
`play_card` returns `PlayResult.combo`. UI: card face line "Combo: +5 de daño." /
"¡Combo activo!" (numbers in green), tooltip rule, teal pulsing silhouette aura on
ready cards in hand and a floating "¡COMBO!" on the hero. 17 rogue cards have Combo
(`_add_combo` in `card_pool.py`).

### Pruebas / tuning (`src/domain/tuning.py`)

`TUNING` (defaults = normal play) holds test knobs: chroma drop chances per kind
(`chroma_chances["golden:card"|"golden:relic"|"golden:pack"]`, generic per
chroma), `all_class_cards`, `starting_gold`, `gold_multiplier`, `invincible`,
`extra_mana`, `extra_draw`, `extra_max_hp`. Edited in the **Pruebas** screen
(main menu → `DevSettingsScene`, rows generated in `_rows()`), saved to
`dev_settings.json` by `infrastructure/dev_settings.py` (loaded at startup,
invalid values fall back). `tests/conftest.py` resets it for every test.

### Card classes (`CardClass` in `src/domain/card.py`)

Every card has `card_class`: `NEUTRAL` (all classes), `WARRIOR`, `MAGE` or `ROGUE`
(values match `CharacterId`). Class and pack theme are independent axes. The
class of each pool card is set in `CARD_CLASS_BY_ID` (`card_pool.py`); unmapped
cards and the starter deck are neutral. Rule kept by tests: in every theme,
neutral + any single class ≥ `PACK_SIZE` (5).

A run finds only `allowed_card_classes(run)` = neutral + its own class + the
classes of its active relics' `Relic.card_classes` (`relic_effects.unlocked_card_classes`).
A pool-mixing relic is just a `Relic(..., card_classes=frozenset({CardClass.MAGE}))`
(or all three classes). The card tooltip shows "Clase: …".

---

## Playing Cards (Slay the Spire style)

Input lives in `ui/card_play.py` (`CardPlayInput`, no pygame) and `CombatScene` executes the
returned `PlayRequest`. What a card acts on comes from `target_kind(card)`:
one **enemy** (damage or `needs_target`) → drag out of the hand to show the chevron arrow
(`ui/targeting.py`) and release on an enemy; **all enemies** (`hits_all_enemies`) or the
**hero** → release above the hand line (`_PLAY_LINE_Y`). A quick click holds the card for a
second click; right click / ESC cancel; keys 1–9, ←/→/Tab, Enter/Space, E. Mark new area cards
with `hits_all_enemies=True` so every enemy gets the reticle. See docs/visual-design.md.

## Card Rendering

Cards use the **cards-v2** frames (`assets/cards-v2/frames/card_<rarity>.png`), chosen by
`card.rarity` (never by type). Layers: type-tinted backdrop + illustration clipped to the
frame's transparent window → dark discs under the see-through circles → frame → text
(mana top-left, name on the plate, effects on the dark panel, attack bottom-left, block
bottom-right; boosted values in green). Zones come from `layout.json`
(`scripts/measure_card_frames.py`). Real illustrations go in `assets/cards-v2/art/<card id>.png`.
The shop shows `packs/pack_<theme>.png` via `pack_art()`.


`draw_card()` in `card_widget.py` accepts `bonus_damage: int = 0`. The number shown in the card centre is always the **effective** value: `card.total_damage() + bonus_damage`.

The combat scene computes `bonus_damage` via `relic_effects.extra_attack_damage(state.relics)` for any card with `total_damage() > 0`, then passes it to both `draw_card()` and `card_tooltip()`.

`card_tooltip()` shows a breakdown when the bonus is non-zero:
```
Inflige 16 de daño a un enemigo.
  (14 + 2 del Orbe de Fuego)
```

`relic_tooltip()` appends `Estado: Activo` or `Estado: Agotado` so the player can see whether a one-time relic has already triggered.

---

## Test Suite

Run with: `uv run pytest tests/ -v`

One test file per source module. All test files follow the same structure:
1. Module-level docstring explaining scope and stress philosophy.
2. Imports.
3. Helper functions / fixtures (no pytest fixtures — plain functions).
4. `class Test<Topic>:` groups, one per concept.
5. `def test_<specific_case>(self):` methods with a single `assert`.

### Test files

| Test file | Module under test | Key areas covered |
|---|---|---|
| `test_numbers.py` | `domain/numbers.py` | resolve, flat/mult chains, 10^1000, 2^200, 1000-op chains, merge, format, display |
| `test_card.py` | `domain/card.py` | total_damage, total_block, stacking, modifiers, draw field, is_broken |
| `test_relic.py` | `domain/relic.py` | RelicTag enum (all 8 values), Relic creation, defaults, is_active mutation |
| `test_character.py` | `domain/character.py` | CharacterStats, Character frozen fields, ALL_CHARACTERS count and invariants |
| `test_entities.py` | `domain/entities.py` | is_alive (Player+Enemy), hp_ratio, dexterity/attack_bonus/luck defaults |
| `test_pile.py` | `domain/pile.py` | DrawPile/DiscardPile count, Hand count, is_full, max_size, mutations |
| `test_mana.py` | `domain/mana.py` | can_afford, spend, gain (capped), refill, boundary values, large amounts |
| `test_combat.py` | `domain/combat.py` | CombatState defaults, field storage, mutations, no-pygame-dependency |
| `test_map_node.py` | `domain/map_node.py` | RoomType enum, MapNode fields, connections, visited/available flags |
| `test_game_map.py` | `domain/game_map.py` | GameMap fields, available_nodes, mark_visited, boss_id |
| `test_run.py` | `domain/run.py` | Run creation, add_card, add_relic, apply_combat_result, field storage |
| `test_card_pool.py` | `domain/card_pool.py` | PackTheme enum, ALL_PACKS count/costs, starter_deck size, card_factories_for_theme |
| `test_relic_effects.py` | `application/relic_effects.py` | All 8 relic functions: active, inactive, two of same, relic without tag |
| `test_play_card.py` | `application/play_card.py` | Validation, damage, Fire Orb, attack_bonus, block, dexterity bonus, mana, draw, target kind (enemy / all enemies / self, pool area cards) |
| `test_end_turn.py` | `application/end_turn.py` | draw_opening_hand, end_player_turn, relic integration, STS block rule, luck draw |
| `test_combat_manager.py` | `application/combat_manager.py` | Structural integrity, relic tags, mana=4/4, hand=6, card pool total |
| `test_combat_factory.py` | `application/combat_factory.py` | Player stats from character, full HP enemies, mana setup, luck-based draw |
| `test_map_generator.py` | `application/map_generator.py` | Determinism, row/col/path counts per floor, room type distribution, boss placement, orthogonal-only edges, bidirectional horizontal, upward-only vertical |
| `test_run_manager.py` | `application/run_manager.py` | create_run, generate_enemies, generate_boss, apply_combat_victory, advance_floor |
| `test_card_rewards.py` | `application/card_rewards.py` | pick_reward_cards count, pick_pack_cards theme filtering, seeded determinism |
| `test_preferences.py` | `infrastructure/preferences.py` | defaults, load (present/missing/invalid JSON), save, round-trip, unknown keys ignored |
| `test_sprite_loader.py` | `infrastructure/sprite_loader.py` | mapping completeness, all asset files exist on disk, unknown-name → None, cache empty on unknown |
| `presentation/fx/test_particles.py` | `fx/particles.py` | spawn rate, capacity, budget, lifetime, dt clamp (10^9), 10 000-step stress, gravity, landing bursts, determinism, clip, trails |
| `presentation/fx/test_bursts.py` | `fx/bursts.py` | emit/burst/implode shapes, lifetime, gravity, drag, dt clamp, swap-remove, 10 000-step stress, drawing of each style, glow cache |
| `presentation/scenes/test_pack_opening_scene.py` | `scenes/pack_opening_scene.py` | phase order, open by click/Space, rare anticipation timing, skip at any moment, outro then cleared, single choice, every theme draws every phase, empty pack, 10 000 random updates |
| `presentation/fx/test_sprite_animation.py` | `fx/sprite_animation.py` | frame timing, looping, hold, offsets, invalid input |
| `infrastructure/test_dungeon_assets.py` | `infrastructure/dungeon_assets.py` | files exist, metadata anchors/palettes, pre-scaling, single load |
| `presentation/ui/test_dungeon_backdrop.py` | `ui/dungeon_backdrop.py` | room drawn, torches animate, budget 0, fallback, cost bound, combat integration |
| `infrastructure/test_card_assets.py` | `infrastructure/card_assets.py` | layout rarities/zones/packs, files exist, frame size & cache, pack aspect, placeholders |
| `presentation/ui/test_card_play.py` | `ui/card_play.py` | pick, drag threshold, play line boundary, aim/target, release/click, sticky, keyboard cycle/confirm, cancel, 10 000-move stress |
| `presentation/ui/test_targeting.py` | `ui/targeting.py` | curve ends, bend, spacing, growth, flow period, head, colours, blit count, sprite cache bound, reticle |
| `test_enemy_sprite_generator.py` | `scripts/generate_enemy_sprites.py` (stdlib) | 5 animations, actions end on idle 0, idle motion and loop, fits the cell, dissolve 0/1, death empty, flash, lunge, 100 random poses, sheet files match |
| `infrastructure/test_enemy_sprites.py` | `infrastructure/enemy_sprites.py` | registry, files, ×2 scale/anchor, cache, idle wrap, death hold at 10^9 s, fallback, actions end on idle 0 |
| `presentation/fx/test_enemy_animator.py` | `fx/enemy_animator.py` | play/queue/return to idle, death latch, cues (hurt splash, strike sparks), ambient, dt clamp, 10 000-step stress, drawing |
| `presentation/scenes/test_combat_enemy_animation.py` | `CombatScene` + animated enemies | animators per sheet, hurt/death on hits, victory waits for death, attack/cast by intent, stagger, hero flinch at strike, 100-turn stress |
| `test_warrior_code_generator.py` | `scripts/generate_warrior_code_sprites.py` (stdlib) | 6 animations, 1.6 s idle, actions end on idle 0, short actions, held kneel, strike frame, idle motion/loop, planted boots, sole row, height, blink, reach, one connected mass (no seams), kneeling hides the boots, sweep helpers (connected, zero width, 10^9 offset), red hair, 100 random poses, sheet meta, legacy copy kept |
| `presentation/fx/test_hero_fx.py` | `fx/hero_fx.py` | cue timing per action, strike wait, kneel dust, delay queue, no cues before draw, dt clamp, 10 000-step stress, shadow |
| `presentation/scenes/test_combat_hero_animation.py` | `CombatScene` + code-drawn warrior | HeroFx only for her, cast on skills, enemy reacts at blade contact, death held and defeat screen waits |
| `test_hero_rogue.py` | rogue sheets in `sprite_loader.py` + `CombatScene` | same contract as the mage, both rogue names |
| `test_hero_mage.py` | mage sheets in `sprite_loader.py` + `CombatScene` | name→hero mapping, 192/96 sheets, idle motion, planted boots, actions end on idle 0, shared idle clock, attack trigger |
| `application/test_floor1_bosses.py` | `enemy_ai`, `status_cards`, boss parts of `end_turn`/`play_card`/`drawing`, `generate_boss` | status math, multi-hit + block per hit, extras, Panacea, hero Veneno/Enredado/timed debuffs, Frágil, Espora/Moho, patterns, enrage once, Banquete per debuff, swords cap, seeded boss choice, Pruebas overrides, 300-turn stress |
| `test_boss_sprite_generators.py` | `scripts/generate_boss_*.py`, `scripts/pixel_kit.py` | Espectro art contract per boss, strike events, move → animation, sword strip, kit (gapless strokes, dissolve, PNG) |
| `presentation/scenes/test_combat_bosses.py` | boss sheets, `EnemyAnimator` styles/swords, `CombatScene` boss slot | loader extras, styles, strike times, sword count/throw/re-form/death, big slot, move clip, cards added, one number per hit, hero waits for the first sword, unplayable card, 60-turn stress |
| `application/test_gacha.py` | `domain/gacha.py`, `application/gacha.py` | prices (growth, rounding, shared counter, Máscara, 10^3 pulls), odds (sum 1, stellar never Común and better, luck, subsets), roll distribution, paying, refusing, determinism, no duplicates until the pool is empty, max HP, stellar golden boost |
| `presentation/ui/test_readability.py` | `ui_icons`, `scripts/generate_ui_icons.py`, `rich_text`, `glossary`, tooltips, `entity_widget` intents/badges, `action_banner`, `CombatScene` hover | every icon exists (one per status), generator = assets, colours (damage/block/keyword/poison/mana/HP), terms found in order without repeats, intent sentences (multi-hit totals, modifiers, block absorbed, lethal, extras), panels not repeated, timed debuff duration, card keyword/flag panels, renderer on screen / 2 columns / beside a card, intent number/extras/hitboxes, banner texts and lifecycle, hover intent / hero status / enemy status, banner after end turn |
| `presentation/ui/test_hud_kit.py` | `ui_kit`, `scripts/generate_ui_kit.py`, `pixel_ui`, HUD widgets, `hero_stats`, `hero_sheet`, SceneManager/CombatScene wiring | pieces + generator = assets, exact 9/3-slice sizes, tiling keeps corners, buttons in every style/state, mana orb (sync, splash, easing, flash, shake, max 0, 10^9 dt stress), End Turn variants, piles, stat bases/relic sources/golden relic/inactive/Pruebas/live combat/odds/huge luck/deck by type, sheet fill order/closing/phases/stress, C key + button + Escape order + overlay guard, End Turn locked while enemies act, orb shakes on unaffordable card |
| `presentation/ui/test_card_ready_and_preview.py` | `card_preview`, reward/pack/pile screens, `fx/card_fx`, card widgets, `MainMenuScene` | hero/relic/Pruebas bonuses = combat hand, per-card rule, no run, 10^100, screens wired; ready keywords only for layers the card has, colour cycling, comets on the edge/moving/tilted, badge position, golden + ready drawn together, combat hand; menu buttons, no overlap, click/keys, fade-in, 1000-frame stress |
| `application/test_luck.py` | `application/luck`, lucky cards in `card_rewards`, `rarity.lucky_card_*`, luck badge, screens | report with/without the Trébol, sources, monotonic, huge luck capped; the Trébol makes pack/reward cards rarer and more golden, shop packs golden, gachapón odds and pulls better (60 seeds); lucky-card chances 0/50/100/200/300/10^9, count range, Trébol guarantees one, Rara+, no duplicates, allowed classes, deterministic, rare for base heroes; badge text/anchor; shop/gachapón/reward/pack draw with luck and marks |
| `presentation/ui/test_gold_hud.py` | `ui/gold_hud.py` + `SceneManager` | format, sync, counting time, +N/−N labels and expiry, flash/spin, anchors, 10 000-step stress; manager sync on new run, map position, change animates, hidden without run |
| `presentation/scenes/test_gacha_scene.py` | `scenes/gacha_scene.py`, `gacha_assets.py`, `scripts/generate_gacha_sprites.py` | assets, generator contract, phase order, skip, auto-open, keys/buttons, poor/busy refusals, exit, keep/decline (mouse, R, Enter), vortex, thunk, lightning, focus, shockwave, drop path, shakes per tier, screen shake, confetti, every phase drawn per tier, 10 000-step stress |
| `test_hero_idle.py` | hero sheet in `sprite_loader.py` + `CombatScene` | sheet slicing, whole-number scaling, planted idle boots, actions ending on idle frame 0, time-based frame selection, attack/guard/hurt triggers |

### Testing rules

- **Boundary values**: always test 0, 1, exact limit, limit+1, and huge numbers (10^9, 10^18, 10^1000).
- **Inactive relics**: test separately from active ones.
- **Combinations**: two of the same relic, mixed active/inactive.
- **No mocks**: instantiate domain objects directly — they have no side effects.
- **No pygame**: domain and application layers are pygame-free; tests must import without errors.
- **Concrete assertions**: assert exact values, not just `assert result.success`.
- **Stress tests**: include at least one test per file that operates at large scale (100+ iterations, 10^100+ values).

## Visual art and animation — required

Read [docs/visual-design.md](docs/visual-design.md) and
[docs/code-drawn-sprites.md](docs/code-drawn-sprites.md) before visual changes. Last Wish uses
**detailed pixel art and dungeon fantasy** with strong warm/cold lighting, native pixels shown
×2 (same grain as the baked room).

**La Guerrera is drawn by code** (user request, 2026-09-30: the illustrated version did not
match the pixel art). `scripts/generate_warrior_code_sprites.py` (stdlib) uses the Espectro
technique literally: the whole figure is ONE silhouette scanned row by row (`body_mass`,
`Body.extents`), with hair, face, armour, tabard, ponytail, cape and boots painted as zones
inside it; only the sword and the sword arm are drawn on top (rimmed, like the Espectro's
sleeve). Animation deforms the mass (offset, lean, squash, nod, wind, `kneel`). Two earlier
versions built from pieces (capsules/IK, then stacked limb sweeps) were rejected — never draw
characters by parts. A `Pose` gives dx/dy, lean, sx/sy, nod, kneel, boot x positions, sword hand
and angle, hair/cape phase and wind, eyes and effects. Look kept from the approved
design: red ponytail and bangs, green eyes, gold circlet, silver plate with gold trim, crimson
tabard, dark-teal cape, leather boots, long sword. Output: `warrior_sheet_96.png` (native 96 px
cells), `warrior_sheet.png` (×2, combat) and `warrior_sheet.json` (with
`events.attack.strike_frame`). Animations: `idle` (16 × 100 ms, boots fixed), `attack` (wind-up,
lunge, warm slash; blade connects on frame 3), `guard` (upright blade, blue ward), `hurt`,
`cast` (raised glowing sword, for skills/powers) and `death` (falls to one knee on the planted
sword; held). The previous illustrated sheets are kept in `assets/characters/warrior_illustrated/`
(`generate_warrior_sprites.py` now writes there; mage and rogue still import its helpers).

`CombatScene` plays `attack` for damage cards, `guard` when block is gained, `cast` for other
cards, `hurt` when HP is lost and `death` on a lethal hit (`death_occurred` waits for it plus
`_DEATH_HOLD`; nothing interrupts it). With the code-drawn hero, enemies react (number, hurt,
death) only when the blade connects (`hero_strike_seconds`), her hit/block show only numbers
(flash baked), and `HeroFx` adds the shadow and particles. Regenerate, inspect
`output/guerrera-preview.gif`, and run `tests/test_hero_idle.py`,
`tests/test_warrior_code_generator.py` with the full suite.

**El Mago** and **La Pícara** follow the same pipeline: `<hero>-source.png` →
`scripts/make_hero_base.py <hero>` (one-time: background removal of the dark
vignette, per-hero protected thin parts and halo peeling, ×8 reduction with an
accent-preserving palette) → `<hero>_base.png` (128×192) →
`scripts/generate_<hero>_sprites.py` (stdlib) → `<hero>_sheet*.png/json`. Mage: pulsing
crystal with motes, arcane bolt, rune circle. Rogue: dagger glints, shadow dash
with after-images and crossed slash, smoky side-step. New heroes: add a source drawing, a base conversion, a generator reusing
the shared helpers, and an entry in `HERO_IDS`.

**Environments:** `scripts/generate_dungeon_assets.py` (stdlib) builds the dungeon
pack in `assets/dungeon/` — reusable wall/floor/ledge blocks, window, torch
bracket, banner, chain, 6 flame frames, glow frames — and **bakes the lighting**
of a room layout (`ROOMS`) into `room_combat.png` (640×360, shown ×2). Runtime
never lights pixels: `DungeonBackdrop` blits the baked room once per frame and
adds only moving things (flames, glow via `BLEND_RGB_ADD`, particles). Keep new
effects in `fx/` reusable and pooled; measure with `scripts/bench_backdrop.py`.

## Animated enemies — "Espectro" (code-drawn, approved method)

The user asked for this enemy to be drawn **by code from scratch** and approved the result as
**the method for new enemies**: read [docs/code-drawn-sprites.md](docs/code-drawn-sprites.md)
(method, lessons, timing table, checklist) and preview with `scripts/preview_enemy_sheet.py <id>`.
Heroes other than La Guerrera (also code-drawn, see above) still come from illustrations. `scripts/generate_enemy_sprites.py`
(stdlib) draws a hooded wraith at native pixel size (cell 128×104, anchor (80, 96) on the
ground) from shaded shapes with a fixed palette and ordered dither: violet cloak with
upper-left light and folds, shoulder capelet, hem fraying into 7 waving teal strands, void
hood with slanted glowing eyes, pulsing soul flame, rusty chest chain and broken shackle,
bony claws in bell sleeves. Each frame is a `Pose` fed to one renderer:
`idle` (12-frame hover loop), `attack` (wind-up, lunge left with a triple claw-slash arc),
`hurt` (white flash, knock-back), `cast` (arms up, rune circle) and `death` (recoil, eye
flare, bottom-up dissolve with motes; ends empty). Non-death actions end on idle frame 0.

Runtime: `infrastructure/enemy_sprites.py` loads the sheet (×2), `fx/enemy_animator.py`
plays it with its own particles. `CombatScene` creates an animator for every enemy whose
name is in `ENEMY_SHEET_IDS`, draws it unframed (`draw_enemy(framed=False)`) at
`(rect.centerx, rect.bottom + 6)`, and drives it: HP loss → `hurt` (number only, no red
rect: the flash is baked), kill → `death` (`combat_won` waits on `enemies_dying`), end
turn → `attack` for ATTACK intents and `cast` otherwise, staggered 0.14 s per enemy; the
hero's `hurt` and hit number are delayed until the first claws land (`strike_time()`).
"Espectro" is in `run_manager.generate_enemies` templates (42 HP, attacks 11, floor-scaled).
New animated enemy: add a renderer/poses (or reuse the script), a sheet id in
`ENEMY_SHEET_IDS`. Preview: `output/espectro-preview.gif`.

## Floor-1 bosses (2026-10-07)

Three bosses, each with its own identity, drawn by code with the Espectro method
(`docs/code-drawn-sprites.md` §11) and driven by a readable pattern AI
(`application/enemy_ai.py`). Numbers and move tables: `docs/game_design.md` → *Jefes*.

| Boss (`ai`) | Identity | Sheet / generator | Clips beyond the five basics |
|---|---|---|---|
| Reina Micélida (`micelida`) | Toxic cards (Espora, Moho) + Veneno | `mycelid` / `generate_boss_mycelid.py` | `spores` |
| La Tejedora (`tejedora`) | Debuffs; Banquete bites once more per distinct debuff | `weaver` / `generate_boss_weaver.py` | `feast` (3 bites), `web` |
| Caballero Hueco (`caballero`) | Multi-hit; floating swords = `Espadas` stacks | `knight` / `generate_boss_knight.py` (+ `knight_blade.png`) | `double`, `command` |

**Rules engine**
- `Intent` gained `hits`, `move`, `move_id`, `block`, `debuffs`, `buffs`, `cards`,
  `description` (defaults keep the old `Intent(type, value)` behaviour). `end_turn._execute_intent`
  resolves the main action (ATTACK hits `hits` times through `_enemy_attack`: Señuelo, block per
  hit, Contraataque per fully blocked hit, death saves), then block → buffs → debuffs (Panacea
  blocks them) → status cards (`CombatState.add_status_cards(id, n, "draw"|"discard"|"hand")`).
  Named BUFF/DEBUFF moves skip the generic behaviour. Each enemy's turn is logged in
  `CombatState.enemy_log` (`EnemyAction`: index, move, HP lost per hit, cards, debuffs).
- Per-hit damage = `entities.enemy_hit_damage`: value + Fuerza, ×0.75 Débil (enemy),
  ×1.5 Vulnerable (hero).
- Hero statuses: Veneno ticks at the start of your turn (`_poison_hero`, ignores block,
  Pruebas invincible respected); Débil/Vulnerable/Frágil tick at the end of your turn
  (`HERO_TIMED_DEBUFFS`); Enredado is spent on the next turn's draw; Frágil reduces card block.
- Status cards (`CardType.STATUS`, `domain/status_cards.py`): `Card.unplayable`, `exhaust`
  (played → `CombatState.exhausted`), `ethereal` (fades at end of turn), `on_draw`
  (`drawing.draw_one`), `on_turn_end_in_hand` (`_discard_hand`). They live only in the
  combat piles. Art: `scripts/generate_status_card_art.py` → `assets/cards-v2/art/status_*.png`.
- `Enemy.ai/ai_step/ai_used/is_boss/floor`. Bosses roll with `enemy_ai.next_intent` (others keep
  `_roll_intent`). Each has a one-shot move at ≤50 % HP (`_enraged`).
- `run_manager.generate_boss`: floor 1 → `floor_boss_ai(run)` (seeded; `TUNING.forced_boss`
  1–3 fixes it); later floors keep the Señor de la Cripta. `TUNING.boss_rooms` turns every
  combat room into the floor boss. Both are rows in the Pruebas screen (right column).

**Presentation**
- `CombatScene`: a boss with a `boss` sheet stands in `_BOSS_*` (centre 905, ground 314, width
  230); `_boss_rect` puts the name and intent above the sprite's top (`EnemySheet.top`). End of
  turn plays `sheet.animation_for_move(move_id, attack|cast)` with `hits`, shows one damage
  number per hit at its `strike_times` (leftover = Veneno), the hero flinches at the first one,
  and `_announce_extras` floats the debuffs and status cards ("+2 Espora", feedback line).
  The scene copies `Espadas` into the knight's animator every update.
- Intent bubble: `entity_widget.intent_label` ("ATQ 5x3", "+DEB", "+CARTAS", "+BLQ"), width
  fits the text, per-hit damage after modifiers. `enemy_tooltip(enemy, hit_damage)` shows the
  move name, description and numbers; status lines include `STATUS_TEXT`.
- Previews: `uv run --with pillow scripts/export_boss_previews.py` → `output/boss-<id>-preview.gif`.

## Gachapón (2026-10-07)

A room (`RoomType.GACHA`, "Gacha", one per floor, placed after El Brujo in a middle row,
avoiding the shop's row when possible) with a code-drawn gachapon machine that sells random
relics. Rules in `domain/gacha.py`, use cases in `application/gacha.py`, screen
`scenes/gacha_scene.py`, art `scripts/generate_gacha_sprites.py` → `assets/gacha/`.

- **Two pulls.** *Tirada normal* (base 80): the usual relic tier weights 50/28/14/6/2.
  *Tirada estelar* (base 190): never Común, weights 0/40/34/18/8, double golden chance
  (chroma luck `2·luck + 10`). Luck lifts high tiers in both (`tier_weight`, same formula as
  `rarity_weight`). Tiers with no relic left in the pool drop out (`roll_pull`).
- **Rising prices.** `price = base × 1.5^Run.gacha_pulls` (rounded to 5), the counter is shared
  by both pulls and lasts the whole run; Máscara del Ladrón discounts it (`shop_price`).
- **Paying rolls the relic** (`pull`: gold, counter, relic from `_relic_pool`, chroma); the
  reveal then offers **Quedármela** (Enter / button → `accept` → `acquire_relic`) or
  **Rechazar** (R / button → `decline`: nothing is added, the gold is not returned, the price
  still rises; the relic stays in the pool). Owned relics come back only when the pool is empty
  (`PullResult.duplicate` → "¡Repetida!").
- **Show:** the room darkens around the machine (cached vignette, `_focus`) → a big coin flies
  from the gold counter into the slot (sparks, shockwave ring, every bulb flashes) → the crank
  turns three times, accelerating, with a squash pulse per quarter turn; the machine leans in
  (zoom) and shakes harder; the capsules lift into a whirling vortex (`_swirl`, depth-sorted);
  two searchlights sweep from the crown; electric arcs crackle on the glass (real tier-coloured
  lightning for Épica+, plus a tease implosion); the glowing prize sinks through the vortex →
  KA-CHUNK (`THUNK_AT`): the machine hops, screen shake, shockwave, burst at the chute → the
  capsule pops out (sparks, ring), bounces twice (dust rings), hops to the stage (sparkle trail
  for Poco común+) → presented in a
  tier halo, shaking once per tier step; click / Space / 6 s → flash, halves fly apart, burst
  sized by tier, rotating rays for Rara+, screen shake for Épica+, gold confetti for
  Legendaria → name, tier, description (golden note), Quedármela / Rechazar → the relic flies
  to the relic counter, or crumbles into grey dust (`discard`). Clicks skip ahead (not past the
  decision). Keys 1 / 2 pull. Static surfaces are cached.
- Pruebas: "Todas las salas: gachapón" (`TUNING.gacha_rooms`) opens the machine from every
  combat room. Preview: `uv run --with pillow scripts/export_gacha_preview.py` →
  `output/gacha-preview.gif`.

## Gold counter (2026-10-07)

`ui/gold_hud.GoldHud`, owned by `SceneManager` (`gold_hud` property), is drawn on every run
screen (same rule as the pause button: a run exists and the top scene is not menu/selection/
settings/Pruebas/death). It syncs silently when a new run starts and animates every change, so
gold won in a fight counts up on the reward screen and gacha/shop purchases count down. A scene
picks the spot with `gold_hud_pos = (anchor, (x, y))` (default top right `(1268, 12)`): map
`("topright", (1048, 11))` next to "Ver mazo", combat `("topleft", (12, 476))` above the mana
orb, Brujo `("bottomright", (1268, 708))`; `show_gold_hud = False` hides it. The old small
"Oro: N" labels (map header, shop, gachapón, Brujo title) were removed. Tests:
`tests/presentation/ui/test_gold_hud.py`.

## Run pause and abandonment

`SceneManager` in `main.py` owns a `PauseMenu` overlay
(`src/presentation/ui/pause_menu.py`). During a run, the visible `Pausa · Esc`
button or Escape opens it in map, combat, shop, event and reward screens. Next to it the
hero button (`stats_button_rect`, key **C**) opens `HeroSheetOverlay` (`SceneManager.open_hero_sheet`,
`hero_sheet` property; live combat values when the top scene is a `CombatScene`); while open,
room updates stop and every event goes to it.
Existing collections/held cards consume Escape first. The button's place comes from `pause_button_rect(scene)` (`pause_menu.py`): `PAUSE_BUTTON` by default, a scene's own `pause_button_rect` when its top bar is busy (combat: `(460, 16, 64, 36)`, between the relic bar and the turn ribbon; Brujo `(78, 652, 64, 36)`; both buttons are 64×36 kit buttons with an icon and their key cap, and show their name on hover), and hidden while a collection overlay is open. The pause button cancels
held combat input. While paused, room updates and transitions stop and all input
goes to the overlay; shared audio still updates. Mouse and keyboard are supported.

`Reanudar` keeps the exact run and scene stack. `Abandonar partida…` opens a
confirmation with Cancel selected by default. Only explicit confirmation clears
`_run` and replaces the stack with a fresh `MainMenuScene` using shared audio.
This discards the current run; it is not a save/suspend feature. The existing main
menu `Salir` action closes the application. Tests: `tests/test_pause_menu.py`.

---

## Luck & rarity (`src/domain/rarity.py`)

Cards and relics share **five tiers**: Común, Poco común, Rara, Épica, Legendaria
(`Rarity`; `CardRarity` is an alias). Relic tiers live in `RELIC_RARITY`:

| Tier | Relics |
|---|---|
| Común | Poción de Sangre, Anillo de Oro, Amuleto de Vitalidad |
| Común | Saco de Trapos (Pícara), Bolsa de Dagas (Pícara), Máscara del Ladrón |
| Poco común | Corazón de Hierro, Orbe de Fuego, Broche de Evasión, Cuchillo Arrojadizo, Pañuelo del Duelista, Garfio, Vaina Afilada, Frasco de Veneno (Pícara); Moneda de la Suerte, Herradura de Plata |
| Rara | Tótem Roto, Piedra de Energía, Cinta Roja, Bolsillo Roto, Colmillo de Víbora (Pícara), Guante de Seda, Botas Silenciosas |
| Épica | Amuleto de Combate, Hilo de Araña, Llave Maestra, Interés Compuesto |
| Legendaria | Escudo Espectral, Trébol de Siete Hojas, Ankh, Espejo Singular, Panacea, Fuente Eterna, Daga Partida (Pícara), Reloj Roto |

Luck = `run.character.stats.luck` (Guerrera 2, Mago 5, Pícara 8). It no longer draws cards.

- **Relic tier odds**: `weighted_sample` picks a tier by weight, then a relic of that tier
  (treasure, boss reward, shop). Weight = `BASE_RARITY_WEIGHT[tier] × (1 + 0.10 × luck × (tier − 1))`,
  base 50/28/14/6/2. Common never changes; each higher tier grows faster.
- **Chroma odds**: `roll_chroma(..., luck=)` multiplies every drop chance (cards, relics,
  packs) by `1 + 0.10 × luck`, capped at 100 %. Pruebas overrides are multiplied too.
- **Card tiers**: card rewards and packs also use `weighted_sample` (tier first, then a card
  of that tier), with the same weights. `CardFactory.rarity` exposes each factory's tier (cached).
- **Pruebas**: `Tuning.extra_luck`, `extra_damage`, `extra_dexterity` (+ the old `extra_max_hp`,
  `extra_mana`, `extra_draw`) form the "Stats del héroe" column of the Pruebas screen, with a live
  preview of each hero's odds. Luck everywhere = `tuning.hero_luck(character luck)`
  (`run_manager.run_luck(run)` for runs, which also adds `relic_effects.luck_bonus`). Shift multiplies a step by 10.
- There is **no cap** on luck. Golden chances hit 100 % at luck 115 (relics), 157 (packs) and
  190 (cards). Tier odds tend to Común 0 % / Poco común 34 % / Rara 34 % / Épica 22 % /
  Legendaria 9.8 % as luck grows.
- UI: relic tooltip shows `Rareza: …`; HUD relic border uses the card rarity colour
  (`card_widget.RARITY_COLOR`); player tooltip shows luck.

---

## Class relics and combo relics

`Relic.relic_class` (default `CardClass.NEUTRAL`) says who can find a relic: neutral relics
for every hero, class relics only for that hero (`run_manager._relic_pool`, used by treasure,
boss reward and shop). The relic tooltip shows "Solo para …" for class relics.

| Relic | Tag | Class | Tier | Effect (golden x2) |
|---|---|---|---|---|
| Amuleto de Vitalidad | `VITALITY_AMULET` | Neutral | Común | +10 max HP (`max_hp_bonus`) |
| Trébol de Siete Hojas | `SEVEN_LEAF_CLOVER` | Neutral | Legendaria | +100 luck (`luck_bonus`) |
| Interés Compuesto | `COMPOUND_INTEREST` | Neutral | Épica | Every gold gain (`run_manager.gain_gold`) adds 10 % of the total gold after the gain, rounded down (golden 20 %); the interest itself earns none (`compound_interest_percent`) |
| Espejo Singular | `SINGULAR_MIRROR` | Neutral | Legendaria | On pickup: removes repeated cards, one copy of each kept (golden copy preferred) |
| Ankh | `ANKH` | Neutral | Legendaria | Fatal hit: revive at full HP, once (golden: twice) (`try_ankh`) |
| Broche de Evasión | `EVASION_BROOCH` | Pícara | Poco común | A card's Combo resolves: +1 block |
| Cuchillo Arrojadizo | `THROWING_KNIFE` | Pícara | Poco común | A card's Combo resolves: 1 damage to a random living enemy (block absorbs) |

Pickup effects: every relic is obtained through `run_manager.acquire_relic(run, relic)` (treasure,
boss reward, shop), which recomputes max HP and applies one-time effects (Espejo Singular →
`relic_effects.remove_duplicate_cards`). It only cleans the deck once; later copies stay.

Death saves: `end_turn` calls `relic_effects.try_revive(state)` after each enemy hit, which tries
Escudo Espectral first (1 HP) and then the Ankh (full HP), so the stronger save is kept.

Combo relics trigger from `relic_effects.on_card_played(state, card, combo)`, called by
`play_card` once per play (not per golden cast) right after the last cast, so their effect is
part of the last cast's snapshots/hits. They only trigger when the card's Combo layer actually
resolved (`combo=True`: another card was already played this turn), never on the first card.

---

## Keyword Singular (`src/domain/keywords.py`)

`Keyword.SINGULAR` ("Singular: efecto extra si tu mazo inicial no tiene cartas repetidas").
Works like Combo: an extra layer `CardEffect.singular` (helper `card_pool._add_singular`),
`Card.singular_effects()`, and every `total_*` / `active_effects` takes `singular=`.

- "Mazo inicial" = the deck a combat starts with. `deck_is_singular(cards)` (no two cards
  with the same `id`; a golden copy is a repeat) sets `CombatState.singular_deck` once in
  `create_combat_from_run` / `create_combat_for_character`; it never changes mid-combat.
- `CombatState.singular_ready(card)`; `play_card` resolves the layer on every cast and
  reports `PlayResult.singular`. Unlike Combo it also works on the first card of the turn.
- UI: `card_widget` (`singular=`, violet aura `SINGULAR_READY_GLOW`, "¡Singular activo!"),
  `card_tooltip(singular_active=)`, "¡SINGULAR!" floating text in combat.
- Starter decks have repeats; the Espejo Singular relic is the way to thin the deck.

---

## Game design list (`docs/game_design.md`)

Living list (in Spanish) of keywords, cards and relics: planned (⏳) and implemented (✅).
When a card, relic or keyword is added or renamed, update its row there too.

---

## Keyword Vacío (`Keyword.VOID`)

"Vacío: efecto extra si al jugarla te quedas con 0 de maná." Mage cards only (by design;
none exist yet). Same layer pattern as Combo/Singular: `CardEffect.void`, `Card.void_effects()`,
`void=` on every `total_*` / `active_effects`, helper `card_pool._add_void`.

- `keywords.void_triggers(cost, mana_before)`: `cost > 0 and mana_before - cost == 0`
  (a free card never triggers it). `CombatState.void_ready(card)` checks it with the current mana.
- `play_card` decides it **before** paying; the layer resolves on every cast; `PlayResult.void`.
- UI: blue aura `VOID_READY_GLOW` (Combo > Vacío > Singular), "¡Vacío activo!", "¡VACÍO!" text.

---

## Card upgrades and El Brujo

- `Card.upgrade_level`, `Card.max_upgrades` (default 1; `None` = unlimited), optional
  `Card.upgrade: CardUpgrade` (deltas for cost/damage/block/draw/mana_gain, optional new
  `on_play`/`text`, `description`), `Card.base_name`; `Card.is_upgraded` is a property.
- `src/domain/card_upgrade.py`: `can_upgrade`, `default_upgrade` (+3 or +1/3 dmg/block; else
  -1 cost; else +1 draw), `apply_upgrade` (in place; renames "X+", "X+2"…), `upgraded_preview`,
  `describe_upgrade`.
- `src/application/warlock.py`: `UPGRADE_PRICE` by rarity (50/75/100/150/200),
  `upgrade_price(card)` = base × (level + 1), `can_buy_upgrade`, `buy_upgrade(run, index)`.
- Map: `RoomType.WARLOCK` ("Brujo"), exactly one per floor (`map_generator` phase 3, after events).
- `scenes/warlock_scene.py`: deck grid (`CollectionViewer` subclass with prices, "Salir"),
  confirmation panel (card now → upgraded preview, "Mejorar (precio)" / "Cancelar"). The panel is
  exposed as `_overlay` so Escape closes it. `CollectionViewer` gained `close_label`,
  `footer_text`, `hint_text`, `close_on_outside_click`.

---

## Combat mechanics added for La Pícara's cards

- `CombatState.card_cost(card)`: printed cost minus `next_card_discount` (this turn, used up by
  the next card played) and `first_card_discount` (power, first card of each turn). Used by
  `play_card`, `void_ready`, and the combat UI (`draw_card_at(..., cost=)`, green when cheaper).
- `CombatState.next_damage_bonus` (Afilar): added to the next card that deals damage; expires at
  end of turn. `combo_always` (Danza de Sombras) makes `combo_active` always true.
- `CardEffect.on_turn_start` (powers): run by `end_turn._trigger_powers` at the start of each of
  your turns, once per cast (golden: twice).
- `Card.play_on_draw` (token "Daga Oculta", `card_pool.hidden_dagger()`): `application/drawing.py`
  (`draw_one` / `draw_cards`, shared by turn draws and card draws) plays it for free when drawn.
- Status "Débil" (`entities.WEAK`, `weakened`, `add_status`, `tick_status`): −25% attack damage.
  On enemies it lasts their next action; enemy DEBUFF intent makes the hero Débil for 2 turns
  (`end_turn.ENEMY_DEBUFF_TURNS`) unless they have Panacea (`relic_effects.immune_to_debuffs`).
- Fuente Eterna: `relic_effects.max_mana_per_turn` added to `mana.maximum` in `_begin_player_turn`.
- `CardEffect.text` is shown on the card face and tooltip; every on_play card now has one.
- Rogue cards live in `_ROGUE_ACERO/_ESCUDO/_MAGIA/_EPICO` in `card_pool.py` (helper `_r`).


---

## Keyword Despojo and La Pícara expansion (2026-10-04)

**Design rule (user):** a keyword *is* the condition. A keyword layer never adds a second
condition ("Combo: si además…" is not allowed). `tests/application/test_rogue_expansion.py`
checks that no keyword layer text contains " si ". Rogue relics only touch her themes
(Combo, Despojo, daggers, poison); anything else is neutral.

**Despojo** (`Keyword.SPOIL`, "Despojo: efecto extra si ya descartaste una carta este turno.").
Same layer pattern as Combo/Singular/Vacío: `CardEffect.spoil`, `Card.spoil_effects()`, `spoil=`
as 4th flag on every `total_*` / `active_effects`, helper `card_pool._add_spoil`,
`CombatState.spoil_ready(card)`, `PlayResult.spoil`, orange aura `SPOIL_READY_GLOW`
(Combo > Despojo > Vacío > Singular), "¡Despojo activo!", floating "¡DESPOJO!".
`CombatState.discards_this_turn` counts discards made by effects through
`discard_from_hand` / `discard_random` (Golpe Desesperado, Rodar, Deshacerse, Vaciar
Bolsillos, Bolsillo Roto, Nada que Perder); the end-of-turn discard does not count. Reset in
`end_turn._reset_turn_counters` with the other per-turn counters.

**Engine pieces added**
- `CombatState.pending_draws`: callbacks (domain, cannot call `draw_cards`) ask for draws;
  `play_card._resolve_cast` and `end_turn._trigger_powers` draw them right after.
- Powers that change rules for the combat set a field when played: `discard_damage` (Rapiña),
  `daggers_on_draw` (Maestra de Dagas), `double_combo` (Sombra Gemela), `echo_every_fifth`
  (Cadena Perfecta: extra casts → `PlayResult.casts`, replayed like golden casts),
  `execute_threshold` (Asesina, `relic_effects.execute_wounded`), `turn_rummages` (Nada que
  Perder). Fortuna Audaz uses `on_turn_start`.
- Per-turn fields: `spoils_this_turn`, `attacks_this_turn`, `double_combo_used`, `decoys`
  (Señuelo, `end_turn._redirect_to_decoy`), `counter_damage` (Contraataque), `retain_block`
  (Capa de Sombras), `turn_start_alive` + `pickpocket_gold` (Carterista →
  `relic_effects.settle_pickpocket` → `CombatState.gold_earned`, added by
  `apply_combat_victory(..., bonus_gold=state.gold_earned)` in `main.py`), `last_random_target` /
  `lucky_coin_used` (Moneda de la Suerte).
- `play_card._resolve_layers`: re-resolves keyword layers with printed values (Sombra Gemela,
  Daga Partida). `_cast_target` retargets a living enemy when the target died mid-play.
- Status **Marcado** (`entities.MARKED`, Marcar Objetivo): +stacks per hit in `deal_damage`;
  cleared at the end of your turn. Poison uses `entities.POISON` and `add_status`.
- `end_turn._after_hand_drawn` (opening hand and each turn): Bolsillo Roto, then Nada que Perder.
  `draw_opening_hand` also adds Bolsa de Dagas daggers and Botas Silenciosas draws.
- `relic_effects`: `on_card_played(state, card, combo, rng=None, *, spoil=False)` (Combo relics +
  Saco de Trapos, Garfio), `combo_scarf_bonus`, `split_dagger_repeats`, `dagger_pouch_count`,
  `torn_pocket_rummages`, `poison_on_attack` (Frasco de Veneno, Hoja Envenenada), `spread_poison`
  (Colmillo de Víbora; called after plays, poison deaths and turn start), `execute_wounded`,
  `settle_pickpocket`, `try_broken_clock` (per-combat charges in `CombatState.clock_uses`),
  `spider_thread_block`, `opening_extra_draw`, `combat_gold_multiplier`, `shop_price`,
  `treasure_choices`; `luck_bonus` includes Herradura de Plata.
- Cinta Roja lives in `CombatState.combo_active` (turn 1) and Guante de Seda in `card_cost`
  (third card of the turn is free), both through `has_relic`.
- Luck in combat: `card_pool.lucky_crit_chance(luck)` (Corte Afortunado) and
  `lucky_roll_count(luck)` (Tirar los Dados).

Every new card, relic and status is listed in `docs/game_design.md`.

## Readable cards and intents (2026-10-07)

Rule text and enemy actions follow the card-game conventions (Slay the Spire,
Monster Train, Hearthstone): **one picture per rule, used everywhere**, colour-coded
numbers, and a glossary panel for every keyword.

- Icons: `scripts/generate_ui_icons.py` → `assets/ui/icons.png/json` (code-drawn,
  ramps + upper-left light + dark outline, shown ×2). New status → add its icon in the
  generator, its entry in `glossary._STATUS_ICON` / `_STATUS_KIND` and its rule in
  `entities.STATUS_TEXT`; tooltips, badges and card text pick it up automatically.
- Intent: icon + number ("4×3"), sword size by total damage (`tooltip.attack_icon`:
  <8, <16, <26, more), extra icons for block / buff / debuff / junk cards, red glow and
  skull when the attacks coming this turn kill the hero. Hover the intent → its tooltip.
- Status badges: icon + stacks; hover one → its rule (and, on the hero, how many turns).
- Tooltips: main panel + one panel per status/keyword/status card mentioned; text
  colour-coded by `rich_text` (also on card faces and banners).
- Hero HP bar blinks the HP the coming attacks will take ("−N" after the bar); the
  hero tooltip says the incoming damage.
- Enemy turn: one banner per acting enemy ("Reina Micélida usa Lluvia de Esporas —
  1 golpe · pierdes 6 de vida · mete 2 Esporas en tu pila de robo").

## Pixel-art HUD and hero sheet (2026-10-07)

User: the HUD (End Turn, pause/Esc, mana, piles…) did not match the game; wanted pixel
art with effects, and a way to see the hero's stats that is easy to read.

- Art: `scripts/generate_ui_kit.py` → `assets/ui/kit.png/json` (iron panel, bronze and
  gold buttons in 4 states, mana orb parts + 8 liquid frames, card piles, top bar, gold
  trim, ribbon) and new icons in `generate_ui_icons.py` (gear, helmet, bag, hand_cards,
  clover, tower, hourglass, deck, coin). Same rules as every sprite: native px ×2, ramps,
  upper-left light, dither, dark outline. Stretchable pieces tile, never stretch.
- Combat: kit top bar, "Reliquias (n)" button, relic slots, info panel (Robo / Mano máx.),
  turn ribbon, End Turn (gold, hourglass + E; pulses when `nothing_to_play`; locked and grey
  as "TURNO ENEMIGO" for `_ENEMY_PHASE` s after ending the turn), gold trim over the hand
  area, `ManaOrb`, card-stack piles, "Mano n/m" button. Map header uses the same kit.
- Pause menu: kit panel, ribbon, gold/bronze buttons, key caps.
- Hero sheet: `C` or the helmet button → `application/hero_stats.hero_sheet` +
  `ui/hero_sheet.HeroSheetOverlay`. New stat or relic bonus: compute it in `hero_sheet`
  (per-relic via `_per_relic(relics, query)`), give it an icon and a colour in
  `STAT_COLOR`.

## Card numbers, ready keywords, main menu (2026-10-07)

- **Bug fixed:** cards offered outside combat (combat reward, shop/boss packs, deck and
  pile viewers, El Brujo) showed printed damage/block while the hand added the hero's
  Ataque/Destreza and relics. All of them now use `application/card_preview` (same values
  as the hand; per-turn extras like Afilar or the Combo scarf stay hand-only).
- **Ready keywords** (`fx/card_fx.py`): when a card's Combo / Singular / Vacío / Despojo
  condition holds, it gets an aura behind, comets running round its border and a
  "¡COMBO!" badge above it — drawn by `draw_card` and `draw_card_at` after the chroma
  layers, so golden (or any future chroma) and ready effects are visible together. New
  keyword → one `ReadyStyle` in `READY_STYLES`. (Replaces `_keyword_glow` / `*_READY_GLOW`.)
- **Main menu** restyled with the pixel kit (see the file map).

## Luck everywhere (2026-10-07)

User: the Trébol de Siete Hojas (and luck in general) should affect gachapones and packs.
`run_luck` (character + Pruebas + relics) already bent every drop — card tiers in rewards and
packs, relic tiers (treasure, shop, boss, gachapón), golden chance of cards/relics/packs/
gachapón — but packs draw 5 of a tiny themed pool (5–8 cards), so luck barely changed them and
nothing on screen showed it. Now:

- **Cartas de la suerte** (`rarity.lucky_card_chances/lucky_card_count`, `LUCKY_CARD_LUCK = 100`,
  `card_rewards.lucky_cards`): every pack and card reward may add extra cards — first one with
  chance luck/100 (Trébol: certain), a second one with (luck − 100)/200. Taken from every
  allowed card of any theme, Rara or better when possible, luck-weighted, own golden roll, own
  rng (normal picks unchanged); `Card.lucky_drop` marks them. Screens: green glow, clover
  sparks and a "¡SUERTE!" badge (`card_fx.draw_lucky_back/front`), anticipation in the reveal.
- **Visible luck:** `ui/luck_badge` in the shop, pack opening and card reward; the gachapón
  odds panel shows "Suerte N ▲" and a green ▲ on every tier your luck raised (vs. the
  character's own luck); the hero sheet's Suerte row says it acts on packs, rewards and the
  gachapón.
- `card_rewards._reward_seed` now hashes the room id with `zlib.crc32` (the old `hash()` was
  salted per process, so rewards were not reproducible from the seed).

## Interés Compuesto (2026-10-07)

User: a neutral relic "interés compuesto": every time you get gold, gain 10 % of your total
gold; pick its rarity. Chosen tier: **Épica** — it is a pure economy relic with no combat
power, but it snowballs (more gold → more shop/gachapón → more power), so above Rara; not
Legendaria because it does nothing in a fight.

- `RelicTag.COMPOUND_INTEREST` (Épica), relic `r_interest` "Interés Compuesto" (neutral,
  sprite `item/gold/gold_pile_25.png`), `relic_effects.compound_interest_percent` (10, golden 20, stacks).
- `run_manager.gain_gold(run, amount)` is the single entry point for gold gains (combat
  victory incl. Carterista gold, events): adds the gain, then `gold × % // 100`; 0/negative
  gains pay nothing; spending never pays. Records `Run.last_interest` / `interest_earned`.
- Feedback: the gold counter shows "+N interés" (purple, one line under the gain, a beat
  later — `GoldHud.note`, delayed entries hidden while age < 0); combat and boss reward
  screens print "Oro obtenido: +X  (+N de interés)".
- Tests: `tests/application/test_compound_interest.py`; `test_relic` tag count now 35.

