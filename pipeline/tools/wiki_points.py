#!/usr/bin/env python3
"""Pontos do mapa que a gta.wiki publica (predefinição {{LeonidaDayMap|x:…, y:…}}), todos os dias.
usage: wiki_points.py <app/www> <state dir> <out map_candidates.json>

A gta.wiki é a fonte da verdade do projeto e já foi aprovada pelo dono como fonte de coordenadas (assaltos, 21/11/2026).
As coordenadas estão no mesmo sistema do GTADB (conferido nos assaltos), então entram no nosso mapa sem conversão.
Este script NÃO desenha nada: gera candidatos por GRUPO (cartas colecionáveis, lojas de armas, Strangers & Freaks...)
para a tela de aprovação. Grupo novo ou ponto novo só aparece no app depois do OK do dono (regra "Mapa: perguntar sempre").
Texto da wiki fica só como pista interna ("fato"); a descrição do app é escrita do zero por nós.
Nunca usa nome que comece com "Unnamed". Estado: <state>/wiki_points_seen.json (data em que cada ponto apareceu)."""
import sys, os, re, json, time, hashlib, datetime, urllib.request, urllib.parse

WWW, STATE, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
UA = {'User-Agent': 'LeonidaCompanionPrototype/0.1 (fan app prototype; generic-client)'}
TODAY = datetime.date.today().isoformat()

def get(**p):
    p['format'] = 'json'
    for i in range(3):
        try: return json.load(urllib.request.urlopen(urllib.request.Request('https://gta.wiki/api.php?' + urllib.parse.urlencode(p), headers=UA), timeout=60))
        except Exception: time.sleep(3)
    raise SystemExit('gta.wiki fora do ar')

def embedded(tpl):
    out, cont = [], {}
    while True:
        r = get(action='query', list='embeddedin', eititle=tpl, eilimit=500, einamespace=0, **cont)
        out += [x['title'] for x in r['query']['embeddedin']]
        if 'continue' not in r: return out
        cont = {'eicontinue': r['continue']['eicontinue']}

def pages(titles):
    """wikitext, revision time and categories, 20 titles per request"""
    res = {}
    for i in range(0, len(titles), 20):
        r = get(action='query', prop='revisions|categories', rvprop='content|timestamp', rvslots='main', cllimit=500, titles='|'.join(titles[i:i + 20]), redirects=1)
        for p in r['query']['pages'].values():
            if 'revisions' not in p: continue
            rv = p['revisions'][0]
            res[p['title']] = (rv['slots']['main']['*'], rv['timestamp'], [c['title'].split(':', 1)[1] for c in p.get('categories', [])])
        time.sleep(1)
    return res

def plain(v):
    v = re.sub(r'<!--.*?-->', '', v, flags=re.S)
    # a picture whose caption is the name: [[File:x.jpg|thumb|'''[[Catch a Bigger Fish]]''']] -> Catch a Bigger Fish
    v = re.sub(r"\[\[(?:File|Image):[^\[\]]*\|'*\[\[(?:[^\]|]*\|)?([^\]]*)\]\]'*\]\]", r'\1', v)
    v = re.sub(r'\[\[(?:File|Image|Arquivo):[^\]]*\]\]', '', v)
    v = v.replace('((', ' (').replace('))', ')')
    v = re.sub(r'\{\{Small\|([^{}]*)\}\}', r'(\1)', v)
    v = re.sub(r'\{\{[^{}]*\}\}', '', v)
    v = re.sub(r'\[\[(?:[^\]|]*\|)?([^\]]*)\]\]', r'\1', v)
    v = re.sub(r"'''?|<[^>]+>", '', v)
    return re.sub(r'\s+', ' ', v).strip(' |')

def templates(t):
    """each {{LeonidaDayMap ...}} with balanced braces: (start, body)"""
    for m in re.finditer(r'\{\{\s*LeonidaDayMap', t):
        i, depth = m.start(), 0
        for j in range(i, len(t) - 1):
            if t[j:j + 2] == '{{': depth += 1
            elif t[j:j + 2] == '}}':
                depth -= 1
                if depth == 0: yield i, t[i:j + 2]; break

PT = re.compile(r'x\s*:\s*(-?\d+(?:\.\d+)?)\s*,\s*y\s*:\s*(-?\d+(?:\.\d+)?)(?:\s*,\s*title\s*:\s*([^,|\n}]+))?(?:\s*,\s*description\s*:\s*([^|\n}]+))?')

def row_cells(t, pos):
    """cells of the wikitable row that holds pos (None when not in a table)"""
    a = t.rfind('\n|-', 0, pos); b = t.rfind('\n{|', 0, pos); e = t.rfind('\n|}', 0, pos)
    if a < 0 or a < b and b > e or e > a: return None
    nxt = [x for x in (t.find('\n|-', pos), t.find('\n|}', pos)) if x >= 0]
    blk = t[a + 3:min(nxt) if nxt else len(t)]
    return [c for c in re.split(r'\n\|\|?|\|\|', '\n' + blk.split('\n', 1)[-1]) if c.strip() != '' or True][1:]

def section(t, pos):
    h = re.findall(r'\n(=+)\s*([^=\n]+?)\s*\1\s*\n', t[:pos])
    return plain(h[-1][1]) if h else ''

# grupos: o que o jogador vê como uma camada do mapa
GROUP_BY_PAGE = {'Collectible Card Sets': 'cards', 'Collectible Card Sets/locations': 'cards', 'Weapon Stores in GTA VI': 'guns',
                 'Unique Playlists': 'playlists', 'Top Fun Drone Races': 'drones', 'Strangers & Freaks': 'strangers',
                 "Smash 'n' Grabs": 'smash', 'Payday Loans': 'payday'}
IN_APP_ALREADY = {'smash', 'payday'}            # já desenhados no mapa (aprovados em 21/11/2026)

def group_of(title, cats):
    if title in GROUP_BY_PAGE: return GROUP_BY_PAGE[title]
    c = ' '.join(cats).lower()
    if re.search(r'gun stores|weapon stores|ammu|pawn', c) or re.search(r'gun|firearms|pawn|guns|shot\b|tackle|outfitters|hunting', title.lower()) and 'store' in c + ' store': return 'guns'
    if 'vehicles' in c: return 'vehicles'
    if 'missions' in c or 'strangers' in c: return 'strangers'
    return 'places'

def app_places():
    s = open(os.path.join(WWW, 'data.js'), encoding='utf-8').read()
    rows = json.loads(s[s.index('['):s.rindex(']') + 1])
    out = [(r[1], r[4][0], r[4][1]) for r in rows if r[4]]
    try:
        h = open(os.path.join(WWW, 'heists.js'), encoding='utf-8').read()
        hp = json.JSONDecoder().raw_decode(h, h.index('{'))[0].get('places', [])   # 1º objeto: HEISTS (o arquivo tem também LAYERS)
        out += [(p[1], p[5], p[6]) for p in hp]
    except Exception: pass
    return out

def nk(s): return re.sub(r'[^a-z0-9]+', '', s.lower())

def main():
    os.makedirs(STATE, exist_ok=True)
    seenf = os.path.join(STATE, 'wiki_points_seen.json')
    seen = json.load(open(seenf)) if os.path.exists(seenf) else {}
    titles = embedded('Template:LeonidaDayMap')
    P = pages(titles)
    mine = app_places()
    pts = {}
    for title, (t, ts, cats) in P.items():
        g = group_of(title, cats)
        for pos, body in templates(t):
            cells = row_cells(t, pos)
            shape = re.search(r'type\s*:\s*(polygon|line|polyline)', body)
            if shape:                                     # contorno de região ou rota: um item só, com o desenho inteiro
                poly = [[float(a), float(b)] for a, b in re.findall(r'x\s*:\s*(-?\d+(?:\.\d+)?)\s*,\s*y\s*:\s*(-?\d+(?:\.\d+)?)', body)]
                if len(poly) < 3: continue
                cx, cy = sum(p[0] for p in poly) / len(poly), sum(p[1] for p in poly) / len(poly)
                k = hashlib.sha1(('area|%s|%d' % (nk(title), len(poly))).encode()).hexdigest()[:12]
                pts[k] = {'id': k, 'group': 'areas', 'label': title[:80], 'page': title, 'section': '', 'x': round(cx), 'y': round(cy),
                          'shape': shape.group(1), 'poly': poly, 'fact': '', 'on_map': False, 'near': [], 'first_seen': seen.get(k, TODAY),
                          'page_rev': ts[:10], 'url': 'https://gta.wiki/wiki/' + urllib.parse.quote(title.replace(' ', '_'))}
                seen.setdefault(k, TODAY)
                continue
            for m in PT.finditer(body):
                x, y = float(m.group(1)), float(m.group(2))
                label, fact = (m.group(3) or '').strip(), (m.group(4) or '').strip()
                if not label and cells:
                    txt = [plain(c) for c in cells]
                    names = [c for c in txt if c and not re.fullmatch(r'[\d#.]+', c) and len(c) <= 60 and 'LeonidaDayMap' not in c]
                    label = names[0] if names else ''
                    longs = [c for c in txt if len(c) > 60]
                    fact = fact or (longs[0] if longs else '')
                if not label: label = title
                label = plain(label)
                if label.lower().startswith('unnamed'): continue
                sec = section(t, pos)
                k = hashlib.sha1(('%s|%s|%d|%d' % (g, nk(label), round(x / 5), round(y / 5))).encode()).hexdigest()[:12]
                if k in pts: continue
                near = [n for (n, px, py) in mine if (px - x) ** 2 + (py - y) ** 2 <= 900]
                same = [n for n in near if n and (nk(n) in nk(label) or nk(label) in nk(n))]
                pts[k] = {'id': k, 'group': g, 'label': label[:80], 'page': title, 'section': sec[:60], 'x': x, 'y': y,
                          'fact': plain(fact)[:300], 'on_map': bool(same) or g in IN_APP_ALREADY, 'near': (same or near)[:1],
                          'first_seen': seen.get(k, TODAY), 'page_rev': ts[:10],
                          'url': 'https://gta.wiki/wiki/' + urllib.parse.quote(title.replace(' ', '_'))}
                seen.setdefault(k, TODAY)
    groups = {}
    for p in pts.values():
        G = groups.setdefault(p['group'], {'group': p['group'], 'n': 0, 'n_new_today': 0, 'n_on_map': 0, 'pages': set()})
        G['n'] += 1; G['n_on_map'] += p['on_map']; G['n_new_today'] += p['first_seen'] == TODAY; G['pages'].add(p['page'])
    for G in groups.values(): G['pages'] = sorted(G['pages'])
    json.dump(seen, open(seenf, 'w'), indent=0)
    json.dump({'ts': datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'), 'source': 'gta.wiki {{LeonidaDayMap}}',
               'n_pages': len(P), 'groups': sorted(groups.values(), key=lambda g: -g['n']),
               'points': sorted(pts.values(), key=lambda p: (p['group'], p['label']))}, open(OUT, 'w'), ensure_ascii=False, indent=1)
    print('gta.wiki: %d páginas com mapa, %d pontos' % (len(P), len(pts)))
    for G in sorted(groups.values(), key=lambda g: -g['n']):
        print('  %-10s %3d pontos (%d já no mapa, %d novos hoje)' % (G['group'], G['n'], G['n_on_map'], G['n_new_today']))

if __name__ == '__main__':
    main()
