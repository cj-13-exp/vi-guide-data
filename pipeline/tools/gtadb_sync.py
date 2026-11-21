#!/usr/bin/env python3
"""Daily check of the open GTADB repository (rolux/gtadb.org, data and photos CC BY 4.0): new places, renamed places, new place photos.
usage: gtadb_sync.py <app/www> <work dir>
Reads the revision the app was built from (tools/gtadb_rev.txt), asks GitHub for the latest commit of main and, only when it differs, downloads
landmarks.json at the new revision, rebuilds app/www/data.js (tools/places_build.py) and syncs app/www/ph + photos.js (tools/place_photos.py,
which needs macOS 'sips'). Writes the new revision back. Nothing here touches coordinates by hand: they come from GTADB or not at all."""
import sys, os, json, subprocess, urllib.request
WWW, WORK = sys.argv[1], sys.argv[2]
HERE = os.path.dirname(os.path.abspath(__file__))
REVF = HERE + '/gtadb_rev.txt'
cur = open(REVF).read().strip() if os.path.exists(REVF) else ''
H = {'User-Agent': 'generic-client'}
if os.environ.get('GH_TOKEN'): H['Authorization'] = 'Bearer ' + os.environ['GH_TOKEN']
def get(url, raw=False):
    b = urllib.request.urlopen(urllib.request.Request(url, headers=H), timeout=90).read()
    return b if raw else json.loads(b)
API = 'https://api.github.com/repos/rolux/gtadb.org/'
latest = get(API + 'commits/main')['sha']
if latest == cur: print('GTADB unchanged at', cur[:7]); sys.exit(0)
print('GTADB moved', cur[:7], '->', latest[:7])
os.makedirs(WORK, exist_ok=True)
def photo_tree(rev, out):
    d = next(x for x in get(API + 'contents/map/photos?ref=' + rev) if x['name'] == '6')
    t = get(API + 'git/trees/' + d['sha'])
    if t.get('truncated'): raise SystemExit('photo tree truncated')
    json.dump(t, open(out, 'w'))
land = WORK + '/landmarks_new.json'
open(land, 'wb').write(get('https://raw.githubusercontent.com/rolux/gtadb.org/%s/map/data/6/landmarks.json' % latest, raw=True))
n = json.load(open(land))
if not isinstance(n, dict) or len(n) < 3000: raise SystemExit('landmarks.json looks wrong (%s entries): refusing to update' % len(n))
photo_tree(latest, WORK + '/photos_new.json')
if cur: photo_tree(cur, WORK + '/photos_old.json')
old_tree = WORK + '/photos_old.json' if cur else '-'
subprocess.run([sys.executable, HERE + '/places_build.py', land, WWW + '/data.js'], check=True)
subprocess.run([sys.executable, HERE + '/place_photos.py', land, WORK + '/photos_new.json', old_tree, WORK + '/gtadb_raw', WWW], check=True, env=dict(os.environ, GTADB_REV=latest))
open(REVF, 'w').write(latest + '\n')
print('GTADB updated to', latest[:7])
