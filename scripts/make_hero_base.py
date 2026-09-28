"""One-time conversion of an approved hero illustration into native pixel art.

    uv run --with pillow --with numpy python scripts/make_hero_base.py mage
    uv run --with pillow --with numpy python scripts/make_hero_base.py rogue

Input ``assets/characters/<hero>-source.png`` (dark vignette with soft glow
instead of transparency); output ``assets/characters/<hero>_base.png``.

1. Background: estimate the smooth backdrop (darkest sixth of each 32 px cell,
   blurred), keep pixels that differ from it or are clearly coloured, protect
   thin dark parts listed in HEROES, close 15 px gaps so dark interiors (boots)
   stay enclosed, then flood the outside from the image border.
2. Reduce by 8: light unsharp mask, block average snapped to a 64-colour palette
   (52 general + 12 from glowing accents so eyes, crystals and gems survive),
   then peel grey halo pixels off the silhouette.
Needs Pillow + numpy (dev only).
"""
import colorsys
import sys
from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parent.parent

# per hero: thin dark segments to protect ((x0, y0), (x1, y1), radius) in source pixels
HEROES = {
    "mage": [((824, 420), (734, 1262), 7)],     # staff shaft below the hand
    "rogue": [],
}
# halo peeling: (passes, max brightness of a grey edge pixel to remove)
PEEL = {"mage": (2, 0.55), "rogue": (3, 0.74)}      # the rogue's daggers carry a bright glow
STEEL = {"mage": False, "rogue": True}


def convert(hero: str, protect=(), peel=(2, 0.55), steel=False) -> None:
    src=Image.open(ROOT / f'assets/characters/{hero}-source.png').convert('RGB'); a=np.asarray(src).astype(np.int32); H,W,_=a.shape
    lum=a.max(2)
    C=32
    gh,gw=H//C,W//C
    cells=np.zeros((gh,gw,3))
    for j in range(gh):
        for i in range(gw):
            blk=a[j*C:(j+1)*C, i*C:(i+1)*C].reshape(-1,3); l=blk.max(1)
            k=np.argsort(l)[:max(1,len(l)//6)]
            cells[j,i]=blk[k].mean(0)
    B=np.asarray(Image.fromarray(cells.clip(0,255).astype(np.uint8)).resize((W,H),Image.BICUBIC).filter(ImageFilter.GaussianBlur(20))).astype(np.int32)
    diff=np.abs(a-B).max(2)
    mx=a.max(2); mn=a.min(2); sat=(mx-mn)/np.maximum(mx,1)
    fg=(diff>20)|((sat>0.4)&(mx>40))
    # thin dark parts (e.g. a staff shaft) that look like background: protect explicitly
    yy,xx=np.mgrid[0:H,0:W]
    for (x0,y0),(x1,y1),rad in protect:
        p0=np.array([x0,y0],float); p1=np.array([x1,y1],float)
        d=p1-p0; L2=(d**2).sum()
        t=np.clip(((xx-p0[0])*d[0]+(yy-p0[1])*d[1])/L2,0,1)
        dist=np.hypot(xx-(p0[0]+t*d[0]), yy-(p0[1]+t*d[1]))
        fg|=(dist<rad)&(a.max(2)>9)
    # close small gaps in the silhouette edge so dark interiors (boots) stay enclosed
    fgi=Image.fromarray((fg*255).astype(np.uint8)).filter(ImageFilter.MaxFilter(15))
    fg_closed=np.asarray(fgi)>0
    fg_orig=fg
    fg=fg_closed
    # background = reachable from the border through non-fg pixels
    seen=np.zeros((H,W),bool); q=deque()
    for x in range(W):
        for y in (0,H-1):
            if not fg[y,x]: seen[y,x]=True; q.append((y,x))
    for y in range(H):
        for x in (0,W-1):
            if not fg[y,x] and not seen[y,x]: seen[y,x]=True; q.append((y,x))
    while q:
        y,x=q.popleft()
        for dy,dx in ((1,0),(-1,0),(0,1),(0,-1)):
            ny,nx=y+dy,x+dx
            if 0<=ny<H and 0<=nx<W and not seen[ny,nx] and not fg[ny,nx]:
                seen[ny,nx]=True; q.append((ny,nx))
    mask=~seen
    # undo the dilation on the outside, keeping every originally detected pixel
    er=np.asarray(Image.fromarray((mask*255).astype(np.uint8)).filter(ImageFilter.MinFilter(15)))>0
    mask=er|(mask&fg_orig)
    cut=np.dstack([a.astype(np.uint8),(mask*255).astype(np.uint8)])

    F=8
    _im=Image.fromarray(cut); _rgb=_im.convert('RGB').filter(ImageFilter.UnsharpMask(radius=5, percent=90, threshold=2)); _im=Image.merge('RGBA',(*_rgb.split(),_im.getchannel('A'))); src=np.asarray(_im).astype(np.int32)
    H,W=src.shape[0]//F, src.shape[1]//F; src=src[:H*F,:W*F]
    op=src[...,3]>128
    rgb=src[...,:3]
    mx=rgb.max(2); mn=rgb.min(2); sat=(mx-mn)/np.maximum(mx,1)
    vivid=(sat>0.45)&(mx>110)
    if steel:   # bright polished metal (blades) also counts as an accent to keep it crisp
        vivid|=(sat<0.2)&(mx>185)
    # palette: 52 general colours + 12 from vivid accents (eyes, crystal, gems)
    def mc(pix,n):
        q=Image.fromarray(pix.astype(np.uint8).reshape(1,-1,3)).quantize(colors=n, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
        return np.array(q.getpalette()[:n*3]).reshape(-1,3)
    pal=np.vstack([mc(rgb[op],52), mc(rgb[op&vivid],12)])
    out=np.zeros((H,W,4),np.uint8)
    for by in range(H):
        for bx in range(W):
            o=op[by*F:(by+1)*F, bx*F:(bx+1)*F]
            if o.mean()<0.5: continue
            px=rgb[by*F:(by+1)*F, bx*F:(bx+1)*F][o]
            vv=vivid[by*F:(by+1)*F, bx*F:(bx+1)*F][o]
            if vv.mean()>=0.2:
                target=px[vv].mean(0)            # keep small glowing accents
            else:
                target=px.mean(0)
            # pick the palette colour nearest to the block colour (no blending of palette)
            k=np.argmin(((pal-target)**2).sum(1))
            out[by,bx,:3]=pal[k]; out[by,bx,3]=255
    for _ in range(peel[0]):
        rm=[]
        for y in range(H):
            for x in range(W):
                if not out[y,x,3]: continue
                if not any(not(0<=y+dy<H and 0<=x+dx<W) or out[y+dy,x+dx,3]==0 for dy,dx in ((1,0),(-1,0),(0,1),(0,-1))): continue
                h,s,v=colorsys.rgb_to_hsv(*(out[y,x,:3]/255))
                if s<0.2 and 0.14<v<peel[1]: rm.append((y,x))
        for y,x in rm: out[y,x,3]=0
    Image.fromarray(out).save(ROOT / f'assets/characters/{hero}_base.png')
    print(f'wrote {hero}_base.png', out.shape[1], 'x', out.shape[0])


if __name__ == "__main__":
    for name in (sys.argv[1:] or list(HEROES)):
        convert(name, HEROES[name], PEEL[name], STEEL[name])
