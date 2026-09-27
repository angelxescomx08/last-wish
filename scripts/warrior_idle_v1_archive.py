"""Author the red-haired warrior on a native pixel grid, one pose at a time.

Run: .venv/Scripts/python.exe scripts/generate_warrior_idle.py
No raster warping, antialiasing, external art tools or runtime dependencies beyond pygame.
Coordinates and palette below are the editable source of the artwork.
"""
from pathlib import Path
import json
import math
import os

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('PYGAME_HIDE_SUPPORT_PROMPT', '1')
import pygame

ROOT = Path(__file__).resolve().parents[1]
SIZE = 96
COUNT = 32
COLUMNS = 8
SECONDS = 0.08
PALETTE = {
    'ink': '#201d2b', 'hair_dark': '#62283a', 'hair_shadow': '#a13c35',
    'hair': '#d65b36', 'hair_light': '#f68a47', 'hair_glint': '#ffc078',
    'skin_shadow': '#b86859', 'skin': '#efaa7d', 'skin_light': '#ffdbab',
    'steel_dark': '#3e4e64', 'steel': '#71899b', 'steel_light': '#b4ccd0',
    'shine': '#ecedd3', 'gold_dark': '#8c603f', 'gold': '#c39557',
    'gold_light': '#efd48a', 'cloth_dark': '#183c40', 'cloth': '#28605b',
    'cloth_light': '#448779', 'leather': '#503344', 'leather_light': '#805048',
    'eye': '#57bba0',
}


class PixelPen:
    def __init__(self, surface, dy=0):
        self.surface = surface
        self.dy = dy

    def shape(self, color, points, outline=False):
        points = [(x, y + self.dy) for x, y in points]
        pygame.draw.polygon(self.surface, PALETTE[color], points)
        if outline:
            pygame.draw.lines(self.surface, PALETTE['ink'], True, points, 1)

    def line(self, color, points, width=1):
        pygame.draw.lines(self.surface, PALETTE[color], False,
                          [(x, y + self.dy) for x, y in points], width)

    def box(self, color, x, y, w=1, h=1):
        pygame.draw.rect(self.surface, PALETTE[color], (x, y + self.dy, w, h))


def draw_legs(p):
    # Both soles and lower legs stay locked to the same ground plane.
    p.shape('leather', [(39,58),(49,60),(46,74),(42,84),(33,84),(35,74)], True)
    p.shape('leather_light', [(40,62),(44,63),(41,74),(37,77),(38,70)])
    p.shape('leather', [(51,60),(60,58),(60,72),(64,85),(55,85),(51,75)], True)
    p.shape('leather_light', [(55,64),(58,64),(58,73),(61,80),(56,78)])
    p.shape('steel_dark', [(34,75),(43,77),(40,86),(41,88),(40,91),(29,91),(29,88),(32,85)], True)
    p.shape('steel', [(35,77),(40,78),(37,85),(33,86)])
    p.line('steel_light', [(35,78),(34,82)])
    p.shape('steel_dark', [(54,77),(62,76),(63,85),(68,88),(68,91),(55,91),(54,87)], True)
    p.shape('steel', [(56,79),(60,78),(60,85),(64,88),(57,88)])
    p.line('steel_light', [(57,80),(57,84)])
    p.line('gold', [(33,77),(40,79)])
    p.line('gold', [(55,79),(61,78)])
    p.line('leather_light', [(30,89),(38,89)])
    p.line('leather_light', [(57,90),(66,90)])


def draw_cape(p, sway):
    p.shape('cloth_dark', [(39,29),(56,31),(57,49),(54+sway,68),
                          (45+sway,65),(37+sway,70),(23+sway,64),(29,45)], True)
    p.shape('cloth', [(37,34),(42,35),(37,53),(30+sway,65),(25+sway,62),(32,46)])
    p.shape('cloth_light', [(37,36),(39,36),(34,51),(28+sway,61),(30+sway,53)])
    p.shape('cloth', [(47,38),(51,40),(50+sway,62),(44+sway,65),(45,52)])
    p.line('gold_dark', [(24+sway,63),(36+sway,68),(43+sway,63)])


def draw_torso(p):
    # Waist overlaps the stationary pelvis, allowing breathing without a cut seam.
    p.shape('leather', [(40,46),(57,46),(61,63),(54,67),(49,60),(43,66),(34,62)], True)
    p.shape('cloth', [(44,51),(50,53),(48,62),(43,65),(41,63)], True)
    p.shape('cloth_light', [(45,55),(47,55),(45,62)])
    p.shape('steel_dark', [(38,32),(45,29),(54,30),(60,35),(56,43),(55,48),(43,50),(39,42)], True)
    p.shape('steel', [(42,33),(50,34),(56,33),(57,38),(53,42),(43,42),(40,38)])
    p.shape('steel_light', [(42,33),(48,34),(47,39),(42,38),(40,36)])
    p.line('shine', [(42,33),(46,34)])
    p.shape('steel', [(43,44),(53,44),(54,47),(44,48)])
    p.line('steel_light', [(45,44),(51,44)])
    p.shape('leather', [(39,49),(55,47),(57,51),(40,54)], True)
    p.box('gold', 48,48,5,5)
    p.box('ink', 49,49,3,3)
    p.box('gold_light', 48,48,4,1)
    p.shape('leather_light', [(37,52),(42,53),(40,59),(35,58)], True)
    p.box('gold', 38,54,2,1)
    # Rear arm, resting beside the hip.
    p.shape('steel_dark', [(57,35),(61,36),(63,45),(61,51),(57,48),(58,43)], True)
    p.line('steel_light', [(60,38),(61,43)])
    p.shape('leather', [(58,48),(62,49),(63,54),(60,57),(57,54)], True)
    p.line('leather_light', [(59,50),(60,54)])


def draw_head(p, hair):
    p.shape('hair_dark', [(40,14),(36,10),(31,11),(28,16),(28+hair,24),
                         (24+hair,33),(27+hair,39),(32+hair,35),(35+hair,27),(39,23)], True)
    p.shape('hair_shadow', [(33,13),(36,14),(34+hair,23),(29+hair,33),(27+hair,35),(29+hair,25),(30,17)])
    p.line('hair', [(33,14),(31,21),(31+hair,26),(28+hair,31)])
    p.box('gold',36,13,3,3)
    p.shape('skin_shadow', [(46,24),(53,24),(52,30),(55,31),(48,34),(43,30)], True)
    p.shape('skin', [(47,25),(51,25),(50,30),(47,30)])
    p.shape('skin', [(41,14),(48,10),(57,12),(61,17),(60,24),(57,28),(51,30),(45,27),(41,23)], True)
    p.shape('skin_light', [(47,16),(55,14),(59,17),(58,23),(55,26),(51,27),(46,24)])
    p.shape('skin_shadow', [(41,20),(44,19),(46,22),(44,25),(41,23)])
    p.box('skin_light',42,21,2,2)
    # Angular anime eyes, with consistent gaze to screen right.
    p.line('hair_dark', [(48,18),(51,17)])
    p.line('hair_dark', [(56,17),(58,18)])
    p.line('ink', [(47,20),(49,19),(52,20)])
    p.box('shine',48,20,4,3)
    p.box('eye',50,20,2,3)
    p.box('ink',51,20,1,2)
    p.box('shine',50,20)
    p.line('ink', [(56,20),(58,19),(59,20)])
    p.box('eye',57,20,2,2)
    p.box('ink',58,20)
    p.box('skin_shadow',56,23)
    p.line('skin_shadow', [(53,26),(55,26)])
    p.shape('hair_shadow', [(39,22),(37,16),(39,10),(44,7),(53,7),(60,10),(62,14),
                            (61,21),(58,18),(56,12),(52,16),(47,18),(48,14),(43,19),(44,24)], True)
    p.shape('hair', [(39,16),(41,11),(46,9),(52,9),(48,13),(43,16),(44,13)])
    p.shape('hair_light', [(42,11),(46,9),(50,9),(46,11),(43,14)])
    p.shape('hair', [(53,9),(58,11),(60,14),(59,17),(56,12),(52,15)])
    p.line('hair_glint', [(44,10),(47,9)])
    p.line('hair_light', [(55,10),(58,12)])
    # Short mantle and gold fastening tie head and shoulders together.
    p.shape('cloth', [(43,29),(48,31),(53,29),(57,31),(53,35),(46,34),(40,32)], True)
    p.line('cloth_light', [(43,30),(48,32),(52,31)])
    p.box('gold_dark',52,32,3,3)
    p.box('gold_light',53,32,2,2)


def draw_sword_arm(p, wrist):
    p.shape('steel', [(38,32),(42,35),(40,40),(34,41),(31,38),(33,34)], True)
    p.shape('steel_light', [(35,34),(38,33),(40,36),(35,37),(33,37)])
    p.line('gold', [(32,38),(35,40),(40,39)])
    p.shape('leather_light', [(34,41),(39,41),(36,48),(33,52),(29,50)], True)
    p.shape('steel_dark', [(31,47),(36,49),(33+wrist,55),(29+wrist,55),(28,52)], True)
    p.line('steel', [(31,49),(33,50),(31+wrist,53)])
    # All weapon vertices share the hand's displacement: no sliding grip.
    x = wrist
    p.line('ink', [(29+x,53),(36+x,61)], 5)
    p.line('leather_light', [(29+x,53),(36+x,61)], 3)
    p.shape('steel', [(36+x,60),(39+x,59),(69+x,73),(74+x,78),(67+x,77),(35+x,64)], True)
    p.shape('steel_light', [(39+x,61),(68+x,74),(72+x,77),(37+x,63)])
    p.line('shine', [(40+x,61),(67+x,74)])
    p.line('steel_dark', [(39+x,64),(67+x,76)])
    p.line('ink', [(32+x,65),(41+x,57)], 4)
    p.line('gold', [(32+x,65),(41+x,57)], 2)
    p.box('gold_light',39+x,57,2,2)
    p.shape('leather', [(29+x,52),(33+x,53),(34+x,57),(31+x,59),(28+x,56)], True)
    p.line('leather_light', [(30+x,54),(32+x,56)])


def pose(index):
    phase = math.tau * index / COUNT
    return {
        'lift': round(1 - math.cos(phase)),
        'hair': round(1.5 * math.sin(phase - 0.65)),
        'cape': round(1.5 * math.sin(phase - 1.1)),
        'wrist': round(0.55 * math.sin(phase - 0.3)),
        'blink': {22: 'half', 23: 'closed', 24: 'half'}.get(index, 'open'),
    }


def render_frame(index):
    state = pose(index)
    frame = pygame.Surface((SIZE, SIZE), pygame.SRCALPHA)
    upper = PixelPen(frame, -state['lift'])
    draw_cape(upper, state['cape'])
    draw_legs(PixelPen(frame))
    draw_torso(upper)
    draw_head(upper, state['hair'])
    if state['blink'] != 'open':
        upper.box('skin_light',47,19,6,4)
        upper.box('skin_light',56,19,4,3)
        upper.line('ink', [(48,21),(51,21)])
        upper.line('ink', [(57,21),(58,21)])
        if state['blink'] == 'half':
            upper.box('eye',50,22,2,1)
            upper.box('eye',58,22)
    draw_sword_arm(upper, state['wrist'])
    return frame


def main():
    directory = ROOT / 'assets/characters/warrior_idle'
    directory.mkdir(parents=True, exist_ok=True)
    output = ROOT / 'output'
    output.mkdir(exist_ok=True)
    sheet = pygame.Surface((COLUMNS*SIZE, 4*SIZE), pygame.SRCALPHA)
    for index in range(COUNT):
        frame = render_frame(index)
        sheet.blit(frame, (index % COLUMNS*SIZE, index // COLUMNS*SIZE))
        pygame.image.save(frame, str(directory / f'idle_{index:02}.png'))
    pygame.image.save(sheet, str(ROOT / 'assets/characters/redhead_idle.png'))
    pygame.image.save(pygame.transform.scale(sheet, (1536,768)), str(output / 'hero-frames.png'))
    manifest = {'frame_size': [SIZE,SIZE], 'columns': COLUMNS, 'rows':4,
                'frame_seconds': SECONDS, 'anchor':[48,92], 'frames':[
                    {'file':f'idle_{i:02}.png', **pose(i)} for i in range(COUNT)]}
    (directory / 'poses.json').write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf-8')
    (output / 'hero-idle-preview.html').write_text(PREVIEW, encoding='utf-8')
    print(f'Generated {COUNT} frames, sprite sheet, pose manifest and interactive preview.')


PREVIEW = '''<!doctype html><html lang="es"><meta charset="utf-8">
<title>La Guerrera · Estudio de idle</title><style>
body{margin:0;background:#141723;color:#e9dfc7;font:16px system-ui}main{max-width:1060px;margin:40px auto;padding:24px}
h1{font-size:36px}small{color:#e2a55f;letter-spacing:3px}.stage{display:flex;gap:48px;align-items:center;background:repeating-linear-gradient(0deg,#202936 0 47px,#1b2330 48px 50px);border:1px solid #465060;border-radius:12px;padding:24px}
canvas{image-rendering:pixelated;width:384px;height:384px;flex-shrink:0}button,input{accent-color:#e49a59}button{background:#394c51;color:#fff;border:1px solid #719083;padding:12px;margin:4px;cursor:pointer;border-radius:6px}.grid{display:grid;grid-template-columns:repeat(8,1fr);gap:6px;margin-top:24px}.grid button{padding:4px;font-size:12px;background:#202936}.grid img{width:100%;image-rendering:pixelated}.selected{outline:2px solid #e49a59}p{line-height:1.7;color:#b7c4c8}@media(max-width:750px){.stage{flex-direction:column}.grid{grid-template-columns:repeat(4,1fr)}}
</style><main><small>LAST WISH / ARTE DE PERSONAJES</small><h1>La Guerrera pelirroja</h1><div class="stage"><canvas width="96" height="96"></canvas><div><h2>En guardia, en calma.</h2><p>32 fotogramas · 2.56 segundos<br>Pixel art nativo de 96 × 96<br>Respiración, cabello, capa y parpadeo.</p><button id="play">Pausar</button><button id="prev">←</button><button id="next">→</button><p id="label"></p><label>Velocidad <input id="speed" type="range" min="0.25" max="1.5" step="0.25" value="1"></label></div></div><p>Selecciona un fotograma para inspeccionarlo. Los pies permanecen apoyados durante todo el ciclo.</p><div class="grid"></div></main>
<script>
const canvas=document.querySelector('canvas'),ctx=canvas.getContext('2d'),sheet=new Image();sheet.src='../assets/characters/redhead_idle.png';let current=0,playing=true,elapsed=0,last=0;const grid=document.querySelector('.grid');
function select(i){current=(i+32)%32;elapsed=current*80;playing=false;update()}
for(let i=0;i<32;i++){const b=document.createElement('button');b.innerHTML=`<img src="../assets/characters/warrior_idle/idle_${String(i).padStart(2,'0')}.png"><br>${String(i+1).padStart(2,'0')}`;b.onclick=()=>select(i);grid.append(b)}
function update(){document.querySelector('#play').textContent=playing?'Pausar':'Reproducir';document.querySelector('#label').textContent=`Fotograma ${current+1} / 32`;[...grid.children].forEach((b,i)=>b.classList.toggle('selected',i===current));ctx.clearRect(0,0,96,96);if(sheet.complete&&sheet.naturalWidth)ctx.drawImage(sheet,(current%8)*96,Math.floor(current/8)*96,96,96,0,0,96,96)}
document.querySelector('#play').onclick=()=>{playing=!playing;update()};document.querySelector('#prev').onclick=()=>select(current-1);document.querySelector('#next').onclick=()=>select(current+1);
function tick(now){if(last&&playing){elapsed=(elapsed+(now-last)*Number(document.querySelector('#speed').value))%2560;current=Math.floor(elapsed/80)}last=now;update();requestAnimationFrame(tick)}requestAnimationFrame(tick);
</script></html>'''

if __name__ == '__main__':
    main()
