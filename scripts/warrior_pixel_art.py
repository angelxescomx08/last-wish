"""Hand-drawn pixel-art parts for La Guerrera (48 x 48 grid, classic 16-bit fantasy style).

One letter = one pixel; colours in PAL. Edit the grids, then run
`python scripts/generate_warrior_sprites.py`.
"""

def hx(h):
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))

PAL = {
    'X': hx('1a1020'),
    'H': hx('4e0e1c'), 'R': hx('8e1e2c'), 'r': hx('c4362c'), 'o': hx('e86236'), 'y': hx('ffa468'),
    'k': hx('7e3a34'), 'S': hx('d08c72'), 's': hx('f0bf9e'), 'z': hx('ffe2c8'),
    'q': hx('1e1418'), 'm': hx('a8505a'),
    'd': hx('262a3c'), 'c': hx('646c88'), 'b': hx('a2acc2'), 'a': hx('dfe5ee'), 'W': hx('ffffff'),
    'O': hx('a8701e'), 'Y': hx('eec464'),
    'N': hx('1c1924'), 'n': hx('34303f'), 'h': hx('4e4759'),
    'u': hx('0b252c'), 'T': hx('154a56'), 't': hx('206a74'), 'i': hx('348e8e'),
    'E': hx('561020'), 'e': hx('8e2430'), 'f': hx('b83a42'),
    'L': hx('3a2014'), 'l': hx('6c4228'), 'j': hx('966240'),
    'V': hx('241409'), 'B': hx('4c2c1a'), 'v': hx('6e4428'),
    'J': hx('d8303a'),
}

# ---------------------------------------------------------------- head (anchor = neck, below the chin)
HEAD_ANCHOR = (7, 11)
HEAD = {'normal': [
"....XXXXX...",
"...XroooorX.",
"..XroyyoorrX",
".XrooorrrrrX",
".XrrrrrRrrRX",
"XRrrrRrsRrsX",
"XRrrRSsqssX.",
"XRrRRSsssssX",
"XRRRXkSssSX.",
".XRRX.kSmX..",
".XRHX..XkX..",
"..XX...X....",
]}

def _variant(base, edits):
    rows = [list(r) for r in base]
    for (x, y), ch in edits.items():
        rows[y][x] = ch
    return ["".join(r) for r in rows]

_B = HEAD['normal']
HEAD['blink'] = _variant(_B, {(7, 6): 'S', (8, 6): 'S'})
HEAD['effort'] = _variant(_B, {(7, 5): 'q', (8, 9): 'q'})
HEAD['pain'] = _variant(_B, {(7, 6): 'k', (6, 6): 'q', (8, 5): 'q', (8, 9): 'q'})

TIE = ["Xi", "TX"]
TIE_AT = (2, 1)

# ---------------------------------------------------------------- ponytail (anchor = under the tie)
TAIL_ANCHOR = (7, 0)
TAIL = [
"....XXXX",
"...XrorX",
"..XroyrX",
"..XrorRX",
".XrorRX.",
".XrorRX.",
".XrorRX.",
"XrorRX..",
"XrorRX..",
"XRorRX..",
"XRrrRX..",
".XRrRX..",
".XRrRX..",
"..XRX...",
"..XRX...",
"...X....",
]

# ---------------------------------------------------------------- torso (anchor = neck)
TORSO_ANCHOR = (5, 0)
TORSO = [
".....XsX...",
"...XXtiTX..",
".XbaaXtTnX.",
"XbaWabXanbX",
"XabacOXaabX",
"XOOOOXbWabX",
".XnnXnbabcX",
".XnhXnbbcX.",
".XnhNXOcOX.",
"..XLljlYLX.",
"..XLLLLOLX.",
"..XnhnnnX..",
]

# ---------------------------------------------------------------- cape (anchor = shoulder)
CAPE_ANCHOR = (6, 0)
CAPE = [
"....XtX",
"...XttX",
"...XitTX",
"..XittTX",
"..XittTX",
"..XitTTX",
".XittTTX",
".XittTX.",
".XitTTX.",
"XittTTX.",
"XitTTTX.",
"XittTTX.",
"XitTTTX.",
"XttTTTX.",
"XOYOYOX.",
".X.X.X..",
]

# ---------------------------------------------------------------- skirt (anchor = waist)
SKIRT_ANCHOR = (5, 0)
SKIRT = [
".XeeeXttX..",
"XefeeXtitX.",
"XefeXtiYtX.",
"XeeEXttOtX.",
"XeEEXtttTX.",
"XEXEXXtTTX.",
".X.X.XOTOX.",
"......XXX..",
]

# ---------------------------------------------------------------- legs (anchor = hip centre)
LEGS_ANCHOR = (7, 0)
LEGS = [
"...XnnX.XnhX....",
"...XnnX.XnhnX...",
"..XnnNX..XnhnX..",
"..XnnNX..XnhnX..",
"..XnnNX...XnhnX.",
"..XbabX...XbabX.",
"..XbObX...XbObX.",
"..XBvBX...XBvBX.",
"..XBvBX...XBvBX.",
"..XjllX...XjllX.",
"..XBvBX...XBvBX.",
"..XBvBX...XBvBX.",
"..XBvBX...XBvBX.",
"..XBvVX...XBvVX.",
"..XBvBVX..XBvBVX",
".XBvvBBX..XBvvBBX",
".XVVVVVX..XVVVVVX",
".XXXXXXX..XXXXXXX",
]

# ---------------------------------------------------------------- arms: (shoulder anchor, grip, rows)
NEAR_ARM = {
'rest': ((1, 0), (2, 10), [
"XnX.",
"XnX.",
"XnX.",
"XnNX",
"XnNX",
"XbcX",
"XacX",
"XbcX",
"XOOX",
"XljX",
"XllX",
".XX.",
]),
'raise': ((2, 9), (1, 1), [
".XX.",
"XljX",
"XllX",
"XOOX",
"XbcX",
"XacX",
".XbcX",
".XnNX",
".XnNX",
"..XnX",
]),
'forward': ((1, 1), (11, 1), [
".XXXXXXXXXXX.",
"XnnnnXbaacOljX",
"XnNNNXbbccOllX",
".XXXXXXXXXXXX.",
]),
'low': ((1, 0), (7, 9), [
"XnX......",
"XnX......",
"XnnX.....",
".XnNX....",
"..XbcX...",
"..XacX...",
"...XbcX..",
"...XOOX..",
"....XljX.",
"....XllX.",
".....XX..",
]),
'guard': ((1, 7), (6, 1), [
".....XX.",
"....XljX",
"....XllX",
"...XOOX.",
"..XbcX..",
".XacX...",
"XnNX....",
"XnNX....",
]),
}

FAR_ARM = {
'rest': ((1, 0), [
"XnX.",
"XnNX",
"XnNX",
"XnNX",
"XbcX",
"XacdX",
"XbcdX",
"XOOX.",
"XljX.",
"XllX.",
".XX..",
]),
'back': ((1, 0), [
"XnX...",
"XnNX..",
".XnNX.",
".XnNX.",
"..XbcX",
"..XacX",
"..XbcX",
"..XOOX",
"..XljX",
"..XllX",
"...XX.",
]),
'up': ((1, 5), [
".XX.",
"XljX",
"XllX",
"XbcX",
"XacX",
"XnNX",
]),
}

# ---------------------------------------------------------------- skeleton offsets
HIP = (24, 29)                 # rest hip; soles end on row 46
BODY = {
    "neck": (1, -12),          # from hip
    "near_shoulder": (-3, 4),  # from neck
    "far_shoulder": (4, 3),
    "cape": (-3, 2),
    "skirt": (0, -3),          # from hip
    "legs_split": 8,           # column where the far leg starts in LEGS
}
