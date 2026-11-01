#!/usr/bin/env python3
"""Turn the web preview (index.src.html) into the phone app screen (index.html).

The preview asks Claude to translate; the app does everything on the phone through
the `Ieum` bridge (ML Kit translation, text reading, the phone's speech screen and voice).
Each block below swaps one part of the preview. The script stops if a marker is missing,
so a changed preview can't silently produce a half-converted app.
"""
import pathlib, re, sys

HERE = pathlib.Path(__file__).resolve().parent.parent / 'app/src/main/assets'
src = (pathlib.Path(__file__).resolve().parent / 'preview.html').read_text(encoding='utf-8')


def between(s, start, end, new, keep_end=True):
    i = s.find(start)
    j = s.find(end, i + len(start)) if i >= 0 else -1
    if i < 0 or j < 0:
        sys.exit('marker not found: %r .. %r' % (start[:60], end[:60]))
    return s[:i] + new + (s[j:] if keep_end else s[j + len(end):])


def swap(s, old, new, count=1):
    n = s.count(old)
    if n != count:
        sys.exit('expected %d of %r, found %d' % (count, old[:80], n))
    return s.replace(old, new)


# ---------- document shell: the app is a full page (the artifact host added this before) ----------
head = '''<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<style>:root{color-scheme:light}body{margin:0}img{max-width:100%}[hidden]{display:none!important}</style>
'''
s = head + src
s = swap(s, '<link rel="preconnect" href="https://fonts.googleapis.com">\n', '')
s = swap(s, '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n', '')
s = re.sub(r'<link rel="stylesheet" href="https://fonts.googleapis.com[^>]*>\n', '', s)
s = swap(s, '--f-sign:"Barlow Semi Condensed","Arial Narrow","Roboto Condensed",sans-serif;',
         '--f-sign:"Roboto Condensed","sans-serif-condensed","Arial Narrow",sans-serif;')
s = swap(s, '--f-body:"IBM Plex Sans KR","Apple SD Gothic Neo","Noto Sans KR","Malgun Gothic",system-ui,sans-serif;',
         '--f-body:"Noto Sans KR","Noto Sans CJK KR","Apple SD Gothic Neo",system-ui,sans-serif;')
s = swap(s, '</head>', '</head>', 0) if '</head>' in s else s
s = s.replace('<title>이음</title>', '<title>이음</title>\n</head><body>', 1)
s = s.rstrip() + '\n</body></html>\n'

# live camera view inside the lens + its style
s = swap(s, '<div class="lens-pic" id="lensPic"><img id="lensImg" alt="번역한 사진">',
         '<div class="lens-pic" id="lensPic"><video id="lensVideo" playsinline muted hidden></video><img id="lensImg" alt="번역한 사진">')
s = swap(s, '.lens-tags{position:absolute;inset:0}',
         '.lens-tags{position:absolute;inset:0}\n.lens-pic video{display:block;width:100%;height:100%;object-fit:contain;border-radius:4px;background:#000}\n.ver.new{color:var(--rec);text-decoration:underline}')

# header logo = the app icon
logo = (pathlib.Path(__file__).resolve().parent / 'logo.svg').read_text().replace('width="100%" height="100%"', 'width="30" height="30" aria-hidden="true"')
s = swap(s, '<span class="mark"><svg class="i" data-ic="swap"></svg></span>\n        <h1>', '<span class="logo">' + logo + '</span>\n        <h1>')
s = swap(s, '.brand h1{', '.logo{width:30px;height:30px;flex:none;border-radius:8px;overflow:hidden;display:block}\n.logo svg{display:block}\n.brand h1{')

# footer
s = swap(s, '<span id="engineTxt">미리보기 · Claude 번역</span>', '<span id="engineTxt">폰 안에서 번역</span>')

# version comes from the installed app
s = swap(s, "const VER = 'v1.3';",
         "const VER = 'v' + (function () { try { return (window.Ieum && window.Ieum.version()) || '1.0'; } catch (e) { return '1.0'; } })();")

# exchange rates are refreshed by the phone once a day
s = swap(s, "const RATES_DATE = '10월 30일';", "let RATES_DATE = '10월 30일';")
s = swap(s, "    sosCountry: store.get('sosCountry', ''),", "    sosCountry: store.get('sosCountry', ''),\n    country: '',")

# ---------- translation engine ----------
ENGINE = r'''/* ---------- translation engine (on the phone: ML Kit through the Ieum bridge) ---------- */
  const NB = window.Ieum || null;
  const ENG = { state: NB ? 'ok' : 'none', img: !!NB };
  const waiters = new Map();
  let nid = 0;
  function nativeCall(fn, args) {
    return new Promise((resolve, reject) => {
      if (!NB || typeof NB[fn] !== 'function') { reject({ code: 'unavailable' }); return; }
      const id = 'n' + (++nid);
      waiters.set(id, { resolve, reject });
      try { NB[fn].apply(NB, [id].concat(args)); } catch (e) { waiters.delete(id); reject({ code: 'unavailable' }); }
    });
  }
  window.onNative = (o) => {
    if (!o || typeof o !== 'object') return;
    if (o.type === 'status') { toast(String(o.msg || ''), o.ms || 4000); return; }
    if (o.type === 'spoke') { onSpoke(o); return; }
    if (o.type === 'rates') { applyRates(o); return; }
    if (o.type === 'latest') { onLatest(o); return; }
    const w = waiters.get(o.id);
    if (!w) return;
    waiters.delete(o.id);
    if (o.ok) w.resolve(o); else w.reject({ code: o.code || 'failed', message: o.error || '' });
  };
  function errText(e) {
    const c = e && e.code;
    if (c === 'unavailable') return '번역 기능을 열지 못했어요. 앱을 껐다 켜 주세요.';
    if (c === 'unsupported') return '이 언어는 아직 번역할 수 없어요.';
    if (c === 'download') return '번역 팩을 받지 못했어요. 인터넷에 연결한 뒤 다시 해 주세요.';
    if (c === 'cancelled') return '취소했어요.';
    if (c === 'nospeech') return '말소리를 알아듣지 못했어요. 다시 눌러서 말해 주세요.';
    if (c === 'nospeechapp') return '이 폰에서 음성 인식을 열 수 없어요. Google 앱이 설치돼 있는지 확인해 주세요.';
    return (e && e.message) || '번역하지 못했어요. 다시 시도해 주세요.';
  }
  const engineOff = () => !NB;
  function trText(text, from, to) {
    if (!text || from === to) return Promise.resolve(text);
    return nativeCall('translate', [text, from, to]).then((r) => String(r.text || '').trim());
  }
  function trMany(arr, from, to) {
    if (!arr.length || from === to) return Promise.resolve(arr.slice());
    return nativeCall('translateMany', [JSON.stringify(arr), from, to])
      .then((r) => (Array.isArray(r.list) && r.list.length === arr.length ? r.list.map((x) => String(x == null ? '' : x).trim()) : arr.slice()));
  }
  function detectLang(text) {
    return nativeCall('detect', [String(text).slice(0, 600)]).then((r) => (r.code && r.code !== 'und' ? normCode(r.code) : '')).catch(() => '');
  }
  function prepareModels() { try { if (NB) NB.prepare(S.me, S.them); } catch (e) { /* ignore */ } }
  function keepOn(on) { try { if (NB) NB.keepOn(!!on); } catch (e) { /* ignore */ } }
  function applyRates(o) {
    if (!o || !o.rates) return;
    for (const [c, v] of Object.entries(o.rates)) { const n = +v; if (n > 0 && isFinite(n)) KRW_PER[c] = n; }
    const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(o.date || ''));
    if (m) RATES_DATE = (+m[2]) + '월 ' + (+m[3]) + '일';
    if (S.items.some((it) => it.kind === 'see')) renderFeed();
  }
  let latestInfo = null;
  function onLatest(o) {
    latestInfo = o;
    const v = $('#verTxt');
    const newer = +o.latest > +o.current;
    v.textContent = VER + (newer ? ' · 새 버전 v1.' + o.latest : ' · 최신');
    v.classList.toggle('new', newer);
    v.onclick = newer ? () => { try { NB.openUpdate(); } catch (e) { /* ignore */ } } : null;
  }

  '''
s = between(s, '/* ---------- translation engine (preview: Claude) ---------- */', '/* phrasebook: one request per language, kept on the phone */', ENGINE)
s = swap(s, "const p = askJSON(promptPB(lang)).then((arr) => {", "const p = trMany(PB_SRC, 'ko', lang).then((arr) => {")

# ---------- notes on the empty feed ----------
NOTE = r'''function renderNote() {
    let node = null;
    if (!NB) node = noteBox('alert', '번역 기능을 열지 못했어요. 앱을 껐다 켜 주세요.');
    else if (!S.noteSeen) node = noteBox('alert', '처음 쓰는 언어는 번역 팩(언어마다 약 30MB)을 한 번 받아요. 와이파이에 연결되면 고른 언어를 알아서 받아 둬요. 그다음부턴 인터넷 없이도 번역돼요.',
      () => { S.noteSeen = true; store.set('noteSeen', true); renderNote(); });
    feedNote.replaceChildren(...(node ? [node] : []));
  }

  '''
s = between(s, 'function renderNote() {', '/* ---------- text translation ---------- */', NOTE)

# ---------- text translation ----------
RUN = r'''async function runText(it, opts) {
    if (busy.has(it)) return;
    busy.add(it);
    it.status = 'pending'; it.err = null;
    updateItem(it);
    try {
      if (it.auto) {
        let src = await detectLang(it.orig);
        if (S.me === 'ko' && /[가-힣]/.test(it.orig)) src = 'ko';
        const mine = src ? src === S.me : it.kind === 'speak';
        it.kind = mine ? 'speak' : 'listen';
        it.src = mine ? S.me : (L[src] && src !== S.me ? src : S.them);
        it.dst = mine ? S.them : S.me;
      }
      const t = await trText(it.orig, it.src, it.dst);
      if (!t) throw { code: 'failed' };
      finish(it, t, opts);
    } catch (e) {
      it.status = 'error'; it.err = errText(e);
      updateItem(it);
    } finally {
      busy.delete(it);
    }
  }
  '''
s = between(s, 'async function runText(it, opts) {', 'async function phrase(i) {', RUN)

# ---------- listening: the phone's own speech screen (no microphone permission needed) ----------
LISTEN = r'''/* ---------- listening (the phone's speech screen; this app has no microphone permission) ---------- */
  const micBlocked = false;
  let rec = null, recKind = null;

  function setRec(r, kind) {
    rec = r; recKind = r ? kind : null;
    for (const [b, k] of [[btnListen, 'listen'], [btnSpeak, 'speak']]) {
      const on = !!r && kind === k;
      b.classList.toggle('rec', on);
      b.querySelector('b').textContent = on ? '듣는 중' : (k === 'listen' ? '듣기' : '말하기');
      b.querySelector('small').textContent = route(k);
    }
  }
  function stopRec() { if (rec) setRec(null); }
  function failToast(code) {
    if (code === 'cancelled') return;
    toast(errText({ code: code || 'nospeech' }));
  }
  // One utterance through the phone's speech screen. Calls cb.onDone(text) or cb.onFail(code).
  function listen(lang, cb) {
    const r = { lang };
    const prompt = lang === S.me ? nameKo(lang) + '로 말하세요' : (pbLine(lang, IX.ui + UI_TAP) || L[lang].native);
    nativeCall('listen', [L[lang].bcp, prompt]).then((o) => {
      if (rec === r) setRec(null);
      const t = String(o.text || '').trim();
      if (t) cb.onDone(t); else cb.onFail('nospeech');
    }, (e) => {
      if (rec === r) setRec(null);
      cb.onFail(e.code || 'nospeech');
    });
    return r;
  }
  function voice(kind) {
    if (rec) return;
    stopSpeak();
    const src = kind === 'speak' ? S.me : S.them, dst = kind === 'speak' ? S.them : S.me;
    const r = listen(src, {
      onDone: (t) => { const it = addItem({ kind, src, dst, orig: t, trans: '', status: 'pending' }); runText(it); },
      onFail: (code) => failToast(code),
    });
    setRec(r, kind);
  }

  '''
s = between(s, '/* ---------- listening ---------- */', '/* ---------- speaking ---------- */', LISTEN)

# ---------- speaking: the phone's text-to-speech ----------
SPEAK = r'''/* ---------- speaking (the phone's text-to-speech) ---------- */
  const spokeCb = new Map();
  let sayN = 0, toldVoice = false;
  function markSpeaking(key, on) {
    document.querySelectorAll('.speaking').forEach((b) => b.classList.remove('speaking'));
    if (on && key) document.querySelectorAll('[data-say="' + key + '"]').forEach((b) => b.classList.add('speaking'));
  }
  function speak(text, code, key, onDone) {
    if (!text) { if (onDone) onDone(); return; }
    const l = L[code];
    const bcp = l ? l.bcp : (code || 'en');
    const sid = 's' + (++sayN);
    spokeCb.clear();
    spokeCb.set(sid, { key, onDone, lang: l ? l.ko : '이 언어' });
    markSpeaking(key, true);
    try { NB.speak(sid, String(text), bcp, S.slow ? 0.7 : 0.95); } catch (e) { onSpoke({ key: sid, ok: false }); }
  }
  function onSpoke(o) {
    const c = spokeCb.get(o.key);
    if (!c) return;
    spokeCb.delete(o.key);
    markSpeaking(c.key, false);
    if (o.ok === false && o.code === 'nolang' && !toldVoice) {
      toldVoice = true;
      toast('이 폰에 ' + c.lang + ' 읽기 음성이 없어요. 폰 설정 → 텍스트 음성 변환에서 음성 데이터를 받아 주세요.', 5200);
    }
    if (c.onDone) c.onDone();
  }
  function stopSpeak() {
    try { if (NB) NB.stopSpeak(); } catch (e) { /* ignore */ }
    spokeCb.clear();
    markSpeaking(null, false);
  }

  '''
s = between(s, '/* ---------- speaking ---------- */', '/* ---------- seeing (photos) ---------- */', SPEAK)

# ---------- seeing: photos read on the phone ----------
SEE = r'''/* ---------- seeing (photos: text read on the phone, then translated) ---------- */
  const SCRIPT = { ja: 'ja', zh: 'zh', hi: 'hi', ko: 'ko' };
  const scriptFor = () => SCRIPT[S.them] || 'latin';
  const CUR_BY_COUNTRY = { JP: 'JPY', CN: 'CNY', TW: 'TWD', HK: 'HKD', MO: 'HKD', VN: 'VND', TH: 'THB', PH: 'PHP', ID: 'IDR', MY: 'MYR', SG: 'SGD',
    IN: 'INR', AE: 'AED', TR: 'TRY', US: 'USD', GU: 'USD', MP: 'USD', CA: 'CAD', GB: 'GBP', CH: 'CHF', AU: 'AUD', NZ: 'NZD',
    FR: 'EUR', DE: 'EUR', IT: 'EUR', ES: 'EUR', PT: 'EUR', NL: 'EUR', AT: 'EUR', BE: 'EUR', IE: 'EUR', FI: 'EUR', GR: 'EUR', HR: 'EUR' };
  const DOLLAR = { HK: 'HKD', TW: 'TWD', SG: 'SGD', AU: 'AUD', NZ: 'NZD', CA: 'CAD' };
  const NO_DEC = new Set(['JPY', 'KRW', 'VND', 'IDR']);
  function detectCur(t, src) {
    if (/₫|\bVND\b|\d\s?đ(?!\p{L})|đồng/iu.test(t)) return 'VND';
    if (/€|\bEUR\b/.test(t)) return 'EUR';
    if (/£|\bGBP\b/.test(t)) return 'GBP';
    if (/฿|บาท|\bTHB\b/.test(t)) return 'THB';
    if (/円|\bJPY\b/.test(t)) return 'JPY';
    if (/元|\bRMB\b|\bCNY\b/.test(t)) return 'CNY';
    if (/¥/.test(t)) return src === 'zh' ? 'CNY' : 'JPY';
    if (/HK\$/.test(t)) return 'HKD';
    if (/NT\$/.test(t)) return 'TWD';
    if (/S\$/.test(t)) return 'SGD';
    if (/\bRM\s?\d/.test(t)) return 'MYR';
    if (/\bRp\.?\s?\d/.test(t)) return 'IDR';
    if (/₱|\bPHP\b/.test(t)) return 'PHP';
    if (/₹|\bRs\.?\s?\d/.test(t)) return 'INR';
    if (/₺/.test(t)) return 'TRY';
    if (/\$|\bUSD\b/.test(t)) return DOLLAR[S.country] || 'USD';
    return CUR_BY_COUNTRY[S.country] || CUR_BY_LANG[src] || '';
  }
  const PRICE_AT_END = /(?:^|[\s.:·…_\-–—|])((?:US\$|HK\$|NT\$|S\$|RM|Rp\.?|[$€£¥₩₫฿₱₹])?\s?\d[\d.,\s]*\d|\d)\s*(원|円|元|₫|đ|VND|฿|บาท|€|\$|¥|,-)?\s*$/;
  function parseNum(raw, cur) {
    const s = String(raw).replace(/[^\d.,]/g, '');
    if (!s) return null;
    let n;
    if (NO_DEC.has(cur)) n = parseFloat(s.replace(/[.,]/g, ''));
    else {
      const m = /^(.*?)[.,](\d{1,2})$/.exec(s);
      n = m ? parseFloat(m[1].replace(/[.,]/g, '') + '.' + m[2]) : parseFloat(s.replace(/[.,]/g, ''));
    }
    return isFinite(n) && n > 0 && n < 1e9 ? n : null;
  }
  function splitPrice(text, cur) {
    if (/\d{1,2}:\d{2}/.test(text)) return null;
    const m = PRICE_AT_END.exec(text);
    if (!m) return null;
    const name = text.slice(0, m.index).replace(/[\s.:·…_\-–—|]+$/, '').trim();
    if (!/\p{L}/u.test(name)) return null;
    // a bare small number after a place word is part of an address or sign ("District 1", "Exit 3"), not a price
    const bare = /^\d+$/.test(m[1].trim()) && !m[2];
    if (bare && /(street|\bst\b|road|avenue|district|floor|room|gate|exit|platform|line|bus|terminal|hall|no\.?|번|층|호|号|番|線|区|quận|phường|tầng)\s*$/iu.test(name)) return null;
    const price = parseNum(m[1], cur);
    return price ? { name, price } : null;
  }
  // Lines read on the same height become one row (menu names and prices are often read apart).
  function rowsOf(lines) {
    const ls = (lines || []).filter((l) => l && typeof l.t === 'string' && l.t.trim() && Array.isArray(l.b) && l.b.length === 4)
      .map((l) => ({ t: l.t.trim(), b: l.b.map(Number) }));
    ls.sort((a, b) => (a.b[1] + a.b[3]) - (b.b[1] + b.b[3]));
    const rows = [];
    for (const l of ls) {
      const g = rows[rows.length - 1];
      if (g) {
        const f = g[0];
        const tol = Math.min(f.b[3] - f.b[1], l.b[3] - l.b[1]) * 0.55;
        if (Math.abs((f.b[1] + f.b[3]) / 2 - (l.b[1] + l.b[3]) / 2) <= tol) { g.push(l); continue; }
      }
      rows.push([l]);
    }
    return rows.map((g) => {
      g.sort((a, b) => a.b[0] - b.b[0]);
      return { t: g.map((x) => x.t).join('  '),
        b: [Math.min(...g.map((x) => x.b[0])), Math.min(...g.map((x) => x.b[1])), Math.max(...g.map((x) => x.b[2])), Math.max(...g.map((x) => x.b[3]))].map(Math.round) };
    });
  }
  async function readRows(rows) {
    const all = rows.map((r) => r.t).join('\n');
    let src = await detectLang(all);
    if (!L[src]) src = S.them;
    const dst = src === S.me ? S.them : S.me;
    const cur = detectCur(all, src);
    const parsed = rows.map((r) => { const m = splitPrice(r.t, cur); return { o: m ? m.name : r.t, p: m ? m.price : null, b: r.b }; });
    const tr = await trMany(parsed.map((x) => x.o), src, dst);
    return { src, dst, cur, lines: parsed.map((x, i) => ({ o: x.o, t: tr[i] || x.o, p: x.p, b: x.b })) };
  }
  function thumbOf(url, max) {
    return new Promise((res) => {
      const im = new Image();
      im.onload = () => {
        try {
          const k = Math.min(1, (max || 560) / Math.max(im.naturalWidth, im.naturalHeight));
          const c = document.createElement('canvas');
          c.width = Math.max(1, Math.round(im.naturalWidth * k)); c.height = Math.max(1, Math.round(im.naturalHeight * k));
          c.getContext('2d').drawImage(im, 0, 0, c.width, c.height);
          res(c.toDataURL('image/jpeg', 0.72));
        } catch (e) { res(url); }
      };
      im.onerror = () => res(url);
      im.src = url;
    });
  }
  function runPhoto() { /* photos are read once, right after they are taken */ }
  async function photoItem(res, opts) {
    opts = opts || {};
    const it = addItem({ kind: 'see', src: '', dst: '', cur: '', lines: [], status: 'pending', img: null, sample: !!opts.sample, order: {} });
    if (res.img) { fullURL.set(it.id, res.img); it.img = await thumbOf(res.img); }
    updateItem(it); scrollEnd();
    try {
      const rows = rowsOf(res.lines).slice(0, 40);
      if (rows.length) Object.assign(it, await readRows(rows));
      else { it.lines = []; it.dst = S.me; }
      it.status = 'done';
    } catch (e) {
      it.status = 'error'; it.err = errText(e);
    }
    updateItem(it);
    if (it === S.items[S.items.length - 1]) scrollEnd();
    if (it.status !== 'done') return;
    if (opts.mode === 'lens' && hasBoxes(it)) openLens(it);
    else if (opts.mode === 'order') { if (hasPrices(it)) orderSheet(it); else toast('가격이 있는 메뉴를 찾지 못했어요.'); }
  }
  function pickPhoto(purpose, camera) {
    if (!photoReady()) return;
    nativeCall('photo', [camera ? 'camera' : 'album', scriptFor()]).then((res) => {
      if (purpose.kind === 'addr') chooseAddress(res); else photoItem(res, purpose);
    }, (e) => { if (e.code !== 'cancelled') toast(e.message || '사진을 열지 못했어요.', 4200); });
  }
  async function samplePhoto(mode) {
    try { if (document.fonts) await Promise.race([document.fonts.load('600 48px "Roboto Condensed"'), new Promise((r) => setTimeout(r, 800))]); } catch (e) { /* fallback font */ }
    let url;
    try { url = drawMenu(FULL_MENU).canvas.toDataURL('image/jpeg', 0.9); } catch (e) { toast('예시 사진을 만들지 못했어요.'); return; }
    nativeCall('ocrImage', [url.slice(url.indexOf(',') + 1), 'latin']).then((res) => { res.img = url; photoItem(res, { sample: true, mode }); },
      (e) => toast(e.message || '글자를 읽지 못했어요.', 4200));
  }
  function onFile() { /* photos come from the phone's camera and gallery screens */ }
  function photoReady() {
    if (!NB) { toast(errText({ code: 'unavailable' })); return false; }
    return true;
  }

  '''
s = between(s, '/* ---------- seeing (photos) ---------- */', '/* lens: translations laid over the photo', SEE)

# ---------- lens: photo overlay + live camera ----------
s = swap(s, "$('#lensNote').textContent = overlay ? '글자를 누르면 원문을 읽어줘요. 미리보기는 사진 한 장으로 보여주고, 앱에선 카메라를 비추는 동안 바로 겹쳐요.' : '';",
         "$('#lensNote').textContent = overlay ? '글자를 누르면 원문을 읽어줘요.' : '';")
s = swap(s, "    lensImg.onload = fitLens;\n    lensImg.src = fullURL.get(it.id) || it.img || '';",
         "    stopLive();\n    lensImg.onload = fitLens;\n    lensImg.src = fullURL.get(it.id) || it.img || '';")
LENS_TAIL = r'''function fitLens() {
    const iw = live ? lensVideo.videoWidth : lensImg.naturalWidth, ih = live ? lensVideo.videoHeight : lensImg.naturalHeight;
    if (!iw || lens.hidden) return;
    const st = lensStage.getBoundingClientRect();
    const k = Math.min(st.width / iw, st.height / ih);
    const w = Math.max(1, Math.floor(iw * k)), hh = Math.max(1, Math.floor(ih * k));
    lensPic.style.width = w + 'px'; lensPic.style.height = hh + 'px';
    lensTags.querySelectorAll('.lens-tag').forEach((t) => {
      const bh = (+t.dataset.h / 1000) * hh;
      t.style.fontSize = Math.max(12, Math.min(22, bh * 0.72)) + 'px';
    });
  }
  function closeLens() { stopLive(); lens.hidden = true; lensItem = null; markSpeaking(null, false); }
  window.addEventListener('resize', () => { if (!lens.hidden) fitLens(); });

  /* live camera: read what the camera sees about once a second and lay the translation over it */
  const lensVideo = $('#lensVideo');
  let live = null;
  function liveTag(l, src, dst, cur) {
    const [x0, y0, x1, y1] = l.b;
    const tag = h('button', { class: 'lens-tag', type: 'button', 'data-h': y1 - y0, 'aria-label': l.t + ' (원문 읽어주기)', onclick: () => speak(l.o, src, null) },
      langOn(h('span', null, l.t), dst), l.p > 0 && krw(l.p, cur) ? h('small', null, ' ' + krw(l.p, cur)) : null);
    tag.style.left = (x0 / 10) + '%';
    tag.style.top = (y0 / 10) + '%';
    tag.style.minWidth = Math.max(6, (x1 - x0) / 10) + '%';
    tag.style.maxWidth = Math.max(20, 100 - x0 / 10) + '%';
    return tag;
  }
  async function openLive() {
    if (!photoReady()) return;
    try { await nativeCall('camPerm', []); } catch (e) { toast('카메라로 비추려면 카메라 권한을 허용해 주세요.', 4200); return; }
    let stream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: 'environment' }, width: { ideal: 1280 }, height: { ideal: 960 } }, audio: false });
    } catch (e) {
      toast('카메라를 열지 못해서 사진으로 찍을게요.', 3600);
      pickPhoto({ kind: 'see', mode: 'lens' }, true);
      return;
    }
    stopLive();
    lensItem = null;
    live = { stream, busy: false, paused: false, timer: 0, cache: new Map(), rows: null, res: null, url: '' };
    lensTags.replaceChildren();
    lensImg.hidden = true; lensVideo.hidden = false;
    lensVideo.srcObject = stream;
    lensVideo.onloadedmetadata = fitLens;
    $('#lensTitle').textContent = '카메라로 비추기';
    $('#lensNote').textContent = '글자에 카메라를 대고 잠깐 멈추면 번역이 겹쳐 보여요. 번역을 누르면 원문을 읽어줘요.';
    const pause = h('button', { class: 'lens-b', type: 'button' }, ic('rotate'), h('span', null, '멈추기'));
    pause.addEventListener('click', () => {
      if (!live) return;
      live.paused = !live.paused;
      if (live.paused) lensVideo.pause(); else lensVideo.play().catch(() => {});
      pause.querySelector('span').textContent = live.paused ? '계속 비추기' : '멈추기';
    });
    const keep = h('button', { class: 'lens-b main', type: 'button' }, ic('list'), h('span', null, '이 화면 저장'));
    keep.addEventListener('click', () => {
      if (!live || !live.res) { toast('아직 읽은 글자가 없어요. 글자에 카메라를 대 주세요.'); return; }
      const res = Object.assign({}, live.res, { img: live.url });
      closeLens();
      photoItem(res, { mode: 'list' });
    });
    lensFoot.replaceChildren(pause, keep);
    lens.hidden = false;
    keepOn(true);
    try { await lensVideo.play(); } catch (e) { /* autoplay muted is allowed */ }
    fitLens();
    liveTick();
  }
  function stopLive() {
    if (!live) return;
    clearTimeout(live.timer);
    try { live.stream.getTracks().forEach((t) => t.stop()); } catch (e) { /* ignore */ }
    live = null;
    lensVideo.srcObject = null;
    lensVideo.hidden = true; lensImg.hidden = false;
    keepOn(false);
  }
  function liveTick() {
    if (!live) return;
    clearTimeout(live.timer);
    live.timer = setTimeout(liveFrame, 700);
  }
  async function liveFrame() {
    const L0 = live;
    if (!L0) return;
    if (L0.paused || L0.busy || !lensVideo.videoWidth) { liveTick(); return; }
    L0.busy = true;
    try {
      const vw = lensVideo.videoWidth, vh = lensVideo.videoHeight;
      const k = Math.min(1, 1280 / Math.max(vw, vh));
      const c = document.createElement('canvas');
      c.width = Math.round(vw * k); c.height = Math.round(vh * k);
      c.getContext('2d').drawImage(lensVideo, 0, 0, c.width, c.height);
      const url = c.toDataURL('image/jpeg', 0.75);
      const res = await nativeCall('ocrImage', [url.slice(url.indexOf(',') + 1), scriptFor()]);
      if (live !== L0 || L0.paused) return;
      const rows = rowsOf(res.lines).slice(0, 25);
      if (!rows.length) { lensTags.replaceChildren(); return; }
      const need = rows.map((r) => r.t).filter((t) => !L0.cache.has(t));
      if (need.length) {
        const out = await readRows(rows.filter((r) => need.includes(r.t)));
        L0.src = out.src; L0.dst = out.dst; L0.cur = out.cur;
        rows.filter((r) => need.includes(r.t)).forEach((r, i) => L0.cache.set(r.t, out.lines[i]));
      }
      if (live !== L0 || L0.paused) return;
      const lines = rows.map((r) => Object.assign({}, L0.cache.get(r.t), { b: r.b }));
      L0.res = { lines: res.lines }; L0.url = url;
      lensTags.replaceChildren(...lines.filter((l) => l && l.t).map((l) => liveTag(l, L0.src, L0.dst, L0.cur)));
      fitLens();
    } catch (e) {
      /* a missed frame is fine; the next one tries again */
    } finally {
      if (live === L0) { L0.busy = false; liveTick(); }
    }
  }
'''
s = between(s, 'function fitLens() {', "  /* menu ordering */", LENS_TAIL + '\n')

# ---------- rates note ----------
s = swap(s, "h('p', { class: 'sheet-note' }, '미리보기는 고정 환율이에요. 앱에선 지금 있는 나라 통화로 알아서 맞추고, 환율을 하루 한 번 새로 받아 와요.')",
         "h('p', { class: 'sheet-note' }, '지금 있는 나라 통화로 알아서 맞추고, 환율은 하루 한 번 새로 받아 와요.')")

# ---------- boards keep the screen on ----------
s = swap(s, "    big.hidden = false;\n    try { $('#bigClose').focus({ preventScroll: true }); } catch (e) { /* ignore */ }\n  }",
         "    big.hidden = false;\n    keepOn(true);\n    try { $('#bigClose').focus({ preventScroll: true }); } catch (e) { /* ignore */ }\n  }")
s = swap(s, "    markSpeaking(null, false);\n    try { if (window.speechSynthesis) window.speechSynthesis.cancel(); } catch (e) { /* ignore */ }\n  }",
         "    stopSpeak();\n    if (face.hidden && !live) keepOn(false);\n  }")

# ---------- address from a photo: read the text, the traveler taps the address lines ----------
ADDR = r'''const ADDR_HINT = /(street|\bst\b|road|\brd\b|avenue|\bave\b|blvd|lane|丁目|番地|番|区|市|町|路|街|号|道|đường|phường|quận|ถนน|ซอย|calle|avenida|rue|straße|strasse|\bvia\b|\brua\b|jalan|\bjl\b|\d{3}-\d{4}|\b\d{5}\b)/i;
  function chooseAddress(res) {
    const rows = rowsOf(res.lines);
    if (!rows.length) { toast('사진에서 글자를 찾지 못했어요. 직접 쓰기로 넣어 주세요.', 4200); return; }
    const picked = new Set();
    rows.forEach((r, i) => { if (/\d/.test(r.t) && ADDR_HINT.test(r.t)) picked.add(i); });
    const save = h('button', { class: 'save', type: 'button' }, '이 주소로 저장');
    const list = h('div', { role: 'group', 'aria-label': '사진에서 읽은 줄' });
    const draw = () => {
      list.replaceChildren(...rows.map((r, i) => h('button', { class: 'opt', type: 'button', role: 'checkbox', 'aria-checked': String(picked.has(i)),
        onclick: () => { if (picked.has(i)) picked.delete(i); else picked.add(i); draw(); } },
        h('span', { class: 'k' }, picked.has(i) ? '✓' : ''), langOn(h('span', { class: 'kn' }, r.t), ''))));
      save.disabled = !picked.size;
    };
    save.addEventListener('click', async () => {
      const address = rows.filter((r, i) => picked.has(i)).map((r) => r.t).join(' ');
      closeSheet();
      const lang = (await detectLang(address)) || S.them;
      let ko = '';
      try { ko = L[lang] ? await trText(address, lang, S.me) : ''; } catch (e) { ko = ''; }
      S.addr = { name: '', address, lang: L[lang] ? lang : S.them, ko: ko !== address ? ko : '', phone: '' };
      store.set('addr', S.addr);
      showAddress();
    });
    draw();
    openSheet('주소 줄을 눌러 고르세요', h('div', { class: 'form' }, h('p', { class: 'sheet-note' }, '주소로 보이는 줄은 미리 골라 뒀어요. 맞으면 저장을 누르세요.'), list, save));
  }

  '''
s = between(s, 'async function readAddress(file) {', '/* emergency card */', ADDR)

# ---------- emergency: the phone's country, and numbers open the dialer ----------
s = swap(s, "function sosCountry() { return SOS_BY[S.sosCountry] || SOS_BY[COUNTRY_BY_LANG[S.them]] || SOS_BY.US; }",
         "function sosCountry() { return SOS_BY[S.sosCountry] || SOS_BY[S.country] || SOS_BY[COUNTRY_BY_LANG[S.them]] || SOS_BY.US; }\n"
         "  function dialNum(num) { try { NB.dial(num); } catch (e) { copyText(num, '번호 ' + num + '를 복사했어요.'); } }")
s = re.sub(r"onclick: \(\) => copyText\(num, [^)]*\)", "onclick: () => dialNum(num)", s)
s = re.sub(r"onclick: \(\) => copyText\(CONSUL\.dial, [^)]*\)", "onclick: () => dialNum(CONSUL.dial)", s)
if 'copyText(num,' in s.split('function sosNums')[1].split('async function showSOS')[0]:
    sys.exit('sos buttons not converted')
s = swap(s, "    openSheet('지금 있는 나라', h('div', null, h('p', { class: 'sheet-note' }, '앱에선 폰이 지금 있는 나라를 알아서 골라요.'), list));",
         "    openSheet('지금 있는 나라', h('div', null, h('p', { class: 'sheet-note' }, '폰이 지금 있는 나라를 알아서 골라요. 다르면 여기서 바꿔 주세요.'), list));")

# ---------- face to face ----------
s = swap(s, "  async function openFace() {\n    face.hidden = false;", "  async function openFace() {\n    face.hidden = false;\n    keepOn(true);")
s = swap(s, "function closeFace() { face.hidden = true; stopRec(); markSpeaking(null, false); try { if (window.speechSynthesis) window.speechSynthesis.cancel(); } catch (e) { /* ignore */ } }",
         "function closeFace() { face.hidden = true; stopRec(); stopSpeak(); if (big.hidden && !live) keepOn(false); }")
s = swap(s, "      onFail: (code) => { end(); if (code === 'blocked') faceInputs(); else failToast(code, lang); },",
         "      onFail: (code) => { end(); failToast(code); },")

# ---------- see sheet ----------
s = swap(s, "opt('camera', '카메라로 비추기', '글자 위에 번역이 겹쳐 보여요 (미리보기는 한 장 찍어서)', () => { closeSheet(); pickPhoto({ kind: 'see', mode: 'lens' }, true); }),",
         "opt('layers', '카메라로 비추기', '비추는 동안 글자 위에 번역이 겹쳐 보여요', () => { closeSheet(); openLive(); }),\n"
         "      opt('camera', '사진 찍어서 번역', '한 장 찍고 천천히 보기', () => { closeSheet(); pickPhoto({ kind: 'see', mode: 'lens' }, true); }),")

# ---------- settings ----------
s = between(s, "    const wb = (icon, label, fn) =>", "  /* ---------- copy ---------- */", r'''    const upd = h('button', { class: 'act-b', type: 'button', onclick: () => { try { NB.openUpdate(); } catch (e) { /* ignore */ } } }, ic('retry'), h('span', null, '확인'));
    openSheet('설정', h('div', null,
      row('말하기 결과 바로 읽어주기', '번역되면 상대 언어로 소리 내 읽어요', sw(S.autoSpeak, (v) => { S.autoSpeak = v; store.set('autoSpeak', v); }, '말하기 결과 바로 읽어주기')),
      row('천천히 읽기', '외국 사람이 알아듣기 쉽게 느리게 읽어요', sw(S.slow, (v) => { S.slow = v; store.set('slow', v); }, '천천히 읽기')),
      row('새 버전 확인', latestInfo && +latestInfo.latest > +latestInfo.current ? '새 버전 v1.' + latestInfo.latest + '이 나왔어요' : '지금 ' + VER, upd),
      h('div', { class: 'set-block' }, h('b', null, '홈 화면 위젯'),
        h('small', null, '홈 화면 빈 곳을 길게 누르고 위젯 → 이음을 놓으면, 듣기·말하기·보기를 바로 열 수 있어요.')),
      h('div', { class: 'row' }, clear),
      h('p', { class: 'about' }, '이음 ' + VER + ' · 번역은 폰 안에서 해요. 대화와 사진은 밖으로 보내지 않아요. 언어마다 처음 한 번 번역 팩을 받고, 그다음부턴 인터넷 없이도 번역돼요.')));
  }

  ''')

# ---------- copy through the phone ----------
s = between(s, '/* ---------- copy ---------- */', '/* ---------- languages on screen ---------- */', r'''/* ---------- copy ---------- */
  function copyText(text, okMsg) {
    try { NB.copy(String(text)); toast(okMsg || '복사했어요.', okMsg ? 3600 : 2800); }
    catch (e) { toast('복사하지 못했어요. 글자를 길게 눌러 복사해 주세요.'); }
  }

  ''')

# ---------- language changes prepare translation packs ----------
s = swap(s, "    store.set('me', S.me); store.set('them', S.them);\n    renderLangs();\n    renderFeed();\n  }",
         "    store.set('me', S.me); store.set('them', S.them);\n    renderLangs();\n    renderFeed();\n    prepareModels();\n  }")
s = swap(s, "    renderLangs(); renderFeed();\n    toast('나 ' + nameKo(S.me) + ' ⇄ 상대 ' + nameKo(S.them), 1600);",
         "    renderLangs(); renderFeed(); prepareModels();\n    toast('나 ' + nameKo(S.me) + ' ⇄ 상대 ' + nameKo(S.them), 1600);")

# ---------- entry points: widget buttons and the back key ----------
s = swap(s, "  window.tongyeokOpen = (what) =>", "  window.ieumOpen = (what) =>")
s = swap(s, "  renderLangs();\n  renderNote();\n  renderFeed();",
         r'''  window.onBackKey = () => {
    if (!sheet.hidden) { closeSheet(); return true; }
    if (!big.hidden) { closeBoard(); return true; }
    if (!lens.hidden) { closeLens(); return true; }
    if (!face.hidden) { closeFace(); return true; }
    return false;
  };
  document.addEventListener('visibilitychange', () => { if (document.hidden && live && !live.paused) closeLens(); });
  if (NB) {
    try { S.country = String(NB.country() || '').toUpperCase(); } catch (e) { S.country = ''; }
    try { NB.rates(); } catch (e) { /* fixed rates stay */ }
    prepareModels();
  }

  renderLangs();
  renderNote();
  renderFeed();''')

s = swap(s, "const KEY = 'tongyeok.';", "const KEY = 'ieum.';")

# ---------- first open: empty screen; examples only when asked ----------
s = swap(s, """  function renderFeed() {
    const real = S.items.length > 0;
    const frag = document.createDocumentFragment();
    for (const it of (real ? S.items : examples())) frag.append(cardNode(it, !real));
    feedList.replaceChildren(frag);
  }""", """  let showEx = false;
  function renderFeed() {
    const real = S.items.length > 0;
    if (real) showEx = false;
    const frag = document.createDocumentFragment();
    if (real) for (const it of S.items) frag.append(cardNode(it, false));
    else if (showEx) {
      frag.append(h('div', { class: 'note' }, ic('eye'), h('p', null, '예시 화면이에요. 내 기록이 아니에요.'),
        h('button', { type: 'button', onclick: () => { showEx = false; renderFeed(); } }, '닫기')));
      for (const it of examples()) frag.append(cardNode(it, true));
    } else {
      frag.append(h('div', { class: 'empty' }, h('b', null, '아직 대화가 없어요'),
        h('p', null, '아래 듣기·말하기·보기나 자주 쓰는 말을 눌러 시작하세요.'),
        h('button', { class: 'act-b', type: 'button', onclick: () => { showEx = true; renderFeed(); } }, ic('eye'), h('span', null, '예시 둘러보기'))));
    }
    feedList.replaceChildren(frag);
  }""")
s = swap(s, '#feedNote:empty{display:none}', '#feedNote:empty{display:none}\n.empty{display:grid;justify-items:center;gap:6px;text-align:center;padding:40px 12px;color:var(--muted)}\n.empty b{color:var(--ink);font-size:17px}\n.empty .act-b{margin-top:6px;border:1px solid var(--line);border-radius:6px;padding:0 14px}')
s = swap(s, "      if (rows.length) Object.assign(it, await readRows(rows));", "      if (rows.length) Object.assign(it, await readRows(rows));")

# ---------- nothing from the preview's Claude path may remain ----------
for bad in ['askJSON', 'samplePromise', 'promptPhoto', 'promptAddr', 'promptAuto', 'promptDirected', 'speechSynthesis', 'SpeechRecognition', 'claude.use', 'fonts.googleapis', '미리보기']:
    if bad in s:
        lines = [i + 1 for i, ln in enumerate(s.splitlines()) if bad in ln]
        sys.exit('leftover %r on lines %s' % (bad, lines[:8]))

(HERE / 'index.html').write_text(s, encoding='utf-8')
print('ok', len(s.encode()), 'bytes')
