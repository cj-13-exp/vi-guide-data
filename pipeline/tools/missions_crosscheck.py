#!/usr/bin/env python3
"""Second-source check for story missions: when gta.wiki does not have a mission yet, accept it only if two independent public guides agree.
usage: missions_crosscheck.py <work dir> [--min N]
Reads the mission tables of several public guides (downloaded as plain HTML with a generic client name, 1 request per 1.5 s), reduces each to
{chapter: [titles in order]}, and keeps a title only when at least N sources (default 2) list it. Only titles, chapters and order are kept
(facts); nothing else from those pages is stored or shipped. PowerPyx is NOT a source here (reference only, by the project's rule).
Output: <work>/consensus.json = [{title, chapter, rank, support:[source,...]}], and a readable report on stdout."""
import sys, os, re, json, html, time, urllib.request, collections
WORK = sys.argv[1]; MIN = int(sys.argv[sys.argv.index('--min') + 1]) if '--min' in sys.argv else 2
UA = {'User-Agent': 'LeonidaCompanionPrototype/0.1 (fan app prototype; generic-client)'}
SOURCES = {
 'beebom': 'https://beebom.com/gta-6-missions-list-walkthrough/',
 'gmtreks': 'https://gmtreks.com/gta6/page/01M7QSGT3QP6VF7KRTAP9HRZ1W',
 'techwiser': 'https://techwiser.com/gta-6-missions/',
 'technerdiness': 'https://www.technerdiness.com/gta/gta-6-chapters-missions-list/',
}
STOP = {'mission', 'missions', 'notes', 'note', 'character', 'characters', 'time requirement', 'requirement', 'reward', 'rewards', 'type', 'optional', 'required', 'yes', 'no', 'jason', 'lucia', 'both', 'story', 'main', 'total', '#', 'objective', 'objectives', 'chapter', 'prologue mission', 'skip to content', 'advertisement', 'image: rockstar games'}
def lines(path):
    t = open(path, encoding='utf-8', errors='ignore').read()
    t = re.sub(r'(?is)<(script|style|noscript|svg|nav|footer|header|aside)\b.*?</\1>', '', t)
    t = re.sub(r'(?i)</(p|div|li|h[1-6]|tr|td|th|section|article|ul|ol)>|<br\s*/?>', '\n', t); t = re.sub(r'<[^>]+>', '', t)
    return [re.sub(r'\s+', ' ', l).strip() for l in html.unescape(t).split('\n') if l.strip()]
def norm(s): return re.sub(r'[^a-z0-9]+', ' ', re.sub(r'\(.*?\)|\[.*?\]', '', s.lower().replace('’', "'"))).strip()
def title_ok(l):
    if not (3 <= len(l) <= 64) or l.lower() in STOP or re.fullmatch(r'[\d\W]+', l): return False
    if len(l.split()) > 9 or l.endswith(('.', '?')) and len(l.split()) > 4: return False
    if re.search(r'(?i)\b(chapter|missions?|walkthrough|guide|how to|all |every |total|trophy|achievement|read more|related)\b', l): return False
    return l[0].isupper() or l[0].isdigit()
def clean(l): return re.sub(r'\s*\(.*?\)\s*$', '', l).strip().rstrip('*').strip()
def parse(path):
    L = lines(path); heads = [i for i, l in enumerate(L) if re.match(r'(?i)^(gta 6 )?chapter\s*([1-5])\b', l)]
    out = {}
    for n in range(1, 6):
        best = None
        for i in [h for h in heads if int(re.search(r'([1-5])', L[h]).group(1)) == n]:
            j = next((h for h in heads if h > i and int(re.search(r'([1-5])', L[h]).group(1)) != n), min(len(L), i + 400))
            cand = [clean(l) for l in L[i + 1:j] if title_ok(clean(l))]
            if best is None or len(cand) > len(best): best = cand
        if best: out[n] = list(dict.fromkeys(best))
    return out
os.makedirs(WORK + '/src2', exist_ok=True); per = {}
for name, url in SOURCES.items():
    f = '%s/src2/%s.html' % (WORK, name)
    if not os.path.exists(f) or os.path.getsize(f) < 20000:
        try: open(f, 'wb').write(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40).read()); time.sleep(1.5)
        except Exception as e: print('  could not read', name, e); continue
    per[name] = parse(f); print('%-14s' % name, {k: len(v) for k, v in per[name].items()})
json.dump(per, open(WORK + '/per_source.json', 'w'), ensure_ascii=False)   # raw per-source lists, read by tools/factdb.py
rank = collections.defaultdict(lambda: collections.defaultdict(list)); sup = collections.defaultdict(set); display = {}
for name, ch in per.items():
    for n, titles in ch.items():
        for i, t in enumerate(titles):
            k = norm(t)
            if not k: continue
            rank[k][n].append((i + 1) / max(len(titles), 1)); sup[k].add(name); display.setdefault(k, t)
rows = []
for k, s in sup.items():
    if len(s) < MIN: continue
    n = max(rank[k], key=lambda c: len(rank[k][c])); r = sorted(rank[k][n])[len(rank[k][n]) // 2]
    rows.append({'title': display[k], 'chapter': n, 'rank': round(r, 3), 'support': sorted(s)})
rows.sort(key=lambda r: (r['chapter'], r['rank']))
json.dump(rows, open(WORK + '/consensus.json', 'w'), ensure_ascii=False)
print(len(rows), 'titles confirmed by >=%d independent sources' % MIN, {n: sum(1 for r in rows if r['chapter'] == n) for n in range(1, 6)})
for n in range(1, 6):
    print('--- chapter', n, '|', ' > '.join('%s%s' % (r['title'], '' if len(r['support']) > 2 else '*') for r in rows if r['chapter'] == n)[:900])
