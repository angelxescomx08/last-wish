"""One-time conversion of the approved mage illustration into native pixel art.

mage-source.png has a dark vignette with a soft glow instead of transparency.
1. Background: estimate the smooth backdrop (darkest sixth of each 32 px cell,
   blurred), keep pixels that differ from it or are clearly coloured, protect the
   thin dark staff shaft explicitly, close small gaps (15 px) so dark interiors
   like the boots stay enclosed, then flood the outside from the image border.
2. Reduce by 8 into assets/characters/mage_base.png: light unsharp mask, block
   average, snap to a 64-colour palette (52 general + 12 from glowing accents so
   eyes, crystal and gems survive), then peel grey halo pixels off the edge.
Needs Pillow + numpy (dev only):

    uv run --with pillow --with numpy python scripts/make_mage_base.py
"""
from pathlib import Path
import colorsys
import numpy as np
from PIL import Image, ImageFilter
from collections import deque

ROOT = Path(__file__).resolve().parent.parent
src=Image.open(ROOT / 'assets/characters/mage-source.png').convert('RGB'); a=np.asarray(src).astype(np.int32); H,W,_=a.shape
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
# staff shaft: dark and thin, so protect it explicitly (line from under the hand to the ferrule)
yy,xx=np.mgrid[0:H,0:W]
p0=np.array([824,420.]); p1=np.array([734,1262.])
d=p1-p0; L2=(d**2).sum()
t=np.clip(((xx-p0[0])*d[0]+(yy-p0[1])*d[1])/L2,0,1)
dist=np.hypot(xx-(p0[0]+t*d[0]), yy-(p0[1]+t*d[1]))
staff=(dist<7)&(a.max(2)>9)
fg|=staff
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
_im=Image.fromarray(cut); from PIL import ImageFilter; _rgb=_im.convert('RGB').filter(ImageFilter.UnsharpMask(radius=5, percent=90, threshold=2)); _im=Image.merge('RGBA',(*_rgb.split(),_im.getchannel('A'))); src=np.asarray(_im).astype(np.int32)
H,W=src.shape[0]//F, src.shape[1]//F; src=src[:H*F,:W*F]
op=src[...,3]>128
rgb=src[...,:3]
mx=rgb.max(2); mn=rgb.min(2); sat=(mx-mn)/np.maximum(mx,1)
vivid=(sat>0.45)&(mx>110)
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
for _ in range(2):
    rm=[]
    for y in range(H):
        for x in range(W):
            if not out[y,x,3]: continue
            if not any(not(0<=y+dy<H and 0<=x+dx<W) or out[y+dy,x+dx,3]==0 for dy,dx in ((1,0),(-1,0),(0,1),(0,-1))): continue
            h,s,v=colorsys.rgb_to_hsv(*(out[y,x,:3]/255))
            if s<0.2 and 0.14<v<0.55: rm.append((y,x))
    for y,x in rm: out[y,x,3]=0
Image.fromarray(out).save(ROOT / 'assets/characters/mage_base.png')
print('wrote mage_base.png', out.shape[1], 'x', out.shape[0])
