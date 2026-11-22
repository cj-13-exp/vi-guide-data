#!/usr/bin/env python3
"""Builds app/www/eggs.js (easter eggs of GTA VI, stored as INFORMATION; not drawn on the map until the owner approves).
usage: eggs_build.py <app/www> <work dir>
Reads tools/eggs_seed.json (our own wording) and checks gta.wiki 'Secrets and Easter Eggs in GTA VI' (source of truth, facts only).
It reports entries that gta.wiki has and the seed does not (so they get added with our own words) and records the wiki revision.
Never writes names starting with 'Unnamed'. Coordinates: none (names only); a later step may resolve 'place' against GTADB."""
import sys, os, re, json, time, urllib.request, urllib.parse
APP, WORK = sys.argv[1], sys.argv[2]
HERE = os.path.dirname(os.path.abspath(__file__))
UA = {'User-Agent': 'LeonidaCompanionPrototype/0.1 (fan app prototype; generic-client)'}
seed = json.load(open(HERE + '/eggs_seed.json', encoding='utf-8'))['eggs']
ts, wiki_titles = '', []
try:
    q = urllib.parse.urlencode({'action': 'query', 'prop': 'revisions', 'rvprop': 'content|timestamp', 'rvslots': 'main',
                                'titles': 'Secrets_and_Easter_Eggs_in_GTA_VI', 'redirects': 1, 'format': 'json'})
    for i in range(3):
        try:
            d = json.load(urllib.request.urlopen(urllib.request.Request('https://gta.wiki/api.php?' + q, headers=UA), timeout=60)); break
        except Exception: time.sleep(3); d = None
    if d:
        r = list(d['query']['pages'].values())[0]['revisions'][0]
        txt = re.sub(r'<!--.*?-->', '', r['slots']['main']['*'], flags=re.S)
        ts = r['timestamp'][:10]
        wiki_titles = [t.strip(': ').strip() for t in re.findall(r"\n\|'''(.+?)'''", txt)]
except Exception as e:
    print('gta.wiki not reachable, keeping the seed only:', e)
eggs = [e for e in seed if not e['name'].startswith('Unnamed')]
ids = [e['id'] for e in eggs]
assert len(ids) == len(set(ids)), 'duplicate egg ids'
out = {'ts': ts, 'eggs': eggs}
open(APP + '/eggs.js', 'w', encoding='utf-8').write('window.EGGS=' + json.dumps(out, ensure_ascii=False, separators=(',', ':')) + ';')
known = ' '.join(e['name'].lower() + ' ' + e['how'].lower() for e in eggs)
new = [t for t in wiki_titles if t and t != 'TBA' and t.lower() not in known]
os.makedirs(WORK, exist_ok=True)
json.dump(new, open(WORK + '/eggs_new_in_wiki.json', 'w', encoding='utf-8'), ensure_ascii=False)
by = {}
for e in eggs: by[e['conf']] = by.get(e['conf'], 0) + 1
print('eggs:', len(eggs), by, '| with a named place:', len([e for e in eggs if e['place']]), '| wiki revision', ts, '| wiki titles not in seed:', new)
