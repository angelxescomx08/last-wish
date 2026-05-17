from __future__ import annotations

import pygame

# Backgrounds
BG_DARK:        pygame.Color = pygame.Color(12, 12, 20)
BG_PANEL:       pygame.Color = pygame.Color(22, 22, 36)
BG_CARD_AREA:   pygame.Color = pygame.Color(8,  10, 16)
BG_OVERLAY:     pygame.Color = pygame.Color(0,  0,  0, 160)

# Entity bodies
PLAYER_BODY:    pygame.Color = pygame.Color(50,  80,  160)
PLAYER_ACCENT:  pygame.Color = pygame.Color(90,  130, 220)
ENEMY_BODY:     pygame.Color = pygame.Color(130, 35,  35)
ENEMY_ACCENT:   pygame.Color = pygame.Color(190, 65,  65)

# Health
HP_FILL:        pygame.Color = pygame.Color(55,  175, 55)
HP_LOW:         pygame.Color = pygame.Color(200, 80,  20)
HP_EMPTY:       pygame.Color = pygame.Color(70,  18,  18)
HP_TEXT:        pygame.Color = pygame.Color(220, 220, 220)

# Block
BLOCK_COLOR:    pygame.Color = pygame.Color(75,  145, 210)
BLOCK_BG:       pygame.Color = pygame.Color(20,  50,  90)

# Cards — type colours
CARD_ATTACK:      pygame.Color = pygame.Color(155, 38, 38)
CARD_ATTACK_DARK: pygame.Color = pygame.Color(85,  15, 15)
CARD_SKILL:       pygame.Color = pygame.Color(38,  125, 55)
CARD_SKILL_DARK:  pygame.Color = pygame.Color(15,  70,  28)
CARD_POWER:       pygame.Color = pygame.Color(45,  55,  165)
CARD_POWER_DARK:  pygame.Color = pygame.Color(18,  22,  100)
CARD_SELECTED:    pygame.Color = pygame.Color(235, 210, 55)
CARD_HOVER:       pygame.Color = pygame.Color(200, 185, 110)
CARD_BORDER:      pygame.Color = pygame.Color(160, 145, 95)
CARD_BROKEN:      pygame.Color = pygame.Color(175, 80,  210)
CARD_BROKEN_DARK: pygame.Color = pygame.Color(80,  25,  105)

# Mana
MANA_FILL:      pygame.Color = pygame.Color(55,  155, 235)
MANA_EMPTY:     pygame.Color = pygame.Color(25,  55,  95)
MANA_ORB_RING:  pygame.Color = pygame.Color(90,  185, 255)
MANA_TEXT:      pygame.Color = pygame.Color(195, 225, 255)

# Intent
INTENT_ATTACK:  pygame.Color = pygame.Color(210, 55,  55)
INTENT_BLOCK:   pygame.Color = pygame.Color(55,  115, 210)
INTENT_BUFF:    pygame.Color = pygame.Color(55,  200, 95)
INTENT_DEBUFF:  pygame.Color = pygame.Color(175, 55,  175)
INTENT_UNKNOWN: pygame.Color = pygame.Color(130, 130, 130)

# Status effects
BUFF_COLOR:     pygame.Color = pygame.Color(55,  200, 120)
DEBUFF_COLOR:   pygame.Color = pygame.Color(200, 90,  200)

# UI text and borders
TEXT_PRIMARY:   pygame.Color = pygame.Color(220, 215, 200)
TEXT_SECONDARY: pygame.Color = pygame.Color(155, 150, 135)
TEXT_ACCENT:    pygame.Color = pygame.Color(215, 180, 75)
TEXT_DAMAGE:    pygame.Color = pygame.Color(255, 120, 80)
TEXT_BLOCK:     pygame.Color = pygame.Color(100, 175, 255)
BORDER_DIM:     pygame.Color = pygame.Color(55,  50,  45)
BORDER_BRIGHT:  pygame.Color = pygame.Color(115, 105, 85)

# HUD
RELIC_BG:       pygame.Color = pygame.Color(38,  32,  52)
RELIC_BORDER:   pygame.Color = pygame.Color(90,  75,  115)
END_TURN_BG:    pygame.Color = pygame.Color(165, 115, 25)
END_TURN_HOVER: pygame.Color = pygame.Color(200, 150, 40)
END_TURN_TEXT:  pygame.Color = pygame.Color(255, 245, 195)
PANEL_BORDER:   pygame.Color = pygame.Color(45,  40,  65)
