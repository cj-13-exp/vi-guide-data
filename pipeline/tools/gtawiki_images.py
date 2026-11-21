#!/usr/bin/env python3
"""Picks, for every item of wiki.js / wiki2.js, the best in-game GTA VI picture on gta.wiki and lists it in a manifest.
usage: gtawiki_images.py <app/www> <work dir>
Rule: only files whose name says GTAVI (screenshots, trailer frames, game renders). Files from other games, logos (except radio stations),
maps, icons, fan art and real photos are never candidates. Output: <work>/picks.json {id: {file, url, w, h, score}} and a coverage summary.
The download, sharpness check and duplicate check happen in the next step (tools/gtawiki_fetch.py)."""
import sys, os, re, json, time, urllib.request, urllib.parse
APP, WORK = sys.argv[1], sys.argv[2]
UA = {'User-Agent': 'LeonidaCompanionPrototype/0.1 (fan app prototype; generic-client)'}
def get(**p):
    p['format'] = 'json'
    for i in range(3):
        try: return json.load(urllib.request.urlopen(urllib.request.Request('https://gta.wiki/api.php?' + urllib.parse.urlencode(p), headers=UA), timeout=60))
        except Exception: time.sleep(3)
    raise SystemExit('gta.wiki not reachable')
dec = json.JSONDecoder()
def jsvar(f, var):
    t = open(APP + '/' + f, encoding='utf-8').read(); return dec.raw_decode(t, t.index(var + '=') + len(var) + 1)[0]
W = jsvar('wiki.js', 'window.WIKI'); W2 = jsvar('wiki2.js', 'window.WIKI2')
items = {}
for k, p in (('vehicles', 'v'), ('weapons', 'w'), ('characters', 'c')):
    for r in W[k]: items[p + ':' + r[0]] = (k, r[0])
for k, p in (('animals', 'a'), ('radios', 'r'), ('gangs', 'g')):
    for r in W2[k]: items[p + ':' + r[0]] = (k, r[0])
BAD = re.compile(r'logo|icon|badge|map|poster|cover|box|art\b|fanart|concept|texture|sprite|signature|-GTAV[^I]|-GTAIV|-GTAO|-GTAOee|-GTAVee|real|stock', re.I)
GOOD = re.compile(r'GTAVI|GTA6', re.I)
KIND_BONUS = (('FrontQuarter', 30), ('Front', 12), ('Portrait', 30), ('Screenshot', 10), ('AnExtendedLook', 8), ('Trailer', 6), ('Render', 12), ('Model', 12), ('Pose', 8))
titles = sorted({t for _, t in items.values()})
cands = {}
for i in range(0, len(titles), 25):
    chunk = titles[i:i + 25]; cont = {}
    while True:
        d = get(action='query', prop='images', imlimit='500', titles='|'.join(chunk), redirects='1', **cont)
        for p in d['query']['pages'].values():
            for im in p.get('images', []): cands.setdefault(p['title'], []).append(im['title'][5:])
        if 'continue' in d: cont = {'imcontinue': d['continue']['imcontinue']}
        else: break
    time.sleep(0.5)
lead = json.load(open(WORK + '/images.json')) if os.path.exists(WORK + '/images.json') else {}
want = {}   # file name -> items that could use it
for t in titles:
    names = [n for n in cands.get(t, []) if GOOD.search(n) and not BAD.search(n) and re.search(r'\.(png|jpe?g)$', n, re.I)]
    if t in lead and lead[t].get('file') and GOOD.search(lead[t]['file']) and not BAD.search(lead[t]['file']) and lead[t]['file'] not in names: names.append(lead[t]['file'])
    want[t] = names
files = sorted({n for v in want.values() for n in v}); info = {}
for i in range(0, len(files), 40):
    d = get(action='query', prop='imageinfo', iiprop='url|size|mime', titles='|'.join('File:' + f for f in files[i:i + 40]))
    for p in d['query']['pages'].values():
        ii = (p.get('imageinfo') or [{}])[0]
        if ii.get('url'): info[p['title'][5:].replace(' ', '_')] = (ii['url'], ii['width'], ii['height'])
    time.sleep(0.5)
picks, cover = {}, {}
for id_, (k, t) in items.items():
    cl = []
    for n in want.get(t, []):
        u = info.get(n.replace(' ', '_'))
        if not u or u[1] < 640: continue
        sc = min(u[1], 2000) / 20 + sum(b for key, b in KIND_BONUS if key.lower() in n.lower()) + (10 if lead.get(t, {}).get('file') == n else 0)
        cl.append({'file': n, 'url': u[0], 'w': u[1], 'h': u[2], 'score': round(sc, 1)})
    cl.sort(key=lambda x: -x['score'])
    best = dict(cl[0], alts=cl[1:4]) if cl else None      # alternates: gtawiki_fetch.py tries them when the best picture is blurry or a look-alike
    if best: picks[id_] = best
    c = cover.setdefault(k, [0, 0]); c[0] += 1; c[1] += 1 if best else 0
json.dump(picks, open(WORK + '/picks.json', 'w'), ensure_ascii=False)
print('in-game GTA VI picture found for', len(picks), 'of', len(items), 'items')
for k, (n, g) in cover.items(): print('  %-10s %4d items, %4d with an in-game picture, %4d without' % (k, n, g, n - g))
