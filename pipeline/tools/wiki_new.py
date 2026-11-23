#!/usr/bin/env python3
"""Tudo o que nasce na gta.wiki sobre GTA VI, para o dono avaliar (pedido de 23/11/2026: "tudo novo que aparecer na gta wiki").
usage: wiki_new.py <app/www> <state dir> <out wiki_new.json>

Lê as páginas NOVAS (recentchanges, tipo new) desde a última rodada, descarta redirecionamentos e o que não é de GTA VI
(categorias da própria wiki), e marca para cada página: tipo (pela categoria), se tem coordenada do mapa ({{LeonidaDayMap}})
e se o app já tem um item com esse nome. Nada entra no app daqui: vira cartão na página Aprovações.
Estado: <state>/wiki_new_state.json (até quando já foi lido + páginas já vistas, para não repetir)."""
import sys, os, re, json, time, datetime, urllib.request, urllib.parse

WWW, STATE, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
UA = {'User-Agent': 'LeonidaCompanionPrototype/0.1 (fan app prototype; generic-client)'}
NOW = datetime.datetime.utcnow()
FIRST_LOOKBACK_DAYS = 3

def get(**p):
    p['format'] = 'json'
    for i in range(3):
        try:
            r = json.load(urllib.request.urlopen(urllib.request.Request('https://gta.wiki/api.php?' + urllib.parse.urlencode(p), headers=UA), timeout=60))
            time.sleep(0.6); return r
        except Exception: time.sleep(3)
    raise SystemExit('gta.wiki fora do ar')

GROUPS = [('missao', r'Missions|Mission Transcripts|Strangers'), ('veiculo', r'Vehicles'), ('arma', r'Weapons'),
          ('lugar', r'Locations|Buildings|Structures|Properties|Neighborhoods|Islands'), ('empresa', r'Businesses|Stores|Restaurants'),
          ('atividade', r'Gameplay|Activities|Collectibles|Hobbies|Achievements|Trophies'), ('animal', r'Animals|Wildlife'),
          ('personagem', r'Characters'), ('organizacao', r'Organizations|Gangs'), ('midia', r'Media|Radio|Songs|Films|TV|Websites|Books'),
          ('atualizacao', r'Title Updates')]

def group_of(cats):
    c = ' | '.join(cats)
    for g, rx in GROUPS:
        if re.search(rx + r'[^|]*(?:GTA VI|Grand Theft Auto VI)', c): return g
    return 'outro'

def nk(s): return re.sub(r'[^a-z0-9]+', '', re.sub(r"'s\b", '', str(s).lower()))

def app_blob():
    b = []
    for f in os.listdir(WWW):
        if f.endswith('.js') and f not in ('analytics.js', 'datasync.js', 'native.js', 'dataver.js'):
            try: b.append(open(os.path.join(WWW, f), encoding='utf-8').read())
            except Exception: pass
    return nk(' '.join(b))

def main():
    os.makedirs(STATE, exist_ok=True)
    stf = os.path.join(STATE, 'wiki_new_state.json')
    st = json.load(open(stf)) if os.path.exists(stf) else {}
    since = st.get('until') or (NOW - datetime.timedelta(days=FIRST_LOOKBACK_DAYS)).strftime('%Y-%m-%dT%H:%M:%SZ')
    seen = st.get('seen', {})
    rc, cont = [], {}
    while True:
        r = get(action='query', list='recentchanges', rctype='new', rcnamespace=0, rclimit=500, rcend=since, rcprop='title|timestamp|redirect', **cont)
        rc += [x for x in r['query']['recentchanges'] if 'redirect' not in x]
        if 'continue' in r: cont = {'rccontinue': r['continue']['rccontinue']}
        else: break
    titles = sorted({x['title'] for x in rc if x['title'] not in seen and not re.match(r'\s*Unnamed\b', x['title'])
                     and '/' not in x['title']})          # subpáginas (transcrições, galerias, notas de atualização) não são itens
    created = {x['title']: x['timestamp'] for x in rc}
    have = app_blob()
    out = []
    for i in range(0, len(titles), 20):
        r = get(action='query', prop='categories|revisions|info|pageimages', cllimit=500, rvprop='content', rvslots='main',
                piprop='thumbnail|name', pithumbsize=320, pilimit=20, titles='|'.join(titles[i:i + 20]), redirects=1)
        for p in r['query']['pages'].values():
            if 'missing' in p or 'redirect' in p: continue
            cats = [c['title'].split(':', 1)[1] for c in p.get('categories', [])]
            if not any(re.search(r'GTA VI|Grand Theft Auto VI', c) for c in cats): continue
            tx = ((p.get('revisions') or [{}])[0].get('slots', {}).get('main', {}) or {}).get('*', '')
            pts = re.findall(r'x\s*:\s*(-?\d+(?:\.\d+)?)\s*,\s*y\s*:\s*(-?\d+(?:\.\d+)?)', ''.join(re.findall(r'\{\{\s*LeonidaDayMap[^}]*\}\}', tx)))
            t = p['title']
            pi = p.get('pageimage', ''); th = (p.get('thumbnail') or {}).get('source', '')
            if not (re.search(r'GTAVI|GTA6', pi, re.I) and not re.search(r'logo|icon|badge|map|poster|cover|artwork|fanart|concept|real|stock', pi, re.I)): th = ''   # só tela do jogo
            out.append({'title': t, 'thumb': th, 'image': pi if th else '', 'created': created.get(t, '')[:10], 'group': group_of(cats),
                        'cats': [c for c in cats if re.search(r'GTA VI', c) and not c.startswith('New content')][:4],
                        'new_content': any(c.startswith('New content') for c in cats), 'returning': any(c.startswith('Returning content') for c in cats),
                        'map_points': len(pts), 'xy': [float(pts[0][0]), float(pts[0][1])] if pts else None,
                        'in_app': len(nk(t)) >= 4 and nk(t) in have, 'size': len(tx),
                        'url': 'https://gta.wiki/wiki/' + urllib.parse.quote(t.replace(' ', '_'))})
            seen[t] = created.get(t, '')[:10]
    st = {'until': NOW.strftime('%Y-%m-%dT%H:%M:%SZ'), 'seen': seen}
    json.dump(st, open(stf, 'w'), ensure_ascii=False, indent=0)
    json.dump({'ts': st['until'], 'since': since, 'pages': out}, open(OUT, 'w'), ensure_ascii=False, indent=1)
    from collections import Counter
    print('gta.wiki: %d páginas novas de GTA VI desde %s' % (len(out), since[:10]), dict(Counter(x['group'] for x in out)))

if __name__ == '__main__':
    main()
