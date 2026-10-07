from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

import pygame

from src.application.card_rewards import pick_pack_cards, pick_reward_cards
from src.application.combat_factory import create_combat_from_run
from src.application.run_manager import (
    acquire_relic,
    advance_floor,
    apply_combat_victory,
    generate_boss,
    generate_enemies,
    generate_event_gold,
    pick_boss_relics,
    pick_treasure_relics,
    create_run,
)
from src.domain.card_pool import PackTheme
from src.domain.map_node import RoomType
from src.infrastructure.colors import TEXT_ACCENT, TEXT_PRIMARY
from src.infrastructure.audio import SoundPlayer
from src.infrastructure.fonts import FontRegistry
from src.infrastructure.viewport import Viewport
from src.infrastructure.preferences import UserPreferences, load_preferences, save_preferences
from src.infrastructure.dev_settings import load_dev_settings, save_dev_settings
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
from src.presentation.scenes.dev_settings_scene import DevSettingsScene
from src.presentation.scenes.shop_scene import ShopScene
from src.presentation.scenes.treasure_scene import TreasureScene
from src.domain.tuning import TUNING
from src.presentation.scenes.gacha_scene import GachaScene
from src.presentation.ui.gold_hud import DEFAULT_POS as GOLD_HUD_POS
from src.presentation.ui.gold_hud import GoldHud
from src.presentation.scenes.warlock_scene import WarlockScene
from src.presentation.ui.pause_menu import PauseMenu, PauseAction, draw_pause_button, pause_button_rect

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

    def __init__(self, initial: Scene, fonts: FontRegistry, prefs: UserPreferences,
                 *, sound: SoundPlayer | None = None) -> None:
        self._stack:         list[Scene] = [initial]
        self._fonts          = fonts
        self._prefs          = prefs
        self._sound = sound if sound is not None else SoundPlayer(
            sfx_volume=prefs.sfx_volume, music_volume=prefs.music_volume
        )
        self._run            = None           # set when character is selected
        self.quit_requested: bool = False
        self._pause: PauseMenu | None = None
        self._gold_hud = GoldHud(fonts)       # shared gold counter on every run screen
        self._gold_run_id: int | None = None

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

    def _can_pause(self) -> bool:
        return self._run is not None and not isinstance(
            self._top(), (MainMenuScene, CharacterSelectScene, SettingsScene, DevSettingsScene, DeathScene)
        )

    def handle_event(self, event: pygame.event.Event) -> None:
        if self._pause is not None:
            self._pause.handle_event(event)
            action = self._pause.action
            if action == PauseAction.ABANDON:
                self._run = None
                self._stack = [MainMenuScene(self._fonts, sound=self._sound)]
            if action is not None:
                self._pause = None
                self._sound.play_confirm()
            return
        top = self._top()
        escape = event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE
        button = pause_button_rect(top)
        clicked = (event.type == pygame.MOUSEBUTTONDOWN and event.button == 1
                   and button is not None and button.collidepoint(event.pos))
        if self._can_pause() and (escape or clicked):
            # Escape first dismisses an existing collection or held card.
            if escape and (getattr(top, '_overlay', None) is not None
                           or isinstance(top, CombatScene) and top._play.active):
                top.handle_event(event)
                return
            if escape and getattr(event, 'repeat', False):
                return
            if isinstance(top, CombatScene):
                top._cancel_selection()
            self._pause = PauseMenu(self._fonts)
            self._sound.play_confirm()
            return
        top.handle_event(event)

    def update(self, dt: float) -> None:
        self._sound.update()
        if self._pause is not None:
            return
        top = self._top()
        top.update(dt)
        self._handle_transitions(top)
        self._update_gold(dt)

    def _update_gold(self, dt: float) -> None:
        run = self._run
        if run is None:
            self._gold_run_id = None
            return
        if self._gold_run_id != id(run):          # a new run: show its gold without counting
            self._gold_run_id = id(run)
            self._gold_hud.sync(run.gold)
        self._gold_hud.update(dt, run.gold)

    @property
    def gold_hud(self) -> GoldHud:
        return self._gold_hud

    def draw(self, surface: pygame.Surface) -> None:
        self._top().draw(surface)
        if self._can_pause() and self._run is not None and getattr(self._top(), 'show_gold_hud', True):
            anchor, pos = getattr(self._top(), 'gold_hud_pos', GOLD_HUD_POS)
            self._gold_hud.draw(surface, anchor, pos)
        button = pause_button_rect(self._top()) if self._can_pause() else None
        if button is not None:
            draw_pause_button(surface, self._fonts, button)
        if self._pause is not None:
            self._pause.draw(surface)

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
        elif isinstance(top, WarlockScene):
            if top.cleared:
                top.cleared = False
                self.pop()
        elif isinstance(top, GachaScene):
            if top.cleared:
                top.cleared = False
                self.pop()
        elif isinstance(top, SettingsScene):
            self._t_settings(top)
        elif isinstance(top, DevSettingsScene):
            if top.cleared:
                top.cleared = False
                save_dev_settings()
                self.pop()
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
            self.push(CharacterSelectScene(self._fonts, sound=self._sound))
        elif action == MenuAction.SETTINGS:
            self.push(SettingsScene(self._fonts, self._prefs, sound=self._sound))
        elif action == MenuAction.DEV:
            self.push(DevSettingsScene(self._fonts, sound=self._sound))
        elif action == MenuAction.EXIT:
            self.quit_requested = True

    def _t_char_select(self, scene: CharacterSelectScene) -> None:
        if scene.confirmed:
            scene.confirmed = False
            self._run = create_run(scene.selected_character, scene.seed)
            self.pop()                      # remove CharacterSelectScene
            self.push(MapScene(self._run, self._fonts, sound=self._sound))

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

        if node.room_type == RoomType.COMBAT and TUNING.gacha_rooms:   # Pruebas: test the machine
            self.push(GachaScene(run, self._fonts, sound=self._sound))

        elif node.room_type == RoomType.COMBAT:
            enemies = generate_enemies(run, node.id)
            state   = create_combat_from_run(run, enemies)
            self.push(CombatScene(state, self._fonts, sound=self._sound))

        elif node.room_type == RoomType.BOSS:
            enemies = generate_boss(run)
            state   = create_combat_from_run(run, enemies)
            self.push(CombatScene(state, self._fonts, is_boss=True, sound=self._sound))

        elif node.room_type == RoomType.TREASURE:
            relics = pick_treasure_relics(run, node.id)   # 2+ with Llave Maestra
            self.push(TreasureScene(run, relics, self._fonts, sound=self._sound))

        elif node.room_type == RoomType.SHOP:
            self.push(ShopScene(run, self._fonts, sound=self._sound))

        elif node.room_type == RoomType.EVENT:
            gold = generate_event_gold(run, node.id)
            self.push(EventScene(run, gold, node.id, self._fonts, sound=self._sound))

        elif node.room_type == RoomType.WARLOCK:
            self.push(WarlockScene(run, self._fonts, sound=self._sound))

        elif node.room_type == RoomType.GACHA:
            self.push(GachaScene(run, self._fonts, sound=self._sound))

    def _t_combat(self, scene: CombatScene) -> None:
        run = self._run

        # Victory
        if scene.combat_won and not scene._victory_acknowledged:
            scene._victory_acknowledged = True
            self._sound.play_win()
            enemies = scene.state.enemies   # already-dead list for gold calc
            if scene.is_boss:
                gold     = apply_combat_victory(run, scene.state.player.current_hp,
                                                scene.state.enemies, scene.state.gold_earned)
                relics   = pick_boss_relics(run)
                self.push(BossRewardScene(run, gold, relics, self._fonts, sound=self._sound))
            else:
                gold     = apply_combat_victory(run, scene.state.player.current_hp,
                                                scene.state.enemies, scene.state.gold_earned)
                cards    = pick_reward_cards(run, run.current_room_id or "unknown")
                self.push(CombatRewardScene(run, gold, cards, self._fonts, sound=self._sound))

        # Death
        elif scene.death_occurred and not scene._death_acknowledged:
            scene._death_acknowledged = True
            self._sound.play_death()
            self.push(DeathScene(self._fonts, scene.turn_reached, sound=self._sound))

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
        if scene.chosen_relic is not None:
            acquire_relic(run, scene.chosen_relic)
        self.pop()

    def _t_shop(self, scene: ShopScene) -> None:
        if scene.selected_pack is not None:
            theme            = scene.selected_pack
            chroma           = scene.selected_pack_chroma
            scene.selected_pack = None      # consume
            scene.selected_pack_chroma = None
            run              = self._run
            cards            = pick_pack_cards(run, theme)
            from src.domain.card_pool import pack_def_for_theme
            from src.domain.chroma import chroma_title
            pack_name        = chroma_title(pack_def_for_theme(theme).name, chroma, masculine=True)
            self.push(PackOpeningScene(cards, pack_name, self._fonts, sound=self._sound,
                                       theme=theme.value, seed=run.floor, chroma=chroma))

        elif scene.cleared:
            scene.cleared = False
            self.pop()

    def _t_pack(self, scene: PackOpeningScene) -> None:
        if not scene.cleared:
            return
        scene.cleared = False
        run = self._run
        for card in scene.chosen_cards:
            run.add_card(card)
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
            self.push(PackOpeningScene(cards, name, self._fonts, sound=self._sound,
                                       theme=PackTheme.EPICO.value, seed=run.floor))

        elif scene.cleared:
            scene.cleared = False
            run = self._run
            if scene.chosen_relic is not None:
                acquire_relic(run, scene.chosen_relic)
            self.pop()              # pop BossRewardScene
            self.pop()              # pop CombatScene
            advance_floor(run)
            self.push(MapScene(run, self._fonts, sound=self._sound))

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
            self.push(CharacterSelectScene(self._fonts, sound=self._sound))
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
    pygame.mixer.pre_init(frequency=44100, size=-16, channels=2, buffer=512)
    pygame.init()

    screen = pygame.display.set_mode(
        (settings.width, settings.height),
        pygame.RESIZABLE,
    )
    pygame.display.set_caption(settings.title)

    viewport      = Viewport(settings.width, settings.height)
    fonts         = FontRegistry()
    prefs         = load_preferences()
    load_dev_settings()
    sound = SoundPlayer(sfx_volume=prefs.sfx_volume, music_volume=prefs.music_volume)
    sound.start_music()
    scene_manager = SceneManager(MainMenuScene(fonts, sound=sound), fonts, prefs, sound=sound)
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

    sound.stop_music()
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
