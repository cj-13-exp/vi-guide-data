#!/usr/bin/env python3
"""Coleta diária do Open GTA 6 Map (github.com/fbritoferreira/gta6, dados CC BY 4.0: pode usar, até comercialmente, com crédito
"Map data from Open GTA 6 Map (fbritoferreira), CC BY 4.0"). É a 3ª fonte da sequência de posições do app:
  1 gta.wiki ({{LeonidaDayMap}}, fonte da verdade) → 2 GTADB (exato) → 3 Open GTA 6 Map → 4 outras bases abertas → 5 Map Genie por
  foto (sob pedido) → 6 texto de guia + lugar do GTADB (aproximado). Fonte de cima sempre ganha; concordância sobe a confiança.
usage: ogm_sync.py <saída.json>

Baixa locations.json e places.json publicados por eles e converte as coordenadas para as do nosso mapa com uma conversão afim
publicada por eles e conferida TODO DIA pelos lugares que eles e o GTADB têm com o mesmo id (L…), lidos do landmarks.json do GTADB. Se o erro mediano
passar de 5 m, para sem gravar (alguém mudou o formato). Nada aqui desenha no mapa: os pontos viram cartões de camada para o dono."""
import sys, os, json, math, urllib.request, datetime

OUT = sys.argv[1]
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from map_compare import conv

H = {'User-Agent': 'generic-client'}
def get(url): return json.load(urllib.request.urlopen(urllib.request.Request(url, headers=H), timeout=120))
BASE = 'https://fbritoferreira.github.io/gta6'
LOC, PLA, CAT = get(BASE + '/data/locations.json'), get(BASE + '/data/places.json'), get(BASE + '/data/categories.json')
rev = open(os.path.join(HERE, 'gtadb_rev.txt')).read().strip() if os.path.exists(os.path.join(HERE, 'gtadb_rev.txt')) else 'main'
GT = get('https://raw.githubusercontent.com/rolux/gtadb.org/%s/map/data/6/landmarks.json' % rev)
pairs = [[p['x'], p['y'], GT[p['id']][1][0], GT[p['id']][1][1]] for p in PLA if p.get('id') in GT and len(GT[p['id']][1]) == 2]
if len(pairs) < 50: raise SystemExit('poucos lugares em comum com o GTADB (%d): não gravo' % len(pairs))
# fórmula publicada por eles (assets.json): x = (gx + 16384) / 32, y = (16384 - gy) / 32  →  gx = 32x - 16384, gy = 16384 - 32y
T = [32.0, 0.0, -16384.0, 0.0, -32.0, 16384.0]
e = [math.hypot(conv(T, p[0], p[1])[0] - p[2], conv(T, p[0], p[1])[1] - p[3]) for p in pairs]; es = sorted(e); med = es[len(es) // 2]
if med > 5: raise SystemExit('a fórmula não bate mais com o GTADB (erro mediano %.1f m): não gravo' % med)
kinds = {k['key']: k for k in CAT.get('kinds', [])}
pts = []
for l in LOC:
    x, y = conv(T, l['x'], l['y'])
    pts.append({'id': l['id'], 'kind': l.get('kind', ''), 'type': l.get('type', ''), 'name': l.get('name', ''), 'area': l.get('area') or '',
                'x': round(x), 'y': round(y), 'conf': l.get('confidence') or '', 'desc': (l.get('description') or '')[:400],
                'shot': (BASE + '/' + l['screenshot']) if l.get('screenshot') else '',
                'group': (kinds.get(l.get('kind')) or {}).get('group', '')})
json.dump({'source': 'Open GTA 6 Map (fbritoferreira/gta6)', 'license': 'CC BY 4.0', 'credit': 'Map data from Open GTA 6 Map (fbritoferreira), CC BY 4.0',
           'date': datetime.date.today().isoformat(), 'T': T, 'pairs': len(pairs), 'median_m': round(med, 2), 'points': pts},
          open(OUT, 'w'), ensure_ascii=False)
print('Open GTA 6 Map: %d pontos em %d tipos · conversão por %d lugares do GTADB, erro mediano %.1f m' % (len(pts), len({p['type'] for p in pts}), len(pairs), med))
