from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

import pygame

from src.application.card_rewards import pick_pack_cards, pick_reward_cards
from src.application.combat_factory import create_combat_from_run
from src.application.run_manager import (
    advance_floor,
    apply_combat_victory,
    generate_boss,
    generate_enemies,
    generate_event_gold,
    pick_boss_relics,
    pick_treasure_relic,
    create_run,
)
from src.domain.card_pool import PackTheme
from src.domain.map_node import RoomType
from src.infrastructure.colors import TEXT_ACCENT, TEXT_PRIMARY
from src.infrastructure.fonts import FontRegistry
from src.infrastructure.viewport import Viewport
from src.infrastructure.preferences import UserPreferences, load_preferences, save_preferences
from src.presentation.scenes.boss_reward_scene import BossRewardScene
from src.presentation.scenes.character_select_scene import CharacterSelectScene
from src.presentation.scenes.combat_reward_scene import CombatRewardScene
from src.presentation.scenes.combat_scene import CombatScene
from src.presentation.scenes.death_scene import DeathAction, DeathScene
from src.presentation.scenes.event_scene import EventScene
from src.presentation.scenes.main_menu_scene import MainMenuScene, MenuAction
from src.presentation.scenes.map_scene import MapScene
from src.presentation.scenes.pack_opening_scene import PackOpeningScene
from src.presentation.scenes.settings_scene import SettingsScene
from src.presentation.scenes.shop_scene import ShopScene
from src.presentation.scenes.treasure_scene import TreasureScene

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

WINDOW_TITLE: str  = "Last Wish"
WINDOW_WIDTH: int  = 1280
WINDOW_HEIGHT: int = 720
TARGET_FPS: int    = 60
MIN_W: int = 480
MIN_H: int = 270


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class GameSettings:
    width: int
    height: int
    fps: int
    title: str


# ---------------------------------------------------------------------------
# Scene protocol
# ---------------------------------------------------------------------------

@runtime_checkable
class Scene(Protocol):
    def handle_event(self, event: pygame.event.Event) -> None: ...
    def update(self, dt: float) -> None: ...
    def draw(self, surface: pygame.Surface) -> None: ...


# ---------------------------------------------------------------------------
# Scene manager
# ---------------------------------------------------------------------------

class SceneManager:
    """Stack-based scene manager that drives all scene transitions.

    Stores the active Run so transitions can update run state without each
    scene needing to know about the next one.
    """

    def __init__(self, initial: Scene, fonts: FontRegistry, prefs: UserPreferences) -> None:
        self._stack:         list[Scene] = [initial]
        self._fonts          = fonts
        self._prefs          = prefs
        self._run            = None           # set when character is selected
        self.quit_requested: bool = False

    # ------------------------------------------------------------------
    # Stack operations
    # ------------------------------------------------------------------

    def push(self, scene: Scene) -> None:
        self._stack.append(scene)

    def pop(self) -> None:
        if len(self._stack) > 1:
            self._stack.pop()

    def _pop_all_except_first(self) -> None:
        while len(self._stack) > 1:
            self._stack.pop()

    def _top(self) -> Scene:
        return self._stack[-1]

    # ------------------------------------------------------------------
    # Game loop delegates
    # ------------------------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> None:
        self._top().handle_event(event)

    def update(self, dt: float) -> None:
        top = self._top()
        top.update(dt)
        self._handle_transitions(top)

    def draw(self, surface: pygame.Surface) -> None:
        self._top().draw(surface)

    # ------------------------------------------------------------------
    # Transition dispatcher
    # ------------------------------------------------------------------

    def _handle_transitions(self, top: Scene) -> None:
        if isinstance(top, MainMenuScene):
            self._t_main_menu(top)
        elif isinstance(top, CharacterSelectScene):
            self._t_char_select(top)
        elif isinstance(top, MapScene):
            self._t_map(top)
        elif isinstance(top, CombatScene):
            self._t_combat(top)
        elif isinstance(top, CombatRewardScene):
            self._t_combat_reward(top)
        elif isinstance(top, TreasureScene):
            self._t_treasure(top)
        elif isinstance(top, ShopScene):
            self._t_shop(top)
        elif isinstance(top, PackOpeningScene):
            self._t_pack(top)
        elif isinstance(top, EventScene):
            self._t_event(top)
        elif isinstance(top, BossRewardScene):
            self._t_boss_reward(top)
        elif isinstance(top, SettingsScene):
            self._t_settings(top)
        elif isinstance(top, DeathScene):
            self._t_death(top)

    # ------------------------------------------------------------------
    # Individual transitions
    # ------------------------------------------------------------------

    def _t_main_menu(self, scene: MainMenuScene) -> None:
        action = scene.requested_action
        if action is None:
            return
        scene.requested_action = None
        if action == MenuAction.PLAY:
            self.push(CharacterSelectScene(self._fonts))
        elif action == MenuAction.SETTINGS:
            self.push(SettingsScene(self._fonts, self._prefs))
        elif action == MenuAction.EXIT:
            self.quit_requested = True

    def _t_char_select(self, scene: CharacterSelectScene) -> None:
        if scene.confirmed:
            scene.confirmed = False
            self._run = create_run(scene.selected_character, scene.seed)
            self.pop()                      # remove CharacterSelectScene
            self.push(MapScene(self._run, self._fonts))

        elif scene.back_to_menu:
            scene.back_to_menu = False
            self.pop()

    def _t_map(self, scene: MapScene) -> None:
        node = scene.selected_node
        if node is None:
            return
        scene.selected_node = None          # consume
        run = self._run

        # Mark node as entered (visited)
        if run.current_map:
            run.current_map.mark_visited(node.id)
        run.current_room_id = node.id

        if node.room_type == RoomType.COMBAT:
            enemies = generate_enemies(run, node.id)
            state   = create_combat_from_run(run, enemies)
            self.push(CombatScene(state, self._fonts))

        elif node.room_type == RoomType.BOSS:
            enemies = generate_boss(run)
            state   = create_combat_from_run(run, enemies)
            self.push(CombatScene(state, self._fonts, is_boss=True))

        elif node.room_type == RoomType.TREASURE:
            relic = pick_treasure_relic(run, node.id)
            self.push(TreasureScene(run, relic, self._fonts))

        elif node.room_type == RoomType.SHOP:
            self.push(ShopScene(run, self._fonts))

        elif node.room_type == RoomType.EVENT:
            gold = generate_event_gold(run, node.id)
            self.push(EventScene(run, gold, node.id, self._fonts))

    def _t_combat(self, scene: CombatScene) -> None:
        run = self._run

        # Victory
        if scene.combat_won and not scene._victory_acknowledged:
            scene._victory_acknowledged = True
            enemies = scene.state.enemies   # already-dead list for gold calc
            if scene.is_boss:
                gold     = apply_combat_victory(run, scene.state.player.current_hp,
                                                scene.state.enemies)
                relics   = pick_boss_relics(run)
                self.push(BossRewardScene(run, gold, relics, self._fonts))
            else:
                gold     = apply_combat_victory(run, scene.state.player.current_hp,
                                                scene.state.enemies)
                cards    = pick_reward_cards(run, run.current_room_id or "unknown")
                self.push(CombatRewardScene(run, gold, cards, self._fonts))

        # Death
        elif scene.death_occurred and not scene._death_acknowledged:
            scene._death_acknowledged = True
            self.push(DeathScene(self._fonts, scene.turn_reached))

    def _t_combat_reward(self, scene: CombatRewardScene) -> None:
        if not scene.cleared:
            return
        scene.cleared = False
        run = self._run
        if scene.chosen_card is not None:
            run.add_card(scene.chosen_card)
        self.pop()          # pop CombatRewardScene
        self.pop()          # pop CombatScene

    def _t_treasure(self, scene: TreasureScene) -> None:
        if not scene.cleared:
            return
        scene.cleared = False
        run = self._run
        if scene.took_relic:
            run.add_relic(scene._relic)
            from src.application import relic_effects
            run.player_max_hp = (
                run.character.stats.max_hp
                + relic_effects.max_hp_bonus(run.relics)
            )
        self.pop()

    def _t_shop(self, scene: ShopScene) -> None:
        if scene.selected_pack is not None:
            theme            = scene.selected_pack
            scene.selected_pack = None      # consume
            run              = self._run
            cards            = pick_pack_cards(run, theme)
            from src.domain.card_pool import pack_def_for_theme
            pack_name        = pack_def_for_theme(theme).name
            self.push(PackOpeningScene(cards, pack_name, self._fonts))

        elif scene.cleared:
            scene.cleared = False
            self.pop()

    def _t_pack(self, scene: PackOpeningScene) -> None:
        if not scene.cleared:
            return
        scene.cleared = False
        run = self._run
        if scene.chosen_card is not None:
            run.add_card(scene.chosen_card)
        self.pop()          # pop PackOpeningScene
        # Caller is either ShopScene or BossRewardScene
        top = self._top()
        if isinstance(top, BossRewardScene):
            top.pack_done()

    def _t_event(self, scene: EventScene) -> None:
        if not scene.cleared:
            return
        scene.cleared = False
        run = self._run
        run.gold += scene._gold
        self.pop()

    def _t_boss_reward(self, scene: BossRewardScene) -> None:
        if scene.open_pack_requested:
            scene.open_pack_requested = False
            run    = self._run
            cards  = pick_pack_cards(run, PackTheme.EPICO)
            from src.domain.card_pool import pack_def_for_theme
            name   = pack_def_for_theme(PackTheme.EPICO).name
            self.push(PackOpeningScene(cards, name, self._fonts))

        elif scene.cleared:
            scene.cleared = False
            run = self._run
            if scene.chosen_relic is not None:
                run.add_relic(scene.chosen_relic)
                from src.application import relic_effects
                run.player_max_hp = (
                    run.character.stats.max_hp
                    + relic_effects.max_hp_bonus(run.relics)
                )
            self.pop()              # pop BossRewardScene
            self.pop()              # pop CombatScene
            advance_floor(run)
            self.push(MapScene(run, self._fonts))

    def _t_settings(self, scene: SettingsScene) -> None:
        if scene.cleared:
            scene.cleared = False
            save_preferences(self._prefs)
            self.pop()

    def _t_death(self, scene: DeathScene) -> None:
        action = scene.requested_action
        if action is None:
            return
        scene.requested_action = None
        self._run = None

        if action == DeathAction.NEW_GAME:
            self._pop_all_except_first()
            self.push(CharacterSelectScene(self._fonts))
        elif action == DeathAction.MAIN_MENU:
            self._pop_all_except_first()


# ---------------------------------------------------------------------------
# Mouse transform
# ---------------------------------------------------------------------------

def _transform_mouse(event: pygame.event.Event, viewport: Viewport) -> pygame.event.Event:
    _MOUSE = (pygame.MOUSEMOTION, pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP)
    if event.type not in _MOUSE:
        return event
    attrs = dict(event.__dict__)
    attrs["pos"] = viewport.to_virtual(event.pos)
    if "rel" in attrs and viewport._scale > 0:
        rx, ry = event.rel
        attrs["rel"] = (rx / viewport._scale, ry / viewport._scale)
    return pygame.event.Event(event.type, attrs)


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

def run(settings: GameSettings) -> None:
    pygame.init()

    screen = pygame.display.set_mode(
        (settings.width, settings.height),
        pygame.RESIZABLE,
    )
    pygame.display.set_caption(settings.title)

    viewport      = Viewport(settings.width, settings.height)
    fonts         = FontRegistry()
    prefs         = load_preferences()
    scene_manager = SceneManager(MainMenuScene(fonts), fonts, prefs)
    clock         = pygame.time.Clock()

    running = True
    while running:
        dt: float = clock.tick(settings.fps) / 1000.0

        actual_w, actual_h = screen.get_size()
        if (actual_w, actual_h) != (viewport._dest_w + viewport._off_x * 2,
                                    viewport._dest_h + viewport._off_y * 2):
            viewport.resize(max(actual_w, MIN_W), max(actual_h, MIN_H))

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.WINDOWRESIZED:
                viewport.resize(max(event.x, MIN_W), max(event.y, MIN_H))
            else:
                scene_manager.handle_event(_transform_mouse(event, viewport))

        scene_manager.update(dt)

        if scene_manager.quit_requested:
            running = False

        scene_manager.draw(viewport.surface)

        if prefs.show_fps:
            fps_text = f"FPS: {clock.get_fps():.0f}"
            fps_surf = fonts.get(16).render(fps_text, True, pygame.Color(255, 220, 50))
            vw = viewport.surface.get_width()
            viewport.surface.blit(fps_surf, (vw - fps_surf.get_width() - 8, 8))

        viewport.present(screen)
        pygame.display.flip()

    pygame.quit()


def main() -> None:
    run(GameSettings(
        width=WINDOW_WIDTH,
        height=WINDOW_HEIGHT,
        fps=TARGET_FPS,
        title=WINDOW_TITLE,
    ))


if __name__ == "__main__":
    main()
