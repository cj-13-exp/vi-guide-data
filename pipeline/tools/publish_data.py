#!/usr/bin/env python3
"""Packs the app's data files into data-dist/ (what the app downloads) and writes app/www/dataver.js (what the app was built with).
usage: publish_data.py [--root <project root>] [--base-url https://.../]
For every app/www/<name>.js of the form `window.<GLOBAL>=<json>;` it writes data-dist/<name>.json (an object {GLOBAL: value}) and one manifest.json:
  {format, generated, files: {name: {globals, sha256, bytes, count}}}
Release gate (exit code 1, nothing is written): invalid JSON, a name starting with 'Unnamed', or a file that shrank below 60% of the (not counting what the owner hid on purpose: hidden_counts.json)
previous manifest (an empty or truncated file must never reach the phones). Images are not part of this package (they ship in the app)."""
import sys, os, re, json, hashlib, time
args = sys.argv[1:]
ROOT = args[args.index('--root') + 1] if '--root' in args else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WWW, OUT = ROOT + '/app/www', ROOT + '/data-dist'
FORMAT = 1
FILES = ['data', 'wiki', 'photos', 'wiki2', 'real', 'gv', 'hundred', 'missions', 'wiki3', 'ref', 'hq', 'ig', 'official', 'chars', 'heists', 'gbinfo']
NAMED = {'wiki', 'wiki2', 'wiki3', 'missions', 'gv', 'real', 'chars', 'hundred'}      # files whose items have names the app lists
UNNAMED = re.compile(r'^\s*Unnamed\b')
prev = {}
if os.path.exists(OUT + '/manifest.json'): prev = json.load(open(OUT + '/manifest.json')).get('files', {})
def names(v):
    """item names the app lists: first string of every row (second for missions, whose first is an id); descriptions may say 'unnamed'"""
    if isinstance(v, dict):
        for k, x in v.items():
            if k == 'rows' and x and isinstance(x[0], list) and len(x[0]) > 2: yield from (r[1] for r in x if isinstance(r[1], str))
            else: yield from names(x)
    elif isinstance(v, list):
        for r in v:
            if isinstance(r, list) and r and isinstance(r[0], str): yield r[0]
def count(v):   # items, one level inside dicts (so {WIKI:{vehicles:[...300 rows]}} counts 300, not 1); the app counts the same way
    if isinstance(v, list): return len(v)
    if isinstance(v, dict): return sum(len(x) if isinstance(x, (list, dict)) else 1 for x in v.values())
    return 1
# itens que o dono tirou do app de propósito (data_admin.py apply grava hidden_counts.json): não contam como encolhimento
HIDDEN = json.load(open(WWW + '/hidden_counts.json')) if os.path.exists(WWW + '/hidden_counts.json') else {}
problems, packed = [], {}
for name in FILES:
    src = open('%s/%s.js' % (WWW, name), encoding='utf-8').read().strip()
    # a file may assign several globals: window.A=<json>;window.B=<json>;  -> one package {A: ..., B: ...}
    src2, vals, dec, i, bad = src, {}, json.JSONDecoder(), 0, None
    while i < len(src2):
        m = re.compile(r'\s*;?\s*window\.([A-Z_0-9]+)\s*=\s*').match(src2, i)
        if not m: bad = 'unexpected text at %d' % i; break
        try: v, i = dec.raw_decode(src2, m.end())
        except Exception as e: bad = 'invalid JSON (%s)' % e; break
        vals[m.group(1)] = v
        if not src2[i:].strip().strip(';'): break
    if bad or not vals: problems.append('%s: %s' % (name, bad or 'empty')); continue
    if name in NAMED:
        bad = [s for s in names(vals) if UNNAMED.match(s)]
        if bad: problems.append('%s: %d item(s) named Unnamed, e.g. %r' % (name, len(bad), bad[0]))
    n = sum(count(v) for v in vals.values())
    if name in prev and prev[name]['count'] >= 5 and n + HIDDEN.get(name, 0) < 0.6 * prev[name]['count']:
        problems.append('%s: shrank from %d to %d (below 60%%)' % (name, prev[name]['count'], n))
    text = json.dumps(vals, ensure_ascii=False, separators=(',', ':'))
    # the collection date (a top-level "ts") changes every run; if nothing else changed, keep the published file so phones do not download it again
    old_path = '%s/%s.json' % (OUT, name)
    if os.path.exists(old_path):
        try:
            old_txt = open(old_path, encoding='utf-8').read(); old_vals = json.loads(old_txt)
            strip = lambda d: {g: ({k: x for k, x in v.items() if k != 'ts'} if isinstance(v, dict) else v) for g, v in d.items()}
            if strip(old_vals) == strip(vals): text, n = old_txt, sum(count(v) for v in old_vals.values())
        except Exception: pass
    packed[name] = dict(globals_=sorted(vals), text=text, sha=hashlib.sha256(text.encode('utf-8')).hexdigest(), bytes=len(text.encode('utf-8')), count=n)
if problems:
    print('RELEASE GATE FAILED:'); [print('  -', p) for p in problems]; sys.exit(1)
os.makedirs(OUT, exist_ok=True)
changed = []
for name, p in packed.items():
    path = '%s/%s.json' % (OUT, name)
    if not (os.path.exists(path) and open(path, encoding='utf-8').read() == p['text']): changed.append(name)
    open(path, 'w', encoding='utf-8').write(p['text'])
files = {n: {'globals': p['globals_'], 'sha256': p['sha'], 'bytes': p['bytes'], 'count': p['count']} for n, p in packed.items()}
man = {'format': FORMAT, 'generated': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'files': files}
if changed or files != prev or not os.path.exists(OUT + '/manifest.json'): json.dump(man, open(OUT + '/manifest.json', 'w'), indent=1)
# what this build of the app contains, so it can tell whether the server has something newer
URL = args[args.index('--base-url') + 1] if '--base-url' in args else (open(ROOT + '/tools/data_url.txt').read().strip() if os.path.exists(ROOT + '/tools/data_url.txt') else '')
if URL and not URL.endswith('/'): URL += '/'
GEN = json.load(open(OUT + '/manifest.json'))['generated']      # generation time of the package this build embeds
open(WWW + '/dataver.js', 'w').write('window.DATA_URL=' + json.dumps(URL) + ';window.DATA_VER=' + json.dumps({'format': FORMAT, 'generated': GEN,'files': {n: {'g': f['globals'], 'sha': f['sha256'], 'n': f['count']} for n, f in files.items()}}, separators=(',', ':')) + ';')
print('data-dist: %d files, %d KB total | changed since last run: %s' % (len(files), sum(f['bytes'] for f in files.values()) // 1024, ', '.join(changed) or 'none'))
for n, f in files.items(): print('  %-9s %-24s %7d B  %5d items  %s' % (n, ','.join(f['globals']), f['bytes'], f['count'], f['sha256'][:10]))
