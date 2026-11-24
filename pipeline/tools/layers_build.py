#!/usr/bin/env python3
"""Camadas do mapa que o dono aprovou (tools/layers_approved.json), dentro de app/www/heists.js. Rodar DEPOIS de heists_build.py.
usage: layers_build.py <app/www> <state dir> <work dir>

heists.js passa a ter dois conjuntos (publish_data.py já empacota vários globais num arquivo):
  window.HEISTS  — os assaltos; as operações de gangue aprovadas entram em places como ['gangops', nome, área, 0, 0, x, y, gangue, fonte]
  window.LAYERS  — {ts, credit, types: [[chave, n]], places: [[chave, nome, área, x, y, detalhe, fonte]]}
Posição pela SEQUÊNCIA de fontes (a de cima ganha): 1 gta.wiki ({{LeonidaDayMap}}) → 2 GTADB (data.js) → 3 Open GTA 6 Map
(fbritoferreira/gta6, CC BY 4.0: o app mostra o crédito quando algum ponto vem dele). Área = área do lugar do GTADB mais perto.
Se uma fonte cair, a camada fica como estava no heists.js de ontem (nunca encolhe)."""
import sys, os, re, json, math, subprocess, datetime, urllib.request

WWW, STATE, WORK = sys.argv[1], sys.argv[2], sys.argv[3]
HERE = os.path.dirname(os.path.abspath(__file__))
APR = json.load(open(os.path.join(HERE, 'layers_approved.json')))
GO = json.load(open(os.path.join(HERE, 'gangops.json')))
os.makedirs(WORK, exist_ok=True)

def globals_of(f):
    s = open(os.path.join(WWW, f), encoding='utf-8').read(); out, i, dec = {}, 0, json.JSONDecoder()
    while True:
        m = re.compile(r'\s*;?\s*window\.([A-Z_0-9]+)\s*=\s*').match(s, i)
        if not m: return out
        v, i = dec.raw_decode(s, m.end()); out[m.group(1)] = v

def key(s): return re.sub(r'[^a-z0-9]', '', (s or '').lower().replace('&', 'and'))
HS = globals_of('heists.js'); HE = HS['HEISTS']; OLD = HS.get('LAYERS')
if not OLD:   # heists_build.py acabou de reescrever o arquivo: as camadas de ontem estão no pacote publicado (heists.json na raiz do data-repo)
    try: OLD = json.load(open(os.path.join(HERE, '..', '..', 'heists.json'))).get('LAYERS')
    except Exception: OLD = None
OLD = OLD or {'places': []}
AT = globals_of('data.js')['ATLAS_PLACES']
GT = [(r[4][0], r[4][1], r[3], r[1]) for r in AT if r[4]]
def area(x, y):
    b = min(GT, key=lambda g: (g[0] - x) ** 2 + (g[1] - y) ** 2); return b[2]

# 1 gta.wiki
mc = os.path.join(WORK, 'wiki_points.json')
wiki = {}
try:
    subprocess.run([sys.executable, os.path.join(HERE, 'wiki_points.py'), WWW, STATE, mc], check=True, capture_output=True, timeout=600)
    for p in json.load(open(mc))['points']: wiki.setdefault(p['group'], []).append(p)
except Exception as e: print('gta.wiki fora do ar (%s): camadas ficam como ontem' % str(e)[:80])
# 3 Open GTA 6 Map (fórmula publicada por eles: gx = 32x - 16384, gy = 16384 - 32y)
ogm = []
try:
    req = urllib.request.Request('https://fbritoferreira.github.io/gta6/data/locations.json', headers={'User-Agent': 'generic-client'})
    ogm = [dict(l, gx=32 * l['x'] - 16384, gy=16384 - 32 * l['y']) for l in json.load(urllib.request.urlopen(req, timeout=120))]
except Exception as e: print('Open GTA 6 Map fora do ar (%s)' % str(e)[:80])

used_ogm = False
# ---- operações de gangue (assalto) ----
if 'gangops' in APR.get('heists', []):
    names = [o[1] for o in GO['operacoes']]
    wp = {key(p['label']): p for g in wiki.values() for p in g}
    gt = {key(r[1]): r for r in AT if r[1] and r[4]}
    og = {}
    for l in ogm:
        if l.get('kind') != 'gang': continue
        n = GO['ogm_alias'][l['id']][0] if l['id'] in GO['ogm_alias'] else next((n for n in names if key(n) == key(l['name'].split(': ', 1)[-1])), None)
        if n and n not in og: og[n] = l
    rows = []
    for g, n, _ in GO['operacoes']:
        if key(n) in wp: x, y, src = wp[key(n)]['x'], wp[key(n)]['y'], 'gta.wiki'
        elif key(n) in gt: x, y, src = gt[key(n)][4][0], gt[key(n)][4][1], 'GTADB'
        elif n in og: x, y, src = og[n]['gx'], og[n]['gy'], 'ogm'
        else: continue
        rows.append(['gangops', n, area(x, y), 0, 0, round(x), round(y), g, src])
    old = [p for p in HE['places'] if p[0] == 'gangops']
    if not old:
        try: old = [p for p in json.load(open(os.path.join(HERE, '..', '..', 'heists.json')))['HEISTS']['places'] if p[0] == 'gangops']
        except Exception: old = []
        HE['places'] += old if len(rows) < len(old) else []
    if len(rows) >= len(old):
        HE['places'] = [p for p in HE['places'] if p[0] != 'gangops'] + rows
    used_ogm |= any(r[8] == 'ogm' for r in (rows if len(rows) >= len(old) else old))
    for t in HE['types']:
        if t[0] == 'gangops': t[4], t[5] = 'mapped', 'gta.wiki + GTADB + Open GTA 6 Map'
    print('operações de gangue no mapa: %d de %d (%s)' % (len(rows), len(names), ', '.join('%s %d' % (s, sum(1 for r in rows if r[8] == s)) for s in ('gta.wiki', 'GTADB', 'ogm'))))

# ---- camadas (side missions, lojas de armas, drones) ----
places = []
for k in APR.get('layers', []):
    seen, rows = set(), []
    for p in sorted(wiki.get(k, []), key=lambda p: p['label']):
        if '(manufacturer)' in p['label'] or p['label'].lower().startswith('unnamed'): continue
        pos = (round(p['x'] / 10), round(p['y'] / 10)) if k == 'guns' else (key(p['label']), round(p['x']), round(p['y']))
        if pos in seen: continue                       # loja repetida no mesmo lugar (ex.: página da fabricante); side missions podem dividir o lugar
        seen.add(pos)
        sub = p['section'] if k == 'strangers' else ''   # side mission: quem dá a missão
        rows.append([k, p['label'], area(p['x'], p['y']), round(p['x']), round(p['y']), sub, 'gta.wiki'])
    old = [p for p in OLD['places'] if p[0] == k]
    places += rows if len(rows) >= len(old) else old
    print('camada %-10s %3d pontos%s' % (k, len(rows), '' if len(rows) >= len(old) else ' (menos que ontem: mantive os %d de ontem)' % len(old)))
LY = {'ts': datetime.date.today().isoformat(), 'types': [[k, sum(1 for p in places if p[0] == k)] for k in APR.get('layers', [])], 'places': places,
      'credit': 'ogm' if used_ogm else ''}
open(os.path.join(WWW, 'heists.js'), 'w', encoding='utf-8').write(
    'window.HEISTS=' + json.dumps(HE, ensure_ascii=False, separators=(',', ':')) + ';window.LAYERS=' + json.dumps(LY, ensure_ascii=False, separators=(',', ':')) + ';')
