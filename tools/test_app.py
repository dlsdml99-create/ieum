# Run the app screen in Chromium with a stand-in for the Android bridge and walk through every flow.
import asyncio, json, os, pathlib, sys
from playwright.async_api import async_playwright
ROOT = pathlib.Path(__file__).resolve().parent.parent
HTML = (ROOT / 'app/src/main/assets/index.html').as_uri()
OUT = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else '/tmp')

MOCK = r'''
(() => {
  const calls = window.__calls = [];
  const reply = (o, ms) => setTimeout(() => window.onNative(o), ms || 30);
  const T = (s, to) => '[' + to.toUpperCase() + '] ' + s;
  window.Ieum = {
    version: () => '1.4',
    country: () => 'us',
    translate(id, text, from, to) { calls.push(['translate', from, to, text]); reply({ id, ok: true, text: T(text, to) }); },
    translateMany(id, json, from, to) { const a = JSON.parse(json); calls.push(['translateMany', from, to, a.length]); reply({ id, ok: true, list: a.map((s) => T(s, to)) }); },
    detect(id, text) { calls.push(['detect', text.slice(0, 20)]); reply({ id, ok: true, code: /[가-힣]/.test(text) ? 'ko' : /[ぁ-ん]/.test(text) ? 'ja' : 'en' }); },
    prepare(me, them) { calls.push(['prepare', me, them]); },
    listen(id, bcp, prompt) { calls.push(['listen', bcp, prompt]); reply({ id, ok: true, text: bcp.startsWith('ko') ? '지하철역 어디예요?' : 'It is two blocks away.' }, 80); },
    speak(sid, text, bcp, rate) { calls.push(['speak', bcp, text, rate]); reply({ type: 'spoke', key: sid, ok: true }, 60); },
    stopSpeak() { calls.push(['stopSpeak']); },
    photo(id, source, script) {
      calls.push(['photo', source, script]);
      const c = document.createElement('canvas'); c.width = 800; c.height = 600;
      const x = c.getContext('2d'); x.fillStyle = '#334'; x.fillRect(0, 0, 800, 600); x.fillStyle = '#fff'; x.font = '40px sans-serif';
      x.fillText('Pho Bo 65,000đ', 60, 150); x.fillText('Banh Mi 30.000', 60, 260); x.fillText('Open 7:00 - 22:00', 60, 370); x.fillText('12 Ly Tu Trong Street, District 1', 60, 480);
      reply({ id, ok: true, w: 800, h: 600, img: c.toDataURL('image/jpeg', 0.8), lines: [
        { t: 'Pho Bo', b: [75, 200, 260, 260] }, { t: '65,000đ', b: [600, 205, 760, 262] },
        { t: 'Banh Mi 30.000', b: [75, 385, 420, 445] },
        { t: 'Open 7:00 - 22:00', b: [75, 570, 470, 630] },
        { t: '12 Ly Tu Trong Street, District 1', b: [75, 755, 800, 815] } ] }, 120);
    },
    ocrImage(id, b64, script) {
      calls.push(['ocrImage', script, b64.length > 1000]);
      reply({ id, ok: true, w: 1200, h: 900, lines: [
        { t: 'CORNER CAFE', b: [320, 95, 680, 170] },
        { t: 'Iced Americano', b: [93, 250, 330, 300] }, { t: '4.50', b: [840, 250, 907, 300] },
        { t: 'Matcha Latte', b: [93, 430, 300, 480] }, { t: '5.50', b: [840, 430, 907, 480] },
        { t: 'Please order and pay at the counter.', b: [270, 860, 730, 900] } ] }, 90);
    },
    camPerm(id) { calls.push(['camPerm']); reply({ id, ok: true }); },
    copy(t) { calls.push(['copy', t]); },
    dial(n) { calls.push(['dial', n]); },
    rates() { calls.push(['rates']); reply({ type: 'rates', date: '2026-11-01', rates: { USD: 1400, VND: 0.055, JPY: 9.1 } }, 50); },
    openUpdate() { calls.push(['openUpdate']); },
    keepOn(on) { calls.push(['keepOn', on]); },
  };
  setTimeout(() => window.onNative({ type: 'latest', latest: 5, current: 4 }), 300);
})();
'''

async def main():
    R, errs = {}, []
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/usr/bin/google-chrome',
                                    args=['--no-sandbox', '--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream'])
        ctx = await b.new_context(viewport={'width': 390, 'height': 800}, device_scale_factor=2, has_touch=True)
        await ctx.add_init_script(MOCK)
        await ctx.route('**/*', lambda r: r.abort() if not r.request.url.startswith(('file:', 'data:', 'blob:')) else r.continue_())
        pg = await ctx.new_page()
        pg.on('pageerror', lambda e: errs.append('pageerror: %s' % e))
        pg.on('console', lambda m: errs.append('console.%s: %s' % (m.type, m.text)) if m.type in ('error', 'warning') else None)
        await pg.goto(HTML)
        await pg.wait_for_selector('.empty')
        await pg.wait_for_timeout(500)
        ev = pg.evaluate
        R['empty_start'] = await ev('[document.querySelectorAll(".card").length, document.querySelector(".empty").textContent]')
        await pg.screenshot(path=str(OUT / 'app-empty.png'))
        await pg.click('.empty .act-b'); await pg.wait_for_timeout(200)
        R['examples_on_tap'] = await ev('[document.querySelectorAll(".card").length, document.querySelector(".note").textContent]')
        await pg.click('.note button >> text=닫기')
        R['start'] = await ev('''() => ({ ver: document.getElementById('verTxt').textContent, newVer: document.getElementById('verTxt').classList.contains('new'),
          note: document.getElementById('feedNote').textContent.slice(0, 40), cards: document.querySelectorAll('.card').length,
          engine: document.getElementById('engineTxt').textContent, logo: !!document.querySelector('.logo svg') })''')
        await pg.screenshot(path=str(OUT / 'app-start.png'))
        # phrase chip -> phrasebook through translateMany, then speak
        await pg.click('.chip >> text=화장실 어디예요?')
        await pg.wait_for_timeout(300)
        R['phrase'] = await ev('[...document.querySelectorAll(".card.speak[data-id] .trans")].pop().textContent')
        # speak button -> native listen (Korean) -> translate to English
        await pg.click('#btnSpeak'); await pg.wait_for_timeout(400)
        R['speak'] = await ev('(() => { const c = [...document.querySelectorAll("#feedList .card")].pop(); return c.className + " | " + c.querySelector(".orig").textContent + " | " + c.querySelector(".trans").textContent; })()')
        # listen -> English heard -> Korean, with quick replies
        await pg.click('#btnListen'); await pg.wait_for_timeout(400)
        R['listen'] = await ev('(() => { const c = [...document.querySelectorAll("#feedList .card")].pop(); return c.className + " | " + c.querySelector(".trans").textContent + " | replies=" + c.querySelectorAll(".rchip").length; })()')
        await pg.click('.card.listen .rchip >> text=네'); await pg.wait_for_timeout(300)
        R['reply'] = await ev('[...document.querySelectorAll(".card.speak[data-id] .trans")].pop().textContent')
        # typed English -> detect -> listen card
        await pg.fill('#txt', 'Where is the bus stop?'); await pg.press('#txt', 'Enter'); await pg.wait_for_timeout(300)
        R['typed'] = await ev('(() => { const c = [...document.querySelectorAll("#feedList .card")].pop(); return c.className + " | " + c.querySelector(".route").textContent + " | " + c.querySelector(".trans").textContent; })()')
        # swap languages
        await pg.click('#swapBtn'); await pg.wait_for_timeout(100)
        R['swap'] = await ev('document.getElementById("meCode").textContent + "/" + document.getElementById("themCode").textContent')
        await pg.click('#swapBtn'); await pg.wait_for_timeout(100)
        # photo from album: prices, currency, order
        await pg.click('#btnSee'); await pg.click('.opt >> text=메뉴판 찍고 주문하기'); await pg.wait_for_timeout(800)
        R['photo_sheet'] = await ev('document.getElementById("sheetTitle").textContent')
        R['photo_lines'] = await ev('[...document.querySelectorAll(".card.see[data-id] .line")].map(n => n.textContent)')
        R['photo_cur'] = await ev('document.querySelector(".card.see[data-id] .cur-chip")?.textContent')
        await pg.click('.o-row .o-main >> nth=0'); await pg.click('.o-row .o-main >> nth=1'); await pg.click('.o-row .o-main >> nth=1')
        R['order_total'] = await ev('document.querySelector(".o-total").textContent')
        await pg.click('.o-show'); await pg.wait_for_timeout(300)
        R['order_board'] = await ev('[...document.querySelectorAll("#bigBody > *")].map(n => n.textContent).join(" | ")')
        await pg.click('#bigClose')
        # sample menu -> ocrImage -> lens with tags
        await pg.click('#btnSee'); await pg.click('.opt >> text=예시 메뉴판으로 해보기'); await pg.wait_for_timeout(800)
        R['sample_lens'] = await ev('[!document.getElementById("lens").hidden, document.querySelectorAll("#lensTags .lens-tag").length, [...document.querySelectorAll("#lensTags .lens-tag")].map(t => t.textContent).slice(0, 3)]')
        await pg.screenshot(path=str(OUT / 'app-lens.png'))
        await pg.click('#lensClose')
        # live camera with a fake camera
        await pg.click('#btnSee'); await pg.click('.opt >> text=카메라로 비추기'); await pg.wait_for_timeout(2600)
        R['live'] = await ev('[!document.getElementById("lens").hidden, !document.getElementById("lensVideo").hidden, document.getElementById("lensVideo").videoWidth, document.querySelectorAll("#lensTags .lens-tag").length, document.getElementById("lensTitle").textContent]')
        await pg.screenshot(path=str(OUT / 'app-live.png'))
        await pg.click('#lensFoot .lens-b.main'); await pg.wait_for_timeout(600)
        R['live_saved'] = await ev('[document.getElementById("lens").hidden, [...document.querySelectorAll(".card.see[data-id]")].length]')
        # address from photo: tap lines, save, board
        await pg.click('#tAddr'); await pg.click('.opt >> text=앨범에서 가져오기'); await pg.wait_for_timeout(500)
        R['addr_pick'] = await ev('[document.getElementById("sheetTitle").textContent, [...document.querySelectorAll("#sheetBody .opt[aria-checked=true]")].map(n => n.textContent)]')
        await pg.click('#sheetBody .save'); await pg.wait_for_timeout(500)
        R['addr_board'] = await ev('[...document.querySelectorAll("#bigBody > *")].map(n => n.textContent).join(" | ")')
        await pg.click('#bigClose')
        # SOS: country from the phone (US), number opens dialer
        await pg.click('#tSos'); await pg.wait_for_timeout(300)
        R['sos'] = await ev('[document.querySelector(".sos-country").textContent, [...document.querySelectorAll(".sos-num")].map(n => n.textContent)]')
        await pg.click('.sos-num >> nth=0')
        await pg.screenshot(path=str(OUT / 'app-sos.png'))
        await pg.click('#bigClose')
        # face to face: me speaks -> them auto listens
        await pg.click('#tFace'); await pg.wait_for_timeout(300)
        await pg.click('#fMeMic'); await pg.wait_for_timeout(900)
        R['face'] = await ev('[document.getElementById("fThemText").textContent, document.getElementById("fMeText").textContent, document.getElementById("fMeSub").textContent]')
        await pg.screenshot(path=str(OUT / 'app-face.png'))
        # back key closes face
        R['back'] = await ev('window.onBackKey()')
        R['back2'] = await ev('window.onBackKey()')
        # settings + update
        await pg.click('#btnSet'); await pg.wait_for_timeout(100)
        R['settings'] = await ev('document.getElementById("sheetBody").textContent.slice(0, 200)')
        await pg.click('#sheetBody .set-btn >> text=버전 정보'); await pg.wait_for_timeout(200)
        R['info_open'] = await ev('getComputedStyle(document.body.lastElementChild).display')
        await ev('window.onBackKey()')
        # widget entry point
        await ev('window.ieumOpen("listen")'); await pg.wait_for_timeout(300)
        R['calls'] = await ev('window.__calls.map(c => c.join(" ")).filter(c => !c.startsWith("detect"))')
        R['overflow'] = await ev('document.documentElement.scrollWidth - document.documentElement.clientWidth')
        await ev('document.getElementById("feed").scrollTop = 0')
        await pg.screenshot(path=str(OUT / 'app-feed.png'))
        await b.close()
    print(json.dumps(R, ensure_ascii=False, indent=1))
    print('ERRORS:', json.dumps(errs, ensure_ascii=False, indent=1))
asyncio.run(main())
