#!/usr/bin/env python3
"""Builds app/www/heists.js: robbery types, their locations, and the fences, from gta.wiki (the project's source of truth).
usage: heists_build.py <app/www> <work dir>
Sources (facts only, our own wording for every sentence): gta.wiki pages 'Smash 'n' Grabs', 'Payday Loans', 'Fences'. Numbers for the types that have no gta.wiki page yet
(bank jobs, gang operations, stick-ups, vaults) come from the 100% checklist data (tools/hundred_build.py, cross-checked there) and are marked 'reported'.
Place rows: [type, name, area, reward_min, reward_max, x, y]. x,y are the map coordinates the wiki prints; they are kept as DATA and are NOT drawn on the app map until the
project owner approves gta.wiki as a coordinate source (standing rule: map coordinates come from GTADB). Never writes names starting with 'Unnamed'."""
import sys, os, re, json, time, urllib.request, urllib.parse
APP, WORK = sys.argv[1], sys.argv[2]
UA = {'User-Agent': 'LeonidaCompanionPrototype/0.1 (fan app prototype; generic-client)'}
def get(**p):
    p['format'] = 'json'
    for i in range(3):
        try: return json.load(urllib.request.urlopen(urllib.request.Request('https://gta.wiki/api.php?' + urllib.parse.urlencode(p), headers=UA), timeout=60))
        except Exception: time.sleep(3)
    raise SystemExit('gta.wiki not reachable')
def page(title):
    d = get(action='query', prop='revisions', rvprop='content|timestamp', rvslots='main', titles=title, redirects=1)
    p = list(d['query']['pages'].values())[0]
    if 'missing' in p: return '', ''
    r = p['revisions'][0]; return r['slots']['main']['*'], r['timestamp']
def plain(v): return re.sub(r'\s+', ' ', re.sub(r"'''?|<[^>]+>|\{\{[^{}]*\}\}", '', re.sub(r'\[\[(?:[^\]|]*\|)?([^\]]*)\]\]', r'\1', v))).strip()
COORD = re.compile(r'x\s*:\s*(-?\d+(?:\.\d+)?)\s*,\s*y\s*:\s*(-?\d+(?:\.\d+)?)')
def rows(x):
    sec = x.split('==Locations==')[1] if '==Locations==' in x else x
    sec = sec.split('\n|}')[0]   # the last row has no '|-' after it
    for blk in re.split(r'\n\|-\s*\n', sec)[1:]:
        cells = [c for c in re.split(r'\n\|', '\n' + blk.strip())[1:]]
        yield cells
def money(s):
    v = [int(a.replace(',', '')) for a in re.findall(r'\$([\d,]+)', s)]
    return (v[0], v[-1]) if v else (0, 0)
places, ts = [], ''
sg, t1 = page("Smash 'n' Grabs"); ts = max(ts, t1)
for c in rows(sg):
    nm = plain(c[0]); m = COORD.search(c[-1]) if len(c) > 1 else None
    if nm and not nm.startswith('Unnamed') and m: places.append(['smash', nm, '', 0, 0, float(m.group(1)), float(m.group(2))])
pl, t2 = page('Payday Loans'); ts = max(ts, t2)
for c in rows(pl):
    raw = c[0]; nm = plain(raw.split('<br>')[0]); lo, hi = money(raw); m = COORD.search(c[-1]) if len(c) > 1 else None
    area = ''
    if ' - ' in nm: nm, area = [s.strip() for s in nm.split(' - ', 1)]
    if nm and not nm.startswith('Unnamed') and m: places.append(['payday', nm, area, lo, hi, float(m.group(1)), float(m.group(2))])
fx, t3 = page('Fences'); ts = max(ts, t3)
LEVEL = {'very low': 1, 'low': 2, 'medium': 3, 'high': 4}
fences = []
if '==List of Fences==' in fx:
    for blk in re.split(r'\n\|-\s*\n', fx.split('==List of Fences==')[1].split('\n|}')[0])[1:]:
        cells = re.split(r'\n\|', '\n' + blk.strip())[1:]
        if len(cells) < 4: continue
        nm = plain(cells[1]); desc = cells[2]; where = plain(desc.split('<br>')[0]).replace('Located at ', '')
        pay = {k: LEVEL.get(plain(v).lower(), 0) for k, v in re.findall(r"'''(Narcotics|Jewelry|Marked Bills):'''\s*([A-Za-z ]+?)(?=<br>|$)", desc)}
        if not pay and re.search(r'vehicle', desc, re.I): pay = {'Vehicles': 4}
        av = cells[3]; fm = re.search(r'Available after (.+?) in Chapter (\d)', plain(av)); um = re.search(r'Unavailable after (?:(.+?) in )?Chapter (\d)', plain(av))
        always = 1 if re.search(r'Always available', plain(av)) else 0
        if nm and not nm.startswith('Unnamed'): fences.append([nm, where, pay, fm.group(1).strip() if fm else '', int(fm.group(2)) if fm else 0, (um.group(1) or '').strip() if um else '', int(um.group(2)) if um else 0, always])
# robbery types: [id, count, needed for 100%, unlock chapter, status, source]
TYPES = [
 ['gangops', 39, 39, 1, 'reported', 'checklist'], ['bankjobs', 22, 22, 3, 'reported', 'checklist'], ['payday', len([p for p in places if p[0] == 'payday']) or 7, 7, 3, 'confirmed', 'gta.wiki'],
 ['smash', len([p for p in places if p[0] == 'smash']) or 35, 34, 2, 'confirmed', 'gta.wiki'], ['stickups', 91, 50, 1, 'reported', 'checklist'], ['vaults', 8, 8, 5, 'reported', 'checklist'],
]
out = {'ts': ts[:10], 'types': TYPES, 'places': places, 'fences': fences}
open(APP + '/heists.js', 'w', encoding='utf-8').write('window.HEISTS=' + json.dumps(out, ensure_ascii=False, separators=(',', ':')) + ';')
print('heists:', len(places), 'places', {t: len([p for p in places if p[0] == t]) for t in ('smash', 'payday')}, '| fences', len(fences), '| wiki revision', ts)
