"""Bake the mage's articulated pixel art and restrained magic into hero sheets.

Run with .venv/Scripts/python.exe scripts/generate_mage_v2_sprites.py.
The original mage assets and generator are preserved before runtime activation.
"""
from pathlib import Path
import json
import math
import os
import shutil

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import pygame

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets" / "characters"
OUTPUT = ROOT / "output"
NAMES = ("idle", "attack", "guard", "hurt", "cast", "death")
TOTAL_MS = {"idle": 1600, "attack": 800, "guard": 720, "hurt": 600, "cast": 1000, "death": 1400}
COUNTS = {"idle": 48, "attack": 44, "guard": 40, "hurt": 36, "cast": 56, "death": 72}
TIMINGS = {
    name: [round((i + 1) * TOTAL_MS[name] / count) - round(i * TOTAL_MS[name] / count)
           for i in range(count)]
    for name, count in COUNTS.items()
}
STRIKE_FRAME = 19
CAST_FRAME = 28
CYAN = (115, 217, 255)
PALE = (222, 249, 255)
VIOLET = (152, 137, 240)


def backup_legacy():
    """Keep the first legacy backup immutable across subsequent rebuilds."""
    backup = ASSETS / "mage_legacy"
    backup.mkdir(exist_ok=True)
    original_names = ("mage-source.png", "mage_base.png", "mage_sheet.png", "mage_sheet_96.png", "mage_sheet.json")
    for name in original_names:
        source, target = ASSETS / name, backup / name
        if target.exists() or not source.exists():
            continue
        if name.endswith(".json"):
            active = json.loads(source.read_text(encoding="utf-8"))
            if "mage_v2_sheet.png" in active.get("sheets", {}).values():
                raise RuntimeError("Legacy metadata must be backed up before activating mage v2")
        shutil.copy2(source, target)
    for name in ("generate_mage_sprites.py", "make_mage_base.py", "make_hero_base.py"):
        source, target = ROOT / "scripts" / name, backup / name
        if source.exists() and not target.exists():
            shutil.copy2(source, target)


def phase_for(name, index):
    count = COUNTS[name]
    return index / (count if name == "idle" else count - 1)


def draw_magic(frame, pose, name, phase, scale):
    """Small hard-edged accents follow the free palm; body acting stays visible."""
    if name not in ("attack", "guard", "cast") or phase <= 0 or phase >= 1:
        return
    from mage_rig import magic_origin
    ox, oy = magic_origin(pose, name)
    start, finish = {"attack": (.15, .68), "guard": (.14, .83), "cast": (.12, .86)}[name]
    if not start < phase < finish:
        return
    local = (phase - start) / (finish - start)
    power = math.sin(math.pi * local) ** 2
    if power < .06:
        return
    center = (round((ox + 3) * scale), round(oy * scale))
    radius = (2.5 if name == "attack" else 4.5) * power
    # Outline diamonds and two orbiting motes leave the palm readable.
    points = [(center[0] + round(x * radius * scale), center[1] + round(y * radius * scale))
              for x, y in ((0, -1), (1, 0), (0, 1), (-1, 0))]
    pygame.draw.lines(frame, CYAN, True, points, max(1, scale))
    for index in range(2):
        angle = math.tau * (local * .65 + index / 2)
        distance = 3 + 3 * power
        x = round((ox + 3 + math.cos(angle) * distance) * scale)
        y = round((oy + math.sin(angle) * distance) * scale)
        pygame.draw.rect(frame, VIOLET if index else PALE, (x, y, scale, scale))
    if name == "attack" and .40 < phase < .57:
        release = (phase - .40) / .17
        # A short departing spark complements the runtime projectile.
        x = ox + 5 + 9 * release
        y = oy - 2 * release
        pygame.draw.line(frame, CYAN, (round((x - 2) * scale), round(y * scale)),
                         (round(x * scale), round(y * scale)), max(1, scale))


def load_poses():
    from mage_rig import prepare_base, split_layers, pose_at, render_pose
    base = prepare_base()
    layers = split_layers(base)
    layer_dir = ASSETS / "mage_rig"
    layer_dir.mkdir(exist_ok=True)
    for name, layer in layers.items():
        pygame.image.save(layer, str(layer_dir / f"{name}.png"))
    result = []
    for scale in (1, 2):
        rows = {}
        for name in NAMES:
            rows[name] = []
            for index in range(COUNTS[name]):
                phase = phase_for(name, index)
                pose = pose_at(name, phase)
                frame = render_pose(layers, pose, scale=scale)
                draw_magic(frame, pose, name, phase, scale)
                rows[name].append(frame)
        result.append(rows)
    return result


def build_metadata():
    from mage_rig import pose_at, magic_origin
    def point_at(name, index):
        point = magic_origin(pose_at(name, phase_for(name, index)), name)
        return [round(value, 3) for value in point]
    return {
        "cell": 192, "columns": max(COUNTS.values()),
        "sheets": {"192": "mage_v2_sheet.png", "96": "mage_v2_sheet_96.png"},
        "events": {
            "attack": {"strike_frame": STRIKE_FRAME, "strike_point": point_at("attack", STRIKE_FRAME)},
            "cast": {"cast_frame": CAST_FRAME, "cast_point": point_at("cast", CAST_FRAME)},
        },
        "animations": {
            name: {"row": row, "frames": COUNTS[name], "durations_ms": TIMINGS[name], "loop": name == "idle"}
            for row, name in enumerate(NAMES)
        },
        "source": "mage-source-v2.png", "base": "mage-rig-base.png",
        "rig": "scripts/mage_rig.py", "generator": "scripts/generate_mage_v2_sprites.py",
    }


def bake():
    backup_legacy()
    rows, large_rows = load_poses()
    frames_dir = ASSETS / "mage_v2_frames"
    frames_dir.mkdir(exist_ok=True)
    for cell, source, filename in ((96, rows, "mage_v2_sheet_96.png"), (192, large_rows, "mage_v2_sheet.png")):
        atlas = pygame.Surface((cell * max(COUNTS.values()), cell * len(NAMES)), pygame.SRCALPHA)
        for row, name in enumerate(NAMES):
            for index, frame in enumerate(source[name]):
                atlas.blit(frame, (index * cell, row * cell))
                if cell == 96:
                    pygame.image.save(frame, str(frames_dir / f"{name}_{index:02}.png"))
        pygame.image.save(atlas, str(ASSETS / filename))
    OUTPUT.mkdir(exist_ok=True)
    contact = pygame.Surface((8 * 192, len(NAMES) * 224))
    contact.fill((18, 20, 34))
    for row, name in enumerate(NAMES):
        for column in range(8):
            index = round(column * (COUNTS[name] - 1) / 7)
            contact.blit(large_rows[name][index], (column * 192, row * 224 + 16))
    pygame.image.save(contact, str(OUTPUT / "mage-v2-contact.png"))
    meta = build_metadata()
    write_preview(meta)
    encoded = json.dumps(meta, indent=2) + "\n"
    (ASSETS / "mage_v2_sheet.json").write_text(encoded, encoding="utf-8")
    (ASSETS / "mage_sheet.json").write_text(encoded, encoding="utf-8")
    print(f"Baked mage: {sum(COUNTS.values())} frames, six states, native 96/192 px and HTML review")


def write_preview(meta):
    html = '''<!doctype html>
<html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>El Mago · animaciones</title>
<style>
*{box-sizing:border-box}body{background:#101724;color:#e7edf6;font:16px system-ui;margin:0;padding:28px;max-width:1100px}h1{margin:0 0 12px}p{line-height:1.5;color:#b7c5d8}.controls{display:flex;gap:10px;align-items:center;flex-wrap:wrap}button,select{font:inherit;padding:9px 12px;background:#22314b;color:#e7edf6;border:1px solid #506485;border-radius:6px}button:focus-visible,select:focus-visible{outline:3px solid #87dafa}label{display:flex;gap:8px;align-items:center}.previews{display:flex;align-items:flex-end;gap:24px;flex-wrap:wrap}figure{margin:12px 0}canvas{display:block;image-rendering:pixelated;background:radial-gradient(ellipse at bottom,#2b3a53,#141e30);border-bottom:2px solid #667995}figcaption{padding-top:8px;color:#b7c5d8;font-size:14px}a{color:#94dbff}.note{font-size:14px}#info{min-height:24px}
</style>
<h1>El Mago · nuevo pixel art</h1>
<p>Movimiento del cuerpo, lanzamiento de magia, defensa, reacción al golpe y derrota. El diseño anterior está conservado.</p>
<div class="controls"><label>Animación <select id="state"></select></label><button id="play">Pausar</button><button id="step">Un fotograma</button><button id="restart">Reiniciar</button><label>Velocidad <select id="speed"><option value="0.5">0.5×</option><option value="1" selected>1×</option><option value="1.5">1.5×</option></select></label><label><input id="repeat" type="checkbox" checked> Repetir acción</label></div>
<p id="info" aria-live="off"></p><div class="previews"><figure><canvas id="small" width="96" height="96" aria-label="Animación a 96 píxeles"></canvas><figcaption>96 px · selección</figcaption></figure><figure><canvas id="large" width="192" height="192" aria-label="Animación a 192 píxeles"></canvas><figcaption>192 px · combate</figcaption></figure><figure><canvas id="zoom" width="384" height="384" aria-label="Animación ampliada"></canvas><figcaption>384 px · inspección</figcaption></figure></div>
<p class="note">Las acciones vuelven al reposo y dejan una pausa breve al repetir. La derrota conserva su última pose. <a href="mage-v2-contact.png">Ver todas las poses</a> · <a href="mage-v2-preview.gif">Ver GIF</a></p>
<script>
const meta=META, names={idle:'Reposo',attack:'Ataque arcano',guard:'Defensa',hurt:'Recibir daño',cast:'Habilidad',death:'Derrota'};
const image=new Image(),nativeImage=new Image();image.src='../assets/characters/mage_v2_sheet.png';nativeImage.src='../assets/characters/mage_v2_sheet_96.png';
const state=document.querySelector('#state');Object.entries(names).forEach(([id,label])=>state.add(new Option(label,id)));
let elapsed=0,playing=true,previous=0;
function duration(a){return a.durations_ms.reduce((x,y)=>x+y,0)}
function frameAt(a){let time=elapsed*1000;if(a.loop)time%=duration(a);else if(state.value!=='death'&&document.querySelector('#repeat').checked)time%=duration(a)+500;for(let i=0;i<a.frames;i++){if(time<a.durations_ms[i])return i;time-=a.durations_ms[i]}return a.frames-1}
function draw(){if(!image.complete||!nativeImage.complete||!image.naturalWidth||!nativeImage.naturalWidth)return;const a=meta.animations[state.value],f=frameAt(a);for(const id of ['small','large','zoom']){const c=document.getElementById(id),ctx=c.getContext('2d'),cell=id==='small'?96:192;ctx.imageSmoothingEnabled=false;ctx.clearRect(0,0,c.width,c.height);ctx.drawImage(id==='small'?nativeImage:image,f*cell,a.row*cell,cell,cell,0,0,c.width,c.height)}const event=meta.events[state.value],impact=event&&(f===event.strike_frame||f===event.cast_frame)?' · Liberación de magia':'';document.querySelector('#info').textContent=`${names[state.value]} · fotograma ${f+1}/${a.frames}${impact}`}
document.querySelector('#play').onclick=()=>{playing=!playing;document.querySelector('#play').textContent=playing?'Pausar':'Reproducir'};
document.querySelector('#step').onclick=()=>{playing=false;document.querySelector('#play').textContent='Reproducir';const a=meta.animations[state.value],next=(frameAt(a)+1)%a.frames;elapsed=a.durations_ms.slice(0,next).reduce((x,y)=>x+y,0)/1000+0.000001;draw()};
state.onchange=()=>{elapsed=0;draw()};document.querySelector('#restart').onclick=()=>{elapsed=0;draw()};
function tick(now){if(previous&&playing)elapsed+=Math.min((now-previous)/1000,.1)*Number(document.querySelector('#speed').value);previous=now;draw();requestAnimationFrame(tick)}requestAnimationFrame(tick);
</script></html>'''.replace('META', json.dumps(meta))
    (OUTPUT / "mage-v2-preview.html").write_text(html, encoding="utf-8")


if __name__ == "__main__":
    bake()

