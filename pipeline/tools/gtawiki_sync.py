#!/usr/bin/env python3
"""Rebuilds the item catalogue (vehicles, weapons, characters, animals) from gta.wiki, the project's source of truth for items.
usage: gtawiki_sync.py <app/www> <work dir>
- Reads the GTA VI categories through the MediaWiki API (1 request per 0.6 s, generic client name; robots.txt allows it).
- Keeps only facts (names, class, maker, capacity, games it appears in); descriptions in the app are our own words.
- Never imports an item whose name starts with 'Unnamed'.
- Writes app/www/wiki.js (vehicles, weapons, characters) and replaces the animals list in app/www/wiki2.js (radios and gangs are left alone).
- Writes <work>/images.json: lead image (file, url, original size) of every kept item, for the photo pass.
gta.wiki text is CC BY-NC-SA 3.0: no prose is copied, only item facts."""
import sys, os, re, json, time, urllib.request, urllib.parse
APP, WORK = sys.argv[1], sys.argv[2]
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from wiki_lib import infobox, clean
src = open(HERE + '/wiki_build.py', encoding='utf-8').read()
exec(src[src.index('G={'):src.index('def skip')])   # G (games), games(), VG (vehicle classes), WG (weapon classes)
UA = {'User-Agent': 'LeonidaCompanionPrototype/0.1 (fan app prototype; generic-client)'}
def get(**p):
    p['format'] = 'json'
    for i in range(3):
        try: return json.load(urllib.request.urlopen(urllib.request.Request('https://gta.wiki/api.php?' + urllib.parse.urlencode(p), headers=UA), timeout=60))
        except Exception: time.sleep(3)
    raise SystemExit('gta.wiki not reachable')
CATS = {'vehicles': 'Vehicles in GTA VI', 'weapons': 'Weapons in GTA VI', 'characters': 'Characters in GTA VI', 'animals': 'Animals in GTA VI'}
raw, images = {}, {}
for kind, cat in CATS.items():
    titles, cont = [], {}
    while True:
        d = get(action='query', list='categorymembers', cmtitle='Category:' + cat, cmlimit='500', cmnamespace='0', **cont)
        titles += [m['title'] for m in d['query']['categorymembers']]
        if 'continue' in d: cont = {'cmcontinue': d['continue']['cmcontinue']}
        else: break
    titles = [t for t in titles if not re.match(r'\s*Unnamed\b', t) and not re.search(r'\b(in GTA VI|Tracklist)$', t)]
    pages = {}
    for i in range(0, len(titles), 40):
        chunk = '|'.join(titles[i:i + 40])
        d = get(action='query', prop='revisions', rvprop='content|timestamp', rvslots='main', titles=chunk, redirects='1')
        for p in d['query']['pages'].values():
            r = (p.get('revisions') or [{}])[0]; text = (r.get('slots', {}).get('main', {}) or {}).get('*', '')
            if text and not re.match(r'\s*#redirect', text, re.I) and not re.match(r'\s*\{\{\s*Delete', text, re.I): pages[p['title']] = {'ts': r.get('timestamp'), 'text': text}
        d = get(action='query', prop='pageimages', piprop='original|name', pilimit='50', titles=chunk, redirects='1')
        for p in d['query']['pages'].values():
            o = p.get('original')
            if o: images[p['title']] = {'file': p.get('pageimage'), 'url': o['source'], 'w': o['width'], 'h': o['height']}
        time.sleep(0.6)
    raw[kind] = pages; print(kind, len(titles), 'listed,', len(pages), 'kept')
os.makedirs(WORK, exist_ok=True); json.dump(raw, open(WORK + '/raw.json', 'w')); json.dump(images, open(WORK + '/images.json', 'w'), ensure_ascii=False)

def jsvar(path, var):
    t = open(path, encoding='utf-8').read(); i = t.index(var + '=') + len(var) + 1
    d, j = json.JSONDecoder().raw_decode(t, i); return d, t[:i], t[j:]
out = {'ts': max(p['ts'] for k in raw for p in raw[k].values() if p['ts']), 'vehicles': [], 'weapons': [], 'characters': []}
sub = {}
need = [t for t, p in raw['characters'].items() if not infobox(p['text'])[0]]
for i in range(0, len(need), 40):
    d = get(action='query', prop='revisions', rvprop='content', rvslots='main', titles='|'.join(t + '/infobox' for t in need[i:i + 40]))
    for p in d['query']['pages'].values():
        r = (p.get('revisions') or [{}])[0]; sub[p['title'].rsplit('/', 1)[0]] = (r.get('slots', {}).get('main', {}) or {}).get('*', '')
    time.sleep(0.6)
for t, p in sorted(raw['vehicles'].items()):
    n, f = infobox(p['text'])
    if not n: continue
    ty = clean(f.get('type', '')).lower()
    out['vehicles'].append([t, VG.get(ty, 'Outros'), clean(f.get('body_style', '')), clean(f.get('manufacturer', '')), clean(f.get('capacity', ''))[:60], games(f)])
for t, p in sorted(raw['weapons'].items()):
    n, f = infobox(p['text'])
    if not n: continue
    ty = clean(f.get('type', '')).lower()
    out['weapons'].append([t, WG.get(ty, 'Outros'), clean(f.get('firemode', ''))[:60], clean(f.get('manufacturer', ''))[:50], '', games(f)])
for t, p in sorted(raw['characters'].items()):
    n, f = infobox(p['text'])
    if not n and sub.get(t): n, f = infobox('{{Infobox character' + sub[t].split('infobox', 1)[-1])
    if not n: continue
    st = {'Alive': 'Vivo', 'Active': 'Ativo', 'Deceased': 'Morto', 'Incarcerated': 'Preso'}.get(clean(f.get('status', '')), '')
    occ = clean(f.get('occupation', '')); occ = '' if occ == 'Not given' else occ
    out['characters'].append([t, 'Protagonistas' if t in ('Jason Duval', 'Lucia Caminos') else 'Personagens', occ[:90], clean(f.get('affiliations', ''))[:120], clean(f.get('home', ''))[:70], [st] if st else []])
old, pre, post = jsvar(APP + '/wiki.js', 'window.WIKI')
open(APP + '/wiki.js', 'w', encoding='utf-8').write(pre + json.dumps(out, ensure_ascii=False, separators=(',', ':')) + post)
animals = []
for t, p in sorted(raw['animals'].items()):
    n, f = infobox(p['text'])
    g = lambda *ks: next((clean(f[k])[:90] for k in ks if f.get(k)), '')
    animals.append([t, 'Animais', g('type', 'class', 'species'), g('habitat', 'location', 'locations'), '', []])
w2, pre2, post2 = jsvar(APP + '/wiki2.js', 'window.WIKI2'); w2['animals'] = animals
open(APP + '/wiki2.js', 'w', encoding='utf-8').write(pre2 + json.dumps(w2, ensure_ascii=False, separators=(',', ':')) + post2)
print('wiki.js:', {k: len(v) for k, v in out.items() if k != 'ts'}, '| animals:', len(animals), '| images found for', len(images), 'items | newest revision', out['ts'])
for k in ('vehicles', 'weapons', 'characters'): print(' app had', len(old.get(k, [])), '->', len(out[k]), k)
