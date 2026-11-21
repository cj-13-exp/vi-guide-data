#!/usr/bin/env python3
"""Syncs app/www/ph with the in-game place photos of a pinned GTADB revision.
usage: place_photos.py <landmarks.json> <photo-tree.json> <old-photo-tree.json|-> <download dir> <app/www>
- landmarks.json: GTADB map/data/6/landmarks.json at the pinned revision
- photo-tree.json: GitHub git tree of map/photos/6 at that revision (path, sha, size)
- old-photo-tree.json: the same listing for the revision the app's current photos came from, to spot replaced files
Keeps a photo for every named place whose in-game photo is at least 6 KB, resized to 520 px wide.
Photos withdrawn upstream are removed; photos.js is rewritten from the folder."""
import sys, json, os, subprocess, urllib.request
from concurrent.futures import ThreadPoolExecutor
REV = os.environ.get('GTADB_REV') or 'd406fea099e1df2bce42fd6b87eed04bce646629'   # gtadb_sync.py passes the revision it just read
land = json.load(open(sys.argv[1]))
tree = lambda p: {t['path']: (t['sha'], t['size']) for t in json.load(open(p))['tree']}
new = tree(sys.argv[2]); old = tree(sys.argv[3]) if sys.argv[3] != '-' else {}
raw, www = sys.argv[4], sys.argv[5]
ph = os.path.join(www, 'ph'); os.makedirs(raw, exist_ok=True)
have = {f[:-4] for f in os.listdir(ph) if f.endswith('.jpg')}
key = lambda i: i + ',ig.jpg'
named = [i for i, v in land.items() if '?' not in v[0].split(',')[0]]
want = {i for i in named if new.get(key(i), (0, 0))[1] >= 6000}
gone = {i for i in have if key(i) not in new}
changed = {i for i in have if key(i) in new and key(i) in old and old[key(i)][0] != new[key(i)][0]}
todo = sorted((want - have) | changed)
print(len(named), 'named,', len(want), 'with photo;', len(have), 'in app;', len(todo), 'to fetch (', len(changed), 'replaced upstream );', len(gone), 'withdrawn')

def fetch(i):
    p = os.path.join(raw, i + '.jpg')
    try:
        if not os.path.exists(p):
            url = 'https://raw.githubusercontent.com/rolux/gtadb.org/%s/map/photos/6/%s,ig.jpg' % (REV, i)
            b = urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'generic-client'}), timeout=60).read()
            if b[:2] != b'\xff\xd8': return (i, 'not a jpeg')
            open(p, 'wb').write(b)
        r = subprocess.run(['sips', '-s', 'format', 'jpeg', '-s', 'formatOptions', '80', '--resampleWidth', '520', p, '--out', os.path.join(ph, i + '.jpg')], capture_output=True, text=True)
        return (i, '' if r.returncode == 0 else r.stderr.strip()[:80])
    except Exception as e:
        return (i, str(e)[:80])

bad = [r for r in ThreadPoolExecutor(8).map(fetch, todo) if r[1]]
for i in gone: os.remove(os.path.join(ph, i + '.jpg'))
ids = sorted(f[:-4] for f in os.listdir(ph) if f.endswith('.jpg'))
open(os.path.join(www, 'photos.js'), 'w').write('window.PLACE_PHOTOS=' + json.dumps(ids, separators=(',', ':')) + ';')
print(len(todo) - len(bad), 'written,', len(bad), 'failed', bad[:10], '| removed', sorted(gone), '|', len(ids), 'photos in app')
