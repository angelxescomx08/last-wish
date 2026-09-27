"""Export an animated review with a fixed global palette. Requires Pillow."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parents[1]
OUTPUT=ROOT/'output'
SIZE=384
BACKGROUND='#202936'


def cell(sheet,index):
    x,y=index%8*256,index//8*256
    return sheet.crop((x,y,x+256,y+256)).resize((SIZE,SIZE),Image.Resampling.NEAREST)


def save_gif(frames,path):
    contact=Image.new('RGB',(384*8,384*12),BACKGROUND)
    for i,frame in enumerate(frames):
        contact.paste(frame.resize((384,384)),(i%8*384,i//8*384))
    palette=contact.quantize(colors=256)
    indexed=[f.quantize(palette=palette,dither=Image.Dither.NONE) for f in frames]
    indexed[0].save(path,save_all=True,append_images=indexed[1:],loop=0,
                    duration=[30,30,40]*32,disposal=2,optimize=False)


def main():
    sheet=Image.open(ROOT/'assets/characters/redhead_idle.png').convert('RGBA')
    before=Image.open(OUTPUT/'warrior-idle-before.png').convert('RGBA')
    font=ImageFont.load_default(size=18)
    animation=[]
    comparison=[]
    for i in range(96):
        art=cell(sheet,i)
        frame=Image.new('RGB',(SIZE,SIZE),BACKGROUND)
        frame.paste(art,(0,0),art)
        animation.append(frame)
        pair=Image.new('RGB',(SIZE*2,SIZE+40),BACKGROUND)
        old=cell(before,int(i/30/0.05)%64)
        pair.paste(old,(0,40),old)
        pair.paste(art,(SIZE,40),art)
        draw=ImageDraw.Draw(pair)
        draw.text((20,12),'ANTES · Imagen deformada',font=font,fill='#ddd4c0')
        draw.text((SIZE+20,12),'AHORA · Piezas articuladas',font=font,fill='#edbf7b')
        comparison.append(pair)
    save_gif(animation,OUTPUT/'warrior-idle.gif')
    save_gif(comparison,OUTPUT/'warrior-idle-comparison.gif')
    print('Animated review and before/after GIF exported.')


if __name__=='__main__':
    main()
