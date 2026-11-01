# Render the 이음 icon (option 2: yellow 가 card in front of a grey A card) for every phone density.
import asyncio, pathlib, base64
from playwright.async_api import async_playwright
ROOT = pathlib.Path(__file__).resolve().parent.parent
RES = ROOT / 'app/src/main/res'
DEFS = '''<defs>
<linearGradient id="b0" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#22262E"/><stop offset="1" stop-color="#0B0C10"/></linearGradient>
<linearGradient id="b1" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#FFE27A"/><stop offset="1" stop-color="#FFB800"/></linearGradient>
<filter id="bs" x="-50%" y="-50%" width="200%" height="200%"><feDropShadow dx="0" dy="4" stdDeviation="4" flood-opacity=".5"/></filter></defs>'''
FONT = 'font-family="Noto Sans CJK KR,Noto Sans KR,sans-serif" font-weight="800"'
CARDS = f'''<g transform="rotate(8 66 42)"><rect x="44" y="20" width="44" height="44" rx="11" fill="#3B3F49"/>
<text x="66" y="53" text-anchor="middle" font-size="28" fill="#D9DBE2" font-family="Arial,sans-serif" font-weight="800">A</text></g>
<g filter="url(#bs)"><rect x="20" y="42" width="46" height="46" rx="12" fill="url(#b1)"/>
<text x="43" y="76" text-anchor="middle" font-size="30" fill="#16181B" {FONT}>가</text></g>'''
BG = '<rect width="108" height="108" fill="url(#b0)"/>'
def svg(body, clip=None):
    c = f'<clipPath id="cl"><rect width="108" height="108" rx="{clip}"/></clipPath>' if clip is not None else ''
    g = f'<g clip-path="url(#cl)">{body}</g>' if clip is not None else body
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 108 108" width="100%" height="100%">{DEFS}<defs>{c}</defs>{g}</svg>'
# adaptive foreground: keep everything inside the 66dp safe circle (scale about the cards' centre)
FG = f'<g transform="translate(54 54) scale(0.8) translate(-56 -53)">{CARDS}</g>'
LEGACY = BG + f'<g transform="translate(54 54) scale(0.95) translate(-56 -53)">{CARDS}</g>'
DENS = {'mdpi': 1, 'hdpi': 1.5, 'xhdpi': 2, 'xxhdpi': 3, 'xxxhdpi': 4}
async def shot(pg, markup, px, out, transparent=True):
    await pg.set_viewport_size({'width': px, 'height': px})
    await pg.set_content(f'<html><body style="margin:0;background:transparent">{markup}</body></html>')
    out.parent.mkdir(parents=True, exist_ok=True)
    await pg.screenshot(path=str(out), omit_background=transparent)
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/usr/bin/google-chrome', args=['--no-sandbox'])
        pg = await b.new_page()
        for d, k in DENS.items():
            folder = RES / f'mipmap-{d}'
            await shot(pg, svg(FG), int(108 * k), folder / 'ic_launcher_foreground.png')
            await shot(pg, svg(LEGACY, 24), int(48 * k), folder / 'ic_launcher.png')
        await shot(pg, svg(LEGACY, 24), 512, ROOT / 'site/icon-512.png')
        await shot(pg, svg(LEGACY, 24), 180, ROOT / 'site/icon-180.png')
        await b.close()
    # small inline logo for the app header
    (ROOT / 'tools/logo.svg').write_text(svg(BG + f'<g transform="translate(54 54) scale(1.05) translate(-56 -53)">{CARDS}</g>', 24))
asyncio.run(main())
