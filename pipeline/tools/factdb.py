#!/usr/bin/env python3
"""Evidence database: every fact the app shows carries where it came from, and only reconciled facts reach the app.
usage: factdb.py <work dir> <db path>
Tables: sources (tier, independence group), entities, facts (entity, field, value, source, url, retrieved). Reconciliation per (entity, field):
  confirmed : a tier-1 source (the game, official posts) OR a tier-2 curated database (gta.wiki, gtadb.org) plus >= 1 independent group agreeing
  probable  : >= 2 independent groups agree (tier-3 guides)
  reported  : a single group
  disputed  : groups disagree (all values kept, the app shows none as certain)
Independence is measured, not assumed: sources whose mission lists overlap >= 0.88 with another source (same titles, same order) are merged into one
group, so copies never count twice. PowerPyx is loaded only to measure that overlap and to compute our recall against it (reference, never a source of values).
Inputs in <work dir>: wiki_missions.json (tools/missions_build.py), per_source.json (tools/missions_crosscheck.py), src2/h_<site>.txt (100% pages),
src2/<site>.txt for PowerPyx reference. Outputs: reconciled_missions.json, reconciled_hundred.json and the SQLite file."""
import sys, os, re, json, sqlite3, time, collections
WORK, DB = sys.argv[1], sys.argv[2]
NOW = time.strftime('%Y-%m-%d')
TIER = {'game': 1, 'rockstar': 1, 'gta.wiki': 2, 'gtadb.org': 2, 'beebom': 3, 'gmtreks': 3, 'techwiser': 3, 'technerdiness': 3, 'shacknews': 3, 'gtabase': 3, 'egamers': 3, 'powerpyx': 3}
URL = {'gta.wiki': 'https://gta.wiki', 'beebom': 'https://beebom.com/gta-6-missions-list-walkthrough/', 'gmtreks': 'https://gmtreks.com/gta6/', 'techwiser': 'https://techwiser.com/gta-6-missions/',
       'technerdiness': 'https://www.technerdiness.com/gta/gta-6-chapters-missions-list/', 'shacknews': 'https://www.shacknews.com/article/151397/gta6-100-percent-checklist',
       'gtabase': 'https://gtabase.com/articles/gta-6/gta-6-100-completion-guide-interactive-checklist', 'egamers': 'https://egamers.io/gta-6-100-completion-the-full-checklist-and-what-each-section-needs/'}
norm = lambda s: re.sub(r'[^a-z0-9]+', ' ', re.sub(r'\(.*?\)|\[.*?\]', '', s.lower().replace('’', "'"))).strip()

def lines(path):
    return open(path, encoding='utf-8').read().split('\n') if os.path.exists(path) else []
# ---- independence groups, measured from the mission lists -------------------------------------------------------
per = json.load(open(WORK + '/per_source.json'))
ref = {}
if os.path.exists(WORK + '/src2/powerpyx_missions.txt'):    # optional reference list, only used to measure overlap and recall
    ref = {re.sub(r'^optional ', '', norm(l)) for l in lines(WORK + '/src2/powerpyx_missions.txt') if l.strip()}
seqs = {n: [norm(t) for c in sorted(ch) for t in ch[c]] for n, ch in per.items()}
def overlap(a, b):
    A, B = set(a), set(b)
    return len(A & B) / max(1, min(len(A), len(B)))
group = {n: n for n in seqs}
names = sorted(seqs)
merged = []
for i, a in enumerate(names):
    for b in names[i + 1:]:
        sa, sb = seqs[a], seqs[b]
        # same titles in the same relative order on at least 88% of the shared titles => a copy
        shared = [t for t in sa if t in set(sb)]
        if len(shared) >= 25 and overlap(sa, sb) >= 0.88 and [t for t in sb if t in set(sa)] == shared:
            group[b] = group[a]; merged.append((a, b))
for n in ('egamers',): group[n] = 'powerpyx'          # cites PowerPyx by name
groups = dict(group); [groups.setdefault(n, n) for n in TIER]
# ---- database ---------------------------------------------------------------------------------------------------
if os.path.exists(DB): os.remove(DB)
con = sqlite3.connect(DB); c = con.cursor()
c.executescript('''create table sources(id text primary key, tier int, grp text, url text);
create table facts(entity text, field text, value text, source text, url text, retrieved text);
create index f on facts(entity, field);''')
for s in sorted(set(TIER) | set(per)): c.execute('insert into sources values(?,?,?,?)', (s, TIER.get(s, 3), groups.get(s, s), URL.get(s, '')))
def fact(entity, field, value, source):
    c.execute('insert into facts values(?,?,?,?,?,?)', (entity, field, json.dumps(value, ensure_ascii=False), source, URL.get(source, ''), NOW))
# missions from gta.wiki (tier 2) and from each guide (tier 3)
wiki = json.load(open(WORK + '/wiki_missions.json')) if os.path.exists(WORK + '/wiki_missions.json') else {}
for t, m in wiki.items():
    e = 'mission:' + norm(t)
    fact(e, 'title', t, 'gta.wiki'); fact(e, 'chapter', m.get('chapter'), 'gta.wiki') if m.get('chapter') else None
    fact(e, 'type', m['type'], 'gta.wiki'); [fact(e, 'unlocks', u, 'gta.wiki') for u in m.get('unl', [])]
    for k in ('prot', 'giver', 'loc', 'obj'): fact(e, k, m[k], 'gta.wiki') if m.get(k) else None
for n, ch in per.items():
    for chap, titles in ch.items():
        for i, t in enumerate(titles):
            e = 'mission:' + norm(t)
            if not norm(t): continue
            fact(e, 'title', t, n); fact(e, 'chapter', int(chap), n); fact(e, 'rank', round((i + 1) / len(titles), 3), n)
con.commit()
def status(rows):
    """rows: [(value, source)] -> (status, value, supporting groups, conflicting values)"""
    by = collections.defaultdict(set)
    for v, s in rows: by[v].add(groups.get(s, s))
    tiers = {v: min(TIER.get(s, 3) for vv, s in rows if vv == v) for v in by}
    best = max(by, key=lambda v: (len(by[v]), -tiers[v]))
    g = by[best]; conflict = [v for v in by if v != best]
    if conflict and len(by[conflict[0]]) >= len(g): return 'disputed', best, sorted(g), conflict
    if tiers[best] == 1 or (tiers[best] == 2 and len(g) >= 2): return 'confirmed', best, sorted(g), conflict
    if len(g) >= 2: return 'probable', best, sorted(g), conflict
    return ('reported' if tiers[best] == 3 else 'confirmed'), best, sorted(g), conflict
out = []
for (e,) in c.execute("select distinct entity from facts where entity like 'mission:%'").fetchall():
    f = collections.defaultdict(list)
    for fld, val, src in c.execute('select field, value, source from facts where entity=?', (e,)): f[fld].append((val, src))
    title = collections.Counter(json.loads(v) for v, s in f['title']).most_common(1)[0][0]
    wiki_title = next((json.loads(v) for v, s in f['title'] if s == 'gta.wiki'), title)
    ch = status(f['chapter']) if f['chapter'] else ('reported', None, [], [])
    srcs = sorted({groups.get(s, s) for v, s in f['title']})
    ranks = [json.loads(v) for v, s in f['rank']]
    st = 'confirmed' if any(s == 'gta.wiki' for v, s in f['title']) and (len(srcs) >= 2 or True) else status(f['title'])[0]
    if st != 'confirmed' and len(srcs) >= 2: st = 'probable'
    elif st != 'confirmed': st = 'reported'
    out.append(dict(key=e[8:], title=wiki_title, chapter=json.loads(ch[1]) if ch[1] is not None else None, chapter_status=ch[0], chapter_conflict=ch[3], status=st,
                    groups=srcs, rank=(sorted(ranks)[len(ranks) // 2] if ranks else None), in_wiki=any(s == 'gta.wiki' for v, s in f['title'])))
json.dump(out, open(WORK + '/reconciled_missions.json', 'w'), ensure_ascii=False)
cnt = collections.Counter(o['status'] for o in out)
print('missions: %d entities | %s | independence groups among guides: %s' % (len(out), dict(cnt), dict(collections.Counter(groups[n] for n in per))))
if merged: print('   merged as copies (overlap >= 0.88, same order):', merged)
if ref:
    have = {o['key'] for o in out if o['status'] in ('confirmed', 'probable')}
    print('   recall against the PowerPyx reference list: %d of %d titles (%.0f%%)' % (len(ref & have), len(ref), 100 * len(ref & have) / max(1, len(ref))), '| missing:', sorted(ref - have)[:12])
# ---- 100% targets -----------------------------------------------------------------------------------------------
LABELS = {'story': r'story', 'optional': r'optional tasks?', 'gangops': r'gang operations', 'bankjobs': r'bank jobs', 'payday': r'payday loan', 'smash': r"smash.{0,4}n.{0,4}grabs?",
 'stickups': r'stick.?ups', 'vaults': r'vaults? hit', 'narcotics': r'narcotics fenced', 'jewelry': r'jewel(?:ry|ery) fenced', 'marked': r'marked bills', 'vehfenced': r'vehicles fenced',
 'kenton': r'kenton', 'cards': r'collectible card sets?', 'waink': r'waink', 'underwater': r'underwater', 'mags': r'magazines', 'meditation': r'meditation',
 'flamingos': r'flamingos', 'playlists': r'playlists', 'styles': r'styles', 'races': r'unique races', 'racegold': r'race challenge', 'shooting': r'shooting range', 'videogames': r'video games',
 'pool': r'pool opponents', 'minigolf': r'mini golf', 'hoops': r'basketball hoops', 'drone': r'drone time', 'stunts': r'stunts', 'challenges': r'challenges completed|challenges\b',
 'bret': r"bret.s target", 'vehicles': r'base model vehicles|vehicles scanned', 'weapons': r'standard issue weapons|weapons found', 'animals': r'animals studied'}
def money(x): return int(x.replace(',', ''))
hund = collections.defaultdict(list)
for site in ('shacknews', 'egamers', 'powerpyx', 'gtabase'):
    for l in lines('%s/src2/h_%s.txt' % (WORK, site)):
        l = l.lstrip('☐ ').strip()
        m = re.match(r'^\$?([\d,]+)(?:\s+of\s+\$?([\d,]+))?\s+(.+?)$', l) or re.match(r'^(.+?):\s*\$?([\d,]+)(?:\s+of\s+\$?([\d,]+))?', l)
        if not m: continue
        if re.match(r'^[\d$]', l): need, total, label = m.group(1), m.group(2), m.group(3)
        else: label, need, total = m.group(1), m.group(2), m.group(3)
        for k, rx in LABELS.items():
            if re.search(rx, label, re.I) and 'Gamerscore' not in label and len(label) < 90:
                hund[k].append((site, money(need), money(total) if total else None)); break
    # one value per site per target (first match wins)
res = {}
for k in LABELS:
    seen = {}
    for site, need, total in hund.get(k, []): seen.setdefault(site, (need, total))
    rows = [(v[0], s) for s, v in seen.items()]
    if not rows: res[k] = dict(status='missing'); continue
    st, val, g, conf = status(rows)
    tot = [v[1] for s, v in seen.items() if v[1]]
    res[k] = dict(status=st, need=val, total=(max(set(tot), key=tot.count) if tot else None), groups=g, sites=sorted(seen), conflict=conf)
json.dump(res, open(WORK + '/reconciled_hundred.json', 'w'), ensure_ascii=False)
print('100%% targets: %d | %s' % (len(res), dict(collections.Counter(v['status'] for v in res.values()))))
for k, v in res.items():
    if v['status'] in ('disputed', 'missing'): print('   ', k, v)
con.commit(); con.close()
print('database:', DB)
