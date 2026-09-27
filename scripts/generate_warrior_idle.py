"""Bake the current anime artwork into a coherent pixel-art idle.

The source painting is immutable. A layered joint hierarchy animates breathing, elbows and secondary motion
while preserving the approved face and rigid hand/weapon attachment. Every
frame is baked at the same resolution and ground anchor; runtime does no warping.
"""
from pathlib import Path
import json
import math
import os

os.environ.setdefault('PYGAME_HIDE_SUPPORT_PROMPT', '1')
import pygame

try:
    from .warrior_rig import build_pose, separate_layers, render_pose
except ImportError:
    from warrior_rig import build_pose, separate_layers, render_pose

ROOT = Path(__file__).resolve().parents[1]
SIZE = 256
COUNT = 96
COLUMNS = 8
SECONDS = 1 / 30
SOURCE = ROOT / 'assets/characters/warrior-source-v2.png'


def source_canvas(path=SOURCE):
    original = pygame.image.load(str(SOURCE))
    bounds = original.get_bounding_rect(min_alpha=128)
    source = pygame.image.load(str(path))
    if source.get_size() != original.get_size():
        source = pygame.transform.scale(source, original.get_size())
    height = 238
    width = round(bounds.width * height / bounds.height)
    source = pygame.transform.scale(source.subsurface(bounds), (width, height))
    canvas = pygame.Surface((SIZE, SIZE), pygame.SRCALPHA)
    canvas.blit(source, ((SIZE-width)//2, 8))
    # Fully opaque pixel clusters or full transparency, never a fuzzy aura.
    for y in range(SIZE):
        for x in range(SIZE):
            color = canvas.get_at((x,y))
            canvas.set_at((x,y), (*color[:3], 255) if color.a >= 160 else (0,0,0,0))
    return canvas


def render_frames(base):
    backing = source_canvas(ROOT/'assets/characters/warrior-rig-backing.png')
    layers = separate_layers(base, backing)
    layer_dir = ROOT/'assets/characters/warrior_rig'
    layer_dir.mkdir(parents=True, exist_ok=True)
    for name, layer in layers.items():
        pygame.image.save(layer, str(layer_dir/f'{name}.png'))
    return [render_pose(layers, build_pose(i/COUNT)) for i in range(COUNT)]


def main():
    directory = ROOT/'assets/characters/warrior_idle'
    directory.mkdir(parents=True, exist_ok=True)
    output = ROOT/'output'
    output.mkdir(exist_ok=True)
    frames = render_frames(source_canvas())
    sheet = pygame.Surface((SIZE*COLUMNS,SIZE*(COUNT//COLUMNS)),pygame.SRCALPHA)
    for index, frame in enumerate(frames):
        sheet.blit(frame,(index%COLUMNS*SIZE,index//COLUMNS*SIZE))
        pygame.image.save(frame,str(directory/f'idle_{index:02}.png'))
    pygame.image.save(sheet,str(ROOT/'assets/characters/redhead_idle.png'))
    pygame.image.save(pygame.transform.scale(sheet,(1536,2304)),str(output/'hero-frames.png'))
    pygame.image.save(pygame.transform.scale(frames[0],(384,384)),str(output/'warrior-v2-preview.png'))
    manifest = {'source':SOURCE.name,'method':'layered-joint-rig','frame_size':[SIZE,SIZE],'columns':COLUMNS,
                'rows':COUNT//COLUMNS,'frame_seconds':SECONDS,'anchor':[128,246],
                'frames':[{'file':f'idle_{i:02}.png','phase':round(math.tau*i/COUNT,6)}
                          for i in range(COUNT)]}
    (directory/'poses.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    (output/'hero-idle-preview.html').write_text(PREVIEW,encoding='utf-8')
    print(f'Baked {COUNT} consistent poses; {COUNT*SECONDS:.2f}s loop.')


PREVIEW = '''<!doctype html><html lang="es"><meta charset="utf-8">
<title>La Guerrera · Idle anime</title><style>
body{margin:0;background:#141723;color:#e9dfc7;font:16px system-ui}main{max-width:1100px;margin:30px auto;padding:24px}h1{font-size:36px}small{color:#e2a55f;letter-spacing:3px}.stage{display:flex;gap:32px;align-items:center;background:#202936;border:1px solid #465060;border-radius:12px;padding:24px}canvas{image-rendering:pixelated;width:384px;height:384px;flex-shrink:0}button,input{accent-color:#e49a59}button{background:#394c51;color:#fff;border:1px solid #719083;padding:12px;margin:4px;cursor:pointer;border-radius:6px}.grid{display:grid;grid-template-columns:repeat(8,1fr);gap:6px;margin-top:24px}.grid button{padding:4px;font-size:12px;background:#202936}.grid img{width:100%;image-rendering:pixelated}.selected{outline:2px solid #e49a59}p{line-height:1.7;color:#b7c4c8}@media(max-width:750px){.stage{flex-direction:column}.grid{grid-template-columns:repeat(4,1fr)}}
</style><main><small>LAST WISH / ANIMACIÓN ARTICULADA</small><h1>La Guerrera pelirroja</h1><div class="stage"><canvas width="256" height="256"></canvas><div><h2>Idle · Anime de mazmorras</h2><p>96 fotogramas · 3.2 segundos<br>Rostro estable · Respiración suave<br>Hombros y codos articulados<br>Espada unida a la mano · Pelo y capa con retraso.</p><button id="play">Pausar</button><button id="prev">←</button><button id="next">→</button><p id="label"></p><label>Velocidad <input id="speed" type="range" min="0.25" max="1.5" step="0.25" value="1"></label><p><label>Tamaño <select id="size"><option value="192">Combate · 192 px</option><option value="96">Selección · 96 px</option><option value="384" selected>Detalle · 384 px</option></select></label></p></div></div><p>Selecciona un fotograma para inspeccionarlo. Comprueba el cierre del ciclo entre 64 y 1.</p><div class="grid"></div></main>
<script>
const canvas=document.querySelector('canvas'),ctx=canvas.getContext('2d'),sheet=new Image();sheet.src='../assets/characters/redhead_idle.png';let current=0,playing=true,elapsed=0,last=0;const grid=document.querySelector('.grid');
function select(i){current=(i+96)%96;elapsed=current*(1000/30);playing=false;update()}
for(let i=0;i<96;i++){const b=document.createElement('button');b.innerHTML=`<img src="../assets/characters/warrior_idle/idle_${String(i).padStart(2,'0')}.png"><br>${String(i+1).padStart(2,'0')}`;b.onclick=()=>select(i);grid.append(b)}
function update(){document.querySelector('#play').textContent=playing?'Pausar':'Reproducir';document.querySelector('#label').textContent=`Fotograma ${current+1} / 96`;[...grid.children].forEach((b,i)=>b.classList.toggle('selected',i===current));ctx.clearRect(0,0,256,256);if(sheet.complete&&sheet.naturalWidth)ctx.drawImage(sheet,(current%8)*256,Math.floor(current/8)*256,256,256,0,0,256,256)}
document.querySelector('#play').onclick=()=>{playing=!playing;update()};document.querySelector('#prev').onclick=()=>select(current-1);document.querySelector('#next').onclick=()=>select(current+1);document.querySelector('#size').onchange=e=>{canvas.style.width=e.target.value+'px';canvas.style.height=e.target.value+'px'};
function tick(now){if(last&&playing){elapsed=(elapsed+(now-last)*Number(document.querySelector('#speed').value))%3200;current=Math.floor(elapsed/(1000/30))}last=now;update();requestAnimationFrame(tick)}requestAnimationFrame(tick);
</script></html>'''

if __name__ == '__main__':
    main()
