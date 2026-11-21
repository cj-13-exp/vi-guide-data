#!/usr/bin/env python3
"""Builds app/www/missions.js: GTA VI missions in execution order, from gta.wiki (the project's source of truth).
usage: missions_build.py <app/www> <work dir>
Source: mission pages that use {{Infobox gameplay}} with style VI (type storyline / side / strangers), plus the chapter and giver headings of
'Missions in GTA VI'. Execution order comes from the 'unlockedby' / 'unlocks' links (topological order starting at Prologue), not from any list.
Only facts are stored (title, chapter, order, protagonist, giver, place names, objective count, links between missions). Summaries are our own
words in tools/mission_text.json (id -> [en, pt-BR]); a mission without a summary still shows up, with its objective count.
Never writes names starting with 'Unnamed'. Re-run any time: each new mission page on gta.wiki appears by itself."""
import sys, os, re, json, time, urllib.request, urllib.parse, collections
APP, WORK = sys.argv[1], sys.argv[2]
HERE = os.path.dirname(os.path.abspath(__file__))
UA = {'User-Agent': 'LeonidaCompanionPrototype/0.1 (fan app prototype; generic-client)'}
def get(**p):
    p['format'] = 'json'
    for i in range(3):
        try: return json.load(urllib.request.urlopen(urllib.request.Request('https://gta.wiki/api.php?' + urllib.parse.urlencode(p), headers=UA), timeout=60))
        except Exception: time.sleep(3)
    raise SystemExit('gta.wiki not reachable')
def members(cat):
    out, cont = [], {}
    while True:
        d = get(action='query', list='categorymembers', cmtitle='Category:' + cat, cmlimit='500', cmnamespace='0', **cont)
        out += [m['title'] for m in d['query']['categorymembers']]
        if 'continue' in d: cont = {'cmcontinue': d['continue']['cmcontinue']}
        else: return out
titles = sorted(set(members('New content in GTA VI') + members('Gameplay in GTA VI')))
pages = {}
for i in range(0, len(titles), 50):
    d = get(action='query', prop='revisions', rvprop='content|timestamp', rvslots='main', titles='|'.join(titles[i:i + 50]))
    for p in d['query']['pages'].values():
        r = (p.get('revisions') or [{}])[0]; x = (r.get('slots', {}).get('main', {}) or {}).get('*', '')
        if re.search(r'\{\{\s*Infobox gameplay', x, re.I) and re.search(r'\|\s*style\s*=\s*VI\b', x): pages[p['title']] = (x, r.get('timestamp'))
    time.sleep(0.5)
def field(x, k):
    m = re.search(r'\|\s*' + k + r'\s*=(.*?)(?=\n\s*\|\s*[A-Za-z_]+\s*=|\n\}\}|\Z)', x, re.S)   # values may hold [[a|b]] links, so stop at the next |key= line
    return m.group(1).strip() if m else ''
def links(v):
    out = []
    for a, b in re.findall(r'\[\[([^\]|#]+)(?:\|([^\]]+))?\]\]', v):
        a = re.sub(r'\s*\(GTA VI\)$', '', a.strip())
        if a and a not in out and not a.lower().startswith(('file:', 'category:')): out.append(a)
    return out
def plain(v): return re.sub(r'\s+', ' ', re.sub(r"'''?|<[^>]+>|\{\{[^{}]*\}\}", '', re.sub(r'\[\[(?:[^\]|]*\|)?([^\]]*)\]\]', r'\1', v))).strip()
M = {}
for t, (x, ts) in pages.items():
    ty = plain(field(x, 'type')).lower()
    if ty not in ('storyline', 'side', 'strangers', 'stranger'): continue
    if re.match(r'\s*Unnamed\b', t): continue
    obj = x.split('==Objectives==')[1].split('\n==')[0] if '==Objectives==' in x else ''
    M[t] = dict(id=re.sub(r'[^a-z0-9]+', '-', t.lower()).strip('-'), title=t, type='story' if ty == 'storyline' else 'side', prot=[plain(a) for a in re.split(r'[,\n*]+', field(x, 'protagonists')) if plain(a)],
                giver=plain(field(x, 'for')), loc=links(field(x, 'location')), by=links(field(x, 'unlockedby')), unl=links(field(x, 'unlocks')), obj=len(re.findall(r'^\*', obj, re.M)), ts=ts)
# chapters and givers from the list page
chap, giver, cur = {}, {}, None
lp = get(action='query', prop='revisions', rvprop='content', rvslots='main', titles='Missions in GTA VI')['query']['pages']
lt = list(lp.values())[0]['revisions'][0]['slots']['main']['*']
for line in lt.split('\n'):
    h3 = re.match(r'===\s*Chapter\s*(\d+)\s*===', line)
    if h3: cur = int(h3.group(1)); who = None; continue
    h4 = re.match(r'====\s*(.+?)\s*====', line)
    if h4: who = plain(h4.group(1)); continue
    if cur and re.match(r'\|\s*[^|!{}\s][^|]*$', line) and not line.startswith('|-') and not line.startswith('|}'):
        name = plain(line[1:])
        if name and not name.startswith('Image'): chap[name] = cur; giver[name] = who
def key(n): return re.sub(r'\s*\(.*?\)\s*$', '', n.replace('\u2019', "'").replace('\u2018', "'")).strip().lower()   # curly and straight apostrophes are the same title
byk = {key(t): t for t in M}
for t, m in M.items():
    k = key(t); c = chap.get(t) or chap.get(m['title']) or next((chap[n] for n in chap if key(n) == k), None)
    m['chapter'] = c
    m['giver'] = m['giver'] or next((giver[n] for n in giver if key(n) == k), '') or ''
# order: breadth-first from the roots over the unlock graph, so a mission always comes after the one that unlocks it
for m in M.values():
    m['by'] = [byk[key(b)] for b in m['by'] if key(b) in byk]; m['unl'] = [byk[key(u)] for u in m['unl'] if key(u) in byk]
for t, m in M.items():
    for u in m['unl']:
        if t not in M[u]['by']: M[u]['by'].append(t)
indeg = {t: len([b for b in m['by'] if b in M]) for t, m in M.items()}
order, ready = [], sorted([t for t, d in indeg.items() if d == 0 and M[t]['type'] == 'story'], key=lambda t: (M[t]['chapter'] or 9, t))
seen = set()
while ready:
    t = ready.pop(0)
    if t in seen: continue
    seen.add(t); order.append(t)
    for u in M[t]['unl']:
        indeg[u] -= 1
        if indeg[u] <= 0 and u not in seen: ready.append(u)
    ready.sort(key=lambda t: (M[t]['chapter'] or 9, t))
rest = [t for t in M if t not in seen]
for n, t in enumerate(order + sorted(rest)): M[t]['order'] = n + 1
for m in M.values():
    if m['chapter'] is None and m['by']: m['chapter'] = next((M[b]['chapter'] for b in m['by'] if M[b]['chapter']), None)
json.dump({t: {k: v for k, v in m.items()} for t, m in M.items()}, open(WORK + '/wiki_missions.json', 'w'), ensure_ascii=False)   # pure gta.wiki facts for tools/factdb.py
# second source: titles two independent public guides agree on (tools/missions_crosscheck.py) fill what gta.wiki has no page for yet
NOISE = re.compile(r'(?i)leave a reply|cancel reply|^name$|^email$|^website$|^facebook$|^twitter$|comment|subscribe|newsletter|share|^home$|top of the world, ma$|^prologue$')
rec = json.load(open(WORK + '/reconciled_missions.json', encoding='utf-8')) if os.path.exists(WORK + '/reconciled_missions.json') else []
cons = [dict(title=o['title'], chapter=o['chapter'], rank=o['rank'] if o['rank'] is not None else 0.5, support=o['groups'] or ['gta.wiki']) for o in rec if o['status'] in ('confirmed', 'probable') and o['chapter']]   # tools/factdb.py decides what is trustworthy
CH = {1: 'Just Like Paradise', 2: 'Paradise Lost', 3: 'Tits Ass Drug Money', 4: 'Vice City, Baby', 5: 'Top of the World, Ma'}
rankof = {}
for c in cons:
    if NOISE.search(c['title']) or re.match(r'\s*Unnamed\b', c['title']): continue
    k = key(c['title']); rankof[k] = (c['chapter'], c['rank'], c['support'])
    if k not in byk:
        i = re.sub(r'[^a-z0-9]+', '-', c['title'].lower()).strip('-')
        M[c['title']] = dict(id=i, title=c['title'], type='story', prot=[], giver='', loc=[], by=[], unl=[], obj=0, ts='', chapter=c['chapter'], order=0, src=c['support'])
        byk[k] = c['title']
for t, m in M.items():
    m.setdefault('src', ['gta.wiki'])
    k = key(t)
    if k in rankof:
        if not m.get('chapter'): m['chapter'] = rankof[k][0]
        m['rank'] = rankof[k][1]
# Strangers & Freaks: the wiki lists every strand's missions in one table before each has its own page. Facts only (name, giver strand, chapter, who can play it, whether it counts for the
# trophy); the in-game blurbs are not copied. A mission that already has a page, or the same title from another source, is not added twice.
def sf_rows():
    d = get(action='query', prop='revisions', rvprop='content|timestamp', rvslots='main', titles='Strangers & Freaks', redirects='1')
    pg = list(d['query']['pages'].values())[0]
    if 'missing' in pg: return [], ''
    r = pg['revisions'][0]; x = r['slots']['main']['*']; ts_ = r['timestamp']
    body = x.split('==List of Missions==')[1] if '==List of Missions==' in x else ''
    out, ch, strand, n = [], None, '', 0
    for part in re.split(r'(?m)^(={3,4}[^=\n]+={3,4})\s*$', body):
        h = re.match(r'(={3,4})\s*([^=\n]+?)\s*={3,4}$', part.strip()) if part.strip().startswith('=') else None
        if h:
            if len(h.group(1)) == 3:
                m_ = re.match(r'Chapter\s*(\d+)', h.group(2)); ch = int(m_.group(1)) if m_ else ch; strand = ''
            else: strand = re.sub(r'\s*\(Part \d+\)', '', plain(h.group(2)))
            continue
        for blk in re.split(r'\n\|-\s*\n', part)[1:]:
            cells = re.split(r'\n\|', '\n' + blk.strip().split('\n|}')[0])[1:]
            if len(cells) < 5: continue
            nm = re.search(r"\[\[([^\]|#]+)(?:\|[^\]]*)?\]\]", re.sub(r'\[\[File:[^\]]*\|', '', cells[0]) if '[[File:' in cells[0] else cells[0])
            nm = nm.group(1).strip() if nm else plain(cells[0])
            if not nm or nm.lower().startswith(('unnamed', 'file:')) or re.match(r'(?i)^name\s*(/|&|and)\s*image$', nm): continue   # header cells are not missions
            out.append(dict(title=nm, chapter=ch, strand=strand, prot=[re.sub(r'(?i)\s+only$', '', a.strip()) for a in re.split(r'\s*&\s*', plain(cells[2])) if a.strip()], trophy=bool(re.search(r'\{\{\s*Yes', cells[4], re.I)), i=n)); n += 1
    return out, ts_
SF, sf_ts = sf_rows()
for q in SF:
    if q['title'] in M or key(q['title']) in byk: continue
    nrank = 0.2 + 0.6 * q['i'] / max(len(SF), 1)
    M[q['title']] = dict(id=re.sub(r'[^a-z0-9]+', '-', q['title'].lower()).strip('-'), title=q['title'], type='side', prot=q['prot'], giver=q['strand'], loc=[], by=[], unl=[], obj=0, ts=sf_ts or '', chapter=q['chapter'], order=0, src=['gta.wiki'], rank=nrank, trophy=q['trophy'])
    byk[key(q['title'])] = q['title']
# a mission with no chapter of its own takes it from the graph: from the mission that unlocks it, or (a root such as the Prologue) from what it unlocks.
# Runs after the guides' chapters are merged, and to a fixed point, so the result does not depend on where the data came from.
byt = {M[t]['id']: t for t in M}
for _ in range(5):
    for t, m in M.items():
        if m['chapter']: continue
        cands = [M[b]['chapter'] for b in m['by'] if b in M and M[b]['chapter']] or [M[u]['chapter'] for u in m['unl'] if u in M and M[u]['chapter']]
        if cands: m['chapter'] = min(cands)
# final order: chapter, then the graph position for wiki missions or the guides' rank for the others (both on a 0..1 scale)
pos = {t: i / max(len(order), 1) for i, t in enumerate(order)}
def sortkey(t):
    m = M[t]; return (m['chapter'] or 9, pos.get(t, m.get('rank', 0.5)) if t in pos and 'rank' not in m else m.get('rank', pos.get(t, 0.5)), t)
for n, t in enumerate(sorted(M, key=sortkey)): M[t]['order'] = n + 1
text = json.load(open(HERE + '/mission_text.json', encoding='utf-8')) if os.path.exists(HERE + '/mission_text.json') else {}
rows = []
for t in sorted(M, key=lambda t: M[t]['order']):
    m = M[t]; s = text.get(m['id'])
    rows.append([m['id'], m['title'], m['type'], m['chapter'], m['order'], m['prot'], m['giver'], m['loc'], [M[b]['id'] for b in m['by']], [M[u]['id'] for u in m['unl']], m['obj'], s[0] if s else '', s[1] if s else '', m.get('src', ['gta.wiki']), 'confirmed' if 'gta.wiki' in m.get('src', ['gta.wiki']) else 'probable', 1 if m.get('trophy') else 0])
open(APP + '/missions.js', 'w', encoding='utf-8').write('window.MISSIONS=' + json.dumps({'ts': max(m['ts'] for m in M.values() if m['ts']), 'chapters': CH, 'rows': rows}, ensure_ascii=False, separators=(',', ':')) + ';')
print(len(rows), 'missions written;', collections.Counter(r[2] for r in rows), '| by chapter', dict(collections.Counter(r[3] for r in rows)))
for r in rows[:30]: print('  %2d ch%s %-34s by %-24s -> %s' % (r[4], r[3], r[1][:34], ','.join(r[8])[:24], ','.join(r[9])[:50]))
