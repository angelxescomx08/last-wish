"""Bake the generated rogue v2 pose atlas into the existing hero sheet contract.

Run with .venv/Scripts/python.exe scripts/generate_rogue_v2_sprites.py.
Source artwork remains immutable; nearest-neighbour sampling preserves hard pixels.
"""
from pathlib import Path
import json
import os

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import pygame

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets" / "characters"
OUTPUT = ROOT / "output"
NAMES = ("idle", "attack", "guard", "hurt", "cast", "death")
TIMINGS = {
    "idle": [100] * 16,
    "attack": [65, 85, 60, 55, 65, 75, 85, 90],
    "guard": [60, 70, 75, 85, 85, 70, 65, 70],
    "hurt": [35, 55, 90, 80, 70, 65, 65, 70],
    "cast": [65, 75, 85, 100, 90, 80, 75, 80],
    "death": [70, 100, 110, 120, 140, 140, 180, 300],
}


COUNTS = {"idle": 48, "attack": 24, "guard": 24, "hurt": 24, "cast": 24, "death": 48}
for name, count in COUNTS.items():
    total = sum(TIMINGS[name])
    TIMINGS[name] = [round((i+1)*total/count)-round(i*total/count) for i in range(count)]


def load_poses():
    from rogue_rig import separate_layers, pose_at, render_pose
    base = pygame.image.load(str(ASSETS / "rogue-rig-base.png"))
    layers = separate_layers(base)
    layer_dir = ASSETS / "rogue_rig"
    layer_dir.mkdir(exist_ok=True)
    for name, layer in layers.items():
        pygame.image.save(layer, str(layer_dir / f"{name}.png"))
    return {name: [render_pose(layers, pose_at(name, i/(count if name == "idle" else count-1)))
                   for i in range(count)] for name,count in COUNTS.items()}


def bake():
    rows = load_poses()
    atlas = pygame.Surface((96 * max(COUNTS.values()), 96 * 6), pygame.SRCALPHA)
    frames_dir = ASSETS / "rogue_v2_frames"
    frames_dir.mkdir(exist_ok=True)
    for row, name in enumerate(NAMES):
        for index, frame in enumerate(rows[name]):
            atlas.blit(frame, (index * 96, row * 96))
            pygame.image.save(frame, str(frames_dir / f"{name}_{index:02}.png"))
    pygame.image.save(atlas, str(ASSETS / "rogue_v2_sheet_96.png"))
    pygame.image.save(pygame.transform.scale(atlas, (atlas.get_width()*2, atlas.get_height()*2)), str(ASSETS / "rogue_v2_sheet.png"))
    meta = {
        "cell": 192, "columns": max(COUNTS.values()),
        "sheets": {"192": "rogue_v2_sheet.png", "96": "rogue_v2_sheet_96.png"},
        "events": {"attack": {"strike_frame": 10}},
        "animations": {name: {"row": row, "frames": len(rows[name]),
            "durations_ms": TIMINGS[name], "loop": name == "idle"}
            for row, name in enumerate(NAMES)},
        "source": "rogue-rig-base.png", "rig": "scripts/rogue_rig.py",
        "generator": "scripts/generate_rogue_v2_sprites.py",
    }
    (ASSETS / "rogue_v2_sheet.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    (ASSETS / "rogue_sheet.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    OUTPUT.mkdir(exist_ok=True)
    review = pygame.Surface((8 * 192, 6 * 224))
    review.fill((18, 20, 34))
    for row, name in enumerate(NAMES):
        for column, frame in enumerate([rows[name][round(i*(len(rows[name])-1)/7)] for i in range(8)]):
            review.blit(pygame.transform.scale(frame, (192, 192)), (column * 192, row * 224 + 16))
    pygame.image.save(review, str(OUTPUT / "rogue-v2-contact.png"))
    write_preview(meta)
    print("Baked articulated rogue: 192 frames, six states, 96/192 px, HTML review")


def write_preview(meta):
    html = '''<!doctype html><html lang="es"><meta charset="utf-8"><title>La Pícara · revisión v2</title>
<style>body{background:#121422;color:#eee6ff;font:16px system-ui;margin:32px}button,select,input{font:inherit;padding:8px;background:#30283f;color:white;border:1px solid #776389;border-radius:6px}canvas{image-rendering:pixelated;background:radial-gradient(ellipse at bottom,#36314b,#191b2c);border-bottom:2px solid #887395;margin:16px}label{margin:12px}small{color:#c4b2ce}</style>
<h1>La Pícara · nuevo diseño</h1><p>Reposo, ataque, esquiva, daño, habilidad y derrota. Arte anterior conservado.</p>
<select id="state"></select><button id="play">Pausar</button><button id="step">Un fotograma</button><label>Velocidad <select id="speed"><option value="0.5">0.5×</option><option value="1" selected>1×</option><option value="1.5">1.5×</option></select></label><button id="restart">Reiniciar</button>
<p id="info"></p><canvas id="small" width="96" height="96"></canvas><canvas id="large" width="192" height="192"></canvas><canvas id="zoom" width="384" height="384"></canvas>
<p><small>96 px · selección / 192 px · combate / 384 px · detalle. La derrota conserva la última pose.</small></p>
<p><a style="color:#cab5ef" href="rogue-v2-contact.png">Ver todas las poses</a></p>
<script>
const meta=META, names={idle:'Reposo',attack:'Ataque',guard:'Esquiva / defensa',hurt:'Recibir daño',cast:'Habilidad',death:'Derrota'};
const image=new Image();image.src='../assets/characters/rogue_v2_sheet_96.png';
const state=document.querySelector('#state');Object.entries(names).forEach(([id,label])=>state.add(new Option(label,id)));
let elapsed=0, playing=true, previous=0;
function frameAt(a){let time=elapsed*1000,total=a.durations_ms.reduce((x,y)=>x+y,0);if(a.loop)time%=total;for(let i=0;i<a.frames;i++){if(time<a.durations_ms[i])return i;time-=a.durations_ms[i]}return a.frames-1}
function draw(){if(!image.complete)return;const a=meta.animations[state.value],f=frameAt(a);for(const id of ['small','large','zoom']){const c=document.getElementById(id),ctx=c.getContext('2d');ctx.imageSmoothingEnabled=false;ctx.clearRect(0,0,c.width,c.height);ctx.drawImage(image,f*96,a.row*96,96,96,0,0,c.width,c.height)}document.querySelector('#info').textContent=`${names[state.value]} · fotograma ${f+1}/${a.frames}`}
document.querySelector('#play').onclick=()=>{playing=!playing;document.querySelector('#play').textContent=playing?'Pausar':'Reproducir'};
document.querySelector('#step').onclick=()=>{playing=false;document.querySelector('#play').textContent='Reproducir';const a=meta.animations[state.value],next=(frameAt(a)+1)%a.frames;elapsed=a.durations_ms.slice(0,next).reduce((x,y)=>x+y,0)/1000+0.00001;draw()};
state.onchange=()=>{elapsed=0;draw()};document.querySelector('#restart').onclick=()=>{elapsed=0;draw()};
function tick(now){if(previous&&playing)elapsed+=(now-previous)/1000*Number(document.querySelector('#speed').value);previous=now;draw();requestAnimationFrame(tick)}requestAnimationFrame(tick);
</script></html>'''.replace('META', json.dumps(meta))
    (OUTPUT / "rogue-v2-preview.html").write_text(html, encoding="utf-8")


if __name__ == "__main__":
    bake()


