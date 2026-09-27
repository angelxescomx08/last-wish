"""One-time conversion of the approved illustration into native pixel art.

warrior-source-v2.png was generated as pixel art on a ~4 px grid. This script
reduces it by 8 (half its art grid) into assets/characters/warrior_base.png:
colours are quantised to a 64-colour palette and every 8x8 block takes its
most common colour (dark outline colours win when they cover 30 % of the
block), so edges stay crisp. Needs Pillow + numpy (dev only):

    uv run --with pillow --with numpy python scripts/make_warrior_base.py
"""
from pathlib import Path
import numpy as np
from PIL import Image
ROOT = Path(__file__).resolve().parent.parent
src=Image.open(ROOT / 'assets/characters/warrior-source-v2.png').convert('RGBA')
a=np.asarray(src).astype(np.int32)
F=8
H,W=a.shape[0]//F, a.shape[1]//F
a=a[:H*F,:W*F]
opaque=a[...,3]>140
# palette quantize opaque colours
NC=64
samp=a[...,:3][opaque].astype('uint8').reshape(1,-1,3)
qs=Image.fromarray(samp).quantize(colors=NC, method=Image.Quantize.MAXCOVERAGE, dither=Image.Dither.NONE)
pal=np.array(qs.getpalette()[:NC*3]).reshape(-1,3)
rgb=Image.fromarray(a[...,:3].astype('uint8'))
idx=np.asarray(rgb.quantize(palette=qs, dither=Image.Dither.NONE)).astype(int)
lum=pal@np.array([0.3,0.59,0.11])
out=np.zeros((H,W,4),np.uint8)
for by in range(H):
    for bx in range(W):
        o=opaque[by*F:(by+1)*F, bx*F:(bx+1)*F]
        if o.mean()<0.45: continue
        ids=idx[by*F:(by+1)*F, bx*F:(bx+1)*F][o]
        cnt=np.bincount(ids,minlength=len(pal))
        dark=cnt[lum<45].sum()
        if dark>=0.3*o.sum():
            k=np.argmax(np.where(lum<45,cnt,-1))
        else:
            k=np.argmax(cnt)
        out[by,bx,:3]=pal[k]; out[by,bx,3]=255
im=Image.fromarray(out)
im.save(ROOT / 'assets/characters/warrior_base.png')
print(im.size)
