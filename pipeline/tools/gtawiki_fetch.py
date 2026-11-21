#!/usr/bin/env python3
"""Downloads the in-game pictures chosen by gtawiki_images.py, checks them and writes them into the app.
usage: gtawiki_fetch.py <app/www> <work dir> <sharp binary> <dhash binary> <batch size>
Per picture: a 900 px wide copy from the wiki (1 request per 1.1 s, generic client name), sharpness measured, then it is kept only if
(1) it is not blurry (Laplacian variance >= 25) and (2) it is not a look-alike (dhash distance <= 6) of any picture already in the app or kept before.
Kept pictures go to app/www/ig/<slug>.jpg and app/www/ig.js (window.IGP = id -> path). Re-run to continue: finished ids are skipped.
Every file is a GTA VI in-game image (see the filters in gtawiki_images.py); credit in the app stays (c) Rockstar Games."""
import sys, os, re, json, time, subprocess, urllib.request, urllib.parse
APP, WORK, SHARP, DH, BATCH = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], int(sys.argv[5])
UA = {'User-Agent': 'LeonidaCompanionPrototype/0.1 (fan app prototype; generic-client)'}
picks = json.load(open(WORK + '/picks.json'))
state_f = WORK + '/fetch_state.json'; state = json.load(open(state_f)) if os.path.exists(state_f) else {}
igp = {}
if os.path.exists(APP + '/ig.js'):
    t = open(APP + '/ig.js', encoding='utf-8').read(); igp = json.loads(t[t.index('=') + 1:t.rindex(';')])
def api(**p):
    p['format'] = 'json'
    for i in range(3):
        try: return json.load(urllib.request.urlopen(urllib.request.Request('https://gta.wiki/api.php?' + urllib.parse.urlencode(p), headers=UA), timeout=60))
        except Exception: time.sleep(3)
def dh(path):
    out = subprocess.run([DH, path], capture_output=True, text=True).stdout.split()
    return out[1] if len(out) > 1 else None
ham = lambda a, b: bin(int(a, 16) ^ int(b, 16)).count('1')
# hashes of every picture already in the app (game sprites, tiles, covers, characters, places, earlier ig files)
known = {}
os.makedirs(WORK + '/dl', exist_ok=True); os.makedirs(APP + '/ig', exist_ok=True)
cache_f = WORK + '/known_hashes.json'
if os.path.exists(cache_f): known = json.load(open(cache_f))
else:
    dec = json.JSONDecoder(); r = open(APP + '/real.js', encoding='utf-8').read()
    R = dec.raw_decode(r, r.index('window.REAL=') + 12)[0]; ROWS = dec.raw_decode(r, r.index('window.REAL_ROWS=') + 17)[0]
    for sh in range(len(ROWS)):
        for l in subprocess.run([DH, '%s/sp/real%d.jpg' % (APP, sh), '5', '480', '300'], capture_output=True, text=True).stdout.split('\n'):
            if l.strip(): i, h = l.split(); known['sprite:%d:%s' % (sh, i)] = h
    for d in ('hero', 'gv', 'ch'):
        for f in os.listdir(APP + '/' + d):
            if f.endswith('.jpg'): known['%s/%s' % (d, f)] = dh('%s/%s/%s' % (APP, d, f))
    for f in os.listdir(APP + '/ph'):
        if f.endswith('.jpg'): known['ph/' + f] = dh(APP + '/ph/' + f)
    json.dump(known, open(cache_f, 'w'))
for k, p in igp.items():
    if os.path.exists(os.path.join(APP, p)): known.setdefault(p, dh(os.path.join(APP, p)))
todo = [k for k in sorted(picks) if k not in state][:BATCH]
print(len(picks) - len(state), 'pictures left; this batch:', len(todo))
files = sorted({c['file'] for k in todo for c in [picks[k]] + picks[k].get('alts', [])}); thumb = {}
for i in range(0, len(files), 40):
    d = api(action='query', prop='imageinfo', iiprop='url', iiurlwidth='900', titles='|'.join('File:' + f for f in files[i:i + 40]))
    for p in d['query']['pages'].values():
        ii = (p.get('imageinfo') or [{}])[0]
        if ii.get('thumburl'): thumb[p['title'][5:].replace(' ', '_')] = ii['thumburl']
    time.sleep(0.5)
kept = rej = 0
def attempt(k, pk):
    """try one picture for item k; returns 'ok' or the reason it was not used"""
    u = thumb.get(pk['file'].replace(' ', '_'))
    if not u: return 'no thumb'
    raw = '%s/dl/%s' % (WORK, re.sub(r'[^A-Za-z0-9._-]', '_', pk['file']))
    if not os.path.exists(raw) or os.path.getsize(raw) < 3000:
        try: open(raw, 'wb').write(urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=60).read()); time.sleep(1.1)
        except Exception: return 'download failed'
    slug = re.sub(r'[^a-z0-9]+', '-', k.lower()).strip('-'); dst = '%s/ig/%s.jpg' % (APP, slug)
    subprocess.run(['sips', '-s', 'format', 'jpeg', '-s', 'formatOptions', '76', '-Z', '900', raw, '--out', dst], capture_output=True)
    if not os.path.exists(dst) or os.path.getsize(dst) < 6000: return 'convert failed'
    w = int(subprocess.run(['sips', '-g', 'pixelWidth', dst], capture_output=True, text=True).stdout.split()[-1]); h = int(subprocess.run(['sips', '-g', 'pixelHeight', dst], capture_output=True, text=True).stdout.split()[-1])
    sv = subprocess.run([SHARP, dst, '1', str(w), str(h)], capture_output=True, text=True).stdout.split()
    sharp = float(sv[1]) if len(sv) > 1 else 0
    hh = dh(dst)
    dup = next((n for n, x in known.items() if x and hh and n != 'ig/%s.jpg' % slug and ham(hh, x) <= 6), None)
    if sharp < 25: os.remove(dst); return 'blurry %.0f' % sharp
    if dup: os.remove(dst); return 'duplicate of ' + dup
    igp[k] = 'ig/%s.jpg' % slug; known['ig/%s.jpg' % slug] = hh
    return 'ok'
for k in todo:
    why = []
    for pk in [picks[k]] + picks[k].get('alts', []):
        r = attempt(k, pk)
        if r == 'ok': state[k] = 'ok'; kept += 1; break
        why.append(r)
    else: state[k] = '; '.join(why[:2]); rej += 1
json.dump(state, open(state_f, 'w')); json.dump(known, open(cache_f, 'w'))
open(APP + '/ig.js', 'w', encoding='utf-8').write('window.IGP=' + json.dumps(igp, ensure_ascii=False, separators=(',', ':')) + ';')
print('kept', kept, '| rejected', rej, '| total in ig.js', len(igp), '| ig folder', subprocess.run(['du', '-sh', APP + '/ig'], capture_output=True, text=True).stdout.split()[0])
