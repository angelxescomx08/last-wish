from __future__ import annotations

from dataclasses import dataclass, field

import pygame

from src.domain.card import Card, CardType, ModifierTag
from src.domain.entities import Enemy, IntentType, Player
from src.domain.mana import Mana
from src.domain.numbers import BigValue
from src.domain.relic import Relic
from src.infrastructure import colors
from src.infrastructure.fonts import FontRegistry

# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

@dataclass
class TooltipContent:
    title: str
    lines: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Content generators -- one per game object type
# ---------------------------------------------------------------------------

_CARD_TYPE_NAME: dict[CardType, str] = {
    CardType.ATTACK: "Ataque",
    CardType.SKILL:  "Habilidad",
    CardType.POWER:  "Poder",
}

_MOD_DESCRIPTIONS: dict[ModifierTag, str] = {
    ModifierTag.CHROMA:      "Chroma -- Altera el tipo de daño",
    ModifierTag.TRANSPARENT: "Transparente -- El daño ignora el bloqueo",
    ModifierTag.ETHEREAL:    "Etéreo -- Se agota al jugarse, no se descarta",
    ModifierTag.ECHO:        "Eco -- El efecto se activa dos veces",
}

_INTENT_DESCRIPTION: dict[IntentType, str] = {
    IntentType.ATTACK:  "Planea atacar",
    IntentType.BLOCK:   "Planea defenderse",
    IntentType.BUFF:    "Planea fortalecerse",
    IntentType.DEBUFF:  "Planea debilitar al jugador",
    IntentType.UNKNOWN: "Intención desconocida",
}


def card_tooltip(card: Card, bonus_damage: int = 0) -> TooltipContent:
    title = card.name + (" (Rota)" if card.is_broken else "")
    lines: list[str] = [
        f"{_CARD_TYPE_NAME[card.card_type]}  ·  Coste: {card.cost} maná",
        "",
    ]

    dmg = card.total_damage()
    blk = card.total_block()
    if dmg > 0:
        effective = dmg + bonus_damage
        base_str = BigValue.format_int(effective)
        if bonus_damage > 0:
            lines.append(f"Inflige {base_str} de daño a un enemigo.")
            lines.append(f"  ({BigValue.format_int(dmg)} + {bonus_damage} del Orbe de Fuego)")
        else:
            lines.append(f"Inflige {base_str} de daño a un enemigo.")
    if blk > 0:
        lines.append(f"Otorga {BigValue.format_int(blk)} puntos de bloqueo.")

    base_draw = card.base_effect.draw + sum(fx.draw for fx in card.stacked_effects)
    if base_draw > 0:
        lines.append(f"Roba {base_draw} carta(s) adicional(es).")

    if not (dmg or blk or base_draw):
        lines.append("Efecto especial -- aún por determinar.")

    if card.stacked_effects:
        lines += ["", f"Efectos apilados ({card.effect_count()}):"]
        for fx in card.stacked_effects:
            parts: list[str] = []
            d = fx.damage.resolve()
            b = fx.block.resolve()
            if d > 0:
                parts.append(f"+{BigValue.format_int(d)} daño")
            if b > 0:
                parts.append(f"+{BigValue.format_int(b)} bloqueo")
            label = ", ".join(parts) if parts else "efecto pasivo"
            lines.append(f"  · {fx.name}: {label}")

    if card.modifiers:
        lines.append("")
        for mod in card.modifiers:
            desc = _MOD_DESCRIPTIONS.get(mod.tag, mod.tag.name)
            lines.append(f"[*] {desc}")

    if card.is_broken:
        lines += ["", "[!] ROTA: puede fusionarse con otra carta rota."]

    return TooltipContent(title=title, lines=lines)


def enemy_tooltip(enemy: Enemy) -> TooltipContent:
    lines: list[str] = [
        f"Vida: {enemy.current_hp} / {enemy.max_hp}",
    ]
    if enemy.block > 0:
        lines.append(f"Bloqueo: {enemy.block} -- Absorbe el siguiente daño")

    lines.append("")
    intent_desc = _INTENT_DESCRIPTION.get(enemy.intent.intent_type, "???")
    if enemy.intent.intent_type == IntentType.ATTACK:
        lines.append(f"[ATQ]  {intent_desc} por {enemy.intent.value} de daño.")
    elif enemy.intent.intent_type == IntentType.BLOCK:
        lines.append(f"[BLQ]  {intent_desc} con {enemy.intent.value} de bloqueo.")
    else:
        lines.append(f"[*]  {intent_desc}.")

    if enemy.status_effects:
        lines.append("")
        for fx in enemy.status_effects:
            tag = "[+]" if fx.is_buff else "[-]"
            lines.append(f"{tag} {fx.name} x{fx.stacks}")

    return TooltipContent(title=enemy.name, lines=lines)


def relic_tooltip(relic: Relic) -> TooltipContent:
    status = "Estado: Activo" if relic.is_active else "Estado: Agotado"
    return TooltipContent(title=relic.name, lines=[relic.description, "", status])


def pile_tooltip(pile_label: str, count: int, *, is_draw: bool) -> TooltipContent:
    if is_draw:
        return TooltipContent(
            title="Pila de Robo",
            lines=[
                f"{count} carta(s) restantes.",
                "Haz clic para ver las cartas.",
                "",
                "Cuando se agota se baraja la pila",
                "de descarte y se convierte en la nueva pila.",
            ],
        )
    return TooltipContent(
        title="Pila de Descarte",
        lines=[
            f"{count} carta(s) descartadas.",
            "Haz clic para ver las cartas.",
            "",
            "Se baraja en la pila de robo cuando ésta",
            "se queda sin cartas.",
        ],
    )


def mana_tooltip(mana: Mana) -> TooltipContent:
    return TooltipContent(
        title="Maná",
        lines=[
            f"Disponible: {mana.current} / {mana.maximum}",
            "",
            "Recurso para jugar cartas.",
            "Se recarga completamente al inicio",
            "de cada turno.",
        ],
    )


def player_tooltip(player: Player) -> TooltipContent:
    lines = [
        f"Vida: {player.current_hp} / {player.max_hp}",
    ]
    if player.block > 0:
        lines.append(f"Bloqueo: {player.block} -- Absorbe el próximo daño recibido.")
    else:
        lines.append("Sin bloqueo activo.")

    if player.status_effects:
        lines.append("")
        for fx in player.status_effects:
            tag = "[+]" if fx.is_buff else "[-]"
            lines.append(f"{tag} {fx.name} x{fx.stacks}")

    return TooltipContent(title=player.name, lines=lines)


# ---------------------------------------------------------------------------
# Renderer
# ---------------------------------------------------------------------------

_MAX_W:   int = 275
_PAD:     int = 10
_GAP:     int = 3
_CORNER:  int = 6
_OFF_X:   int = 15
_OFF_Y:   int = -6


def draw_tooltip(
    surface: pygame.Surface,
    content: TooltipContent,
    mouse_pos: tuple[int, int],
    fonts: FontRegistry,
) -> None:
    title_font = fonts.get(14)
    body_font  = fonts.get(11)

    # Build render list: (font, text, is_title)
    render_list: list[tuple[pygame.font.Font, str, bool]] = [
        (title_font, content.title, True),
    ]
    if content.lines:
        render_list.append((body_font, "", False))
    for raw_line in content.lines:
        if raw_line == "":
            render_list.append((body_font, "", False))
        else:
            for wrapped in _word_wrap(raw_line, body_font, _MAX_W - _PAD * 2):
                render_list.append((body_font, wrapped, False))

    # Compute panel height
    panel_h = _PAD * 2
    for font, text, _ in render_list:
        panel_h += (font.get_height() + _GAP) if text else (_GAP * 2)

    # Position: default top-right of cursor, clamp to canvas
    sw, sh = surface.get_size()
    tx = mouse_pos[0] + _OFF_X
    ty = mouse_pos[1] + _OFF_Y
    if tx + _MAX_W > sw - 4:
        tx = mouse_pos[0] - _MAX_W - _OFF_X
    if ty + panel_h > sh - 4:
        ty = mouse_pos[1] - panel_h - 4
    tx = max(4, tx)
    ty = max(4, ty)

    # Background (semi-transparent overlay)
    bg_surf = pygame.Surface((_MAX_W, panel_h), pygame.SRCALPHA)
    bg_surf.fill((14, 12, 24, 222))
    surface.blit(bg_surf, (tx, ty))
    pygame.draw.rect(surface, colors.TEXT_ACCENT,
                     pygame.Rect(tx, ty, _MAX_W, panel_h), 1, border_radius=_CORNER)

    # Text
    cy = ty + _PAD
    for font, text, is_title in render_list:
        if not text:
            cy += _GAP * 2
            continue
        col  = colors.TEXT_ACCENT if is_title else colors.TEXT_PRIMARY
        surf = font.render(text, True, col)
        surface.blit(surf, (tx + _PAD, cy))
        cy += font.get_height() + _GAP


def _word_wrap(text: str, font: pygame.font.Font, max_w: int) -> list[str]:
    words   = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        test = (current + " " + word).strip()
        if font.size(test)[0] <= max_w:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [text]
