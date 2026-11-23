#!/usr/bin/env python3
"""Administração dos dados do app (aba "Dados do app" da página Aprovações VI Guide).
  data_admin.py catalog <app/www> <out dir> [hidden.json] [item_videos.json] [map_candidates.json]
        monta o catálogo: TUDO o que está na base, com a ficha completa (os mesmos campos que o app mostra), foto, vídeo e situação:
        "app" (aparece no app), "stored" (guardado na base, não sobe: easter eggs, pontos da gta.wiki ainda não desenhados) e
        "out" (o dono tirou do app; vem de hidden.json). Gera também as folhas de miniaturas (sprites) das fotos.
  data_admin.py apply <app/www> <hidden.json>
        tira do app o que o dono marcou como "Fora do app" (reescreve os .js de dados). Roda na rotina diária ANTES de publish_data.py
        (o pacote que os celulares baixam já sai sem o item) e antes de cada build.

hidden.json: {"<tipo>": {"<chave>": [nome, detalhe]}} (ou {"<tipo>": [chave, ...]}), copiado do banco da página pela rotina diária.
Chave estável por tipo: nome (veículos, armas, personagens, animais, gangues, rádios, organizações, mídia, edições), id (missões, lugares,
trapaças, easter eggs, metas), tipo|nome|x|y (assaltos)."""
import sys, os, re, json, hashlib, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
L = {'body': 'Carroceria', 'maker': 'Fabricante', 'cap': 'Capacidade', 'fire': 'Modo de disparo', 'job': 'Ocupação', 'links': 'Ligações',
     'home': 'Onde vive', 'type': 'Tipo', 'where': 'Onde aparece', 'genre': 'Gênero', 'host': 'Apresentação', 'leader': 'Liderança',
     'aka': 'Sigla', 'also': 'Também aparece em', 'cat': 'Categoria'}

def wiki_detail(f3):
    """linha da wiki: [nome, categoria, campo1, campo2, campo3, outros jogos]; f3 = rótulos dos 3 campos (como o WK do app)"""
    def d(r):
        out = [[L['cat'], r[1]]]
        for lab, v in zip(f3, r[2:5]):
            if lab and v: out.append([L[lab], v])
        if len(r) > 5 and r[5]: out.append([L['also'], ', '.join(r[5])])
        return out
    return d

def mission_detail(chapters):
    def d(r):
        o = [['Tipo', 'Principal' if r[2] == 'story' else 'Side mission'], ['Capítulo', '%s · %s' % (r[3], chapters.get(str(r[3]), '')) if r[3] else ''],
             ['Ordem', r[4]], ['Protagonistas', ', '.join(r[5] or [])], ['Quem dá', r[6]], ['Lugares', ', '.join(r[7] or [])],
             ['Vem depois de', ', '.join(r[8] or [])], ['Libera', ', '.join(r[9] or [])], ['Objetivos', r[10]], ['Fontes', ', '.join(r[13] or [])], ['Situação do dado', r[14]]]
        return [x for x in o if x[1] not in ('', None, [])]
    return d

KINDS = [  # tipo, rótulo, arquivo, global, caminho, (linha -> chave, nome, resumo), detalhe, prefixo da foto, prefixo do vídeo
    ('vehicles', 'Veículos', 'wiki.js', 'WIKI', 'vehicles', lambda r: (r[0], r[0], r[1]), wiki_detail(['body', 'maker', 'cap']), 'v', 'v'),
    ('weapons', 'Armas', 'wiki.js', 'WIKI', 'weapons', lambda r: (r[0], r[0], r[1]), wiki_detail(['fire', 'maker', '']), 'w', 'w'),
    ('characters', 'Personagens', 'wiki.js', 'WIKI', 'characters', lambda r: (r[0], r[0], r[1]), wiki_detail(['job', 'links', 'home']), 'c', None),
    ('missions', 'Missões', 'missions.js', 'MISSIONS', 'rows', lambda r: (r[0], r[1], ('Principal' if r[2] == 'story' else 'Side mission') + (' · cap. %s' % r[3] if r[3] else '')), None, None, 'm'),
    ('animals', 'Animais', 'wiki2.js', 'WIKI2', 'animals', lambda r: (r[0], r[0], r[2]), wiki_detail(['type', 'where', '']), 'a', 'a'),
    ('gangs', 'Gangues', 'wiki2.js', 'WIKI2', 'gangs', lambda r: (r[0], r[0], r[2] if len(r) > 2 else ''), wiki_detail(['type', 'leader', 'where']), 'g', None),
    ('radios', 'Rádios', 'wiki2.js', 'WIKI2', 'radios', lambda r: (r[0], r[0], r[2] if len(r) > 2 else ''), wiki_detail(['genre', 'host', 'where']), 'r', None),
    ('orgs', 'Organizações', 'wiki3.js', 'WIKI3', 'orgs', lambda r: (r[0], r[0], r[1]), wiki_detail(['type', 'where', 'aka']), 'o', None),
    ('media', 'Mídia', 'wiki3.js', 'WIKI3', 'media', lambda r: (r[0], r[0], r[1]), wiki_detail(['type', 'genre', '']), 'm', None),
    ('editions', 'Edições', 'wiki3.js', 'WIKI3', 'editions', lambda r: (r[0], r[0], r[1]), wiki_detail(['type', '', '']), 'e', None),
    ('heists', 'Assaltos (lugares)', 'heists.js', 'HEISTS', 'places', lambda r: ('%s|%s|%s|%s' % (r[0], r[1], r[5], r[6]), r[1], r[0] + (' · ' + r[2] if r[2] else '')),
        lambda r: [['Tipo', r[0]], ['Região', r[2]], ['Recompensa', ('US$ %s a %s' % (r[3], r[4])) if r[4] else ''], ['Posição no mapa', '%s, %s' % (r[5], r[6])]], None, 'h'),
    ('cheats', 'Trapaças', 'gv.js', 'GV', 'cheats', lambda r: (r[0], r[3], r[1]),
        lambda r: [['Grupo', r[1]], ['Código', r[2]], ['O que faz', r[5] or r[4]], ['Como liberar', r[7] or r[6]], ['Situação do dado', r[9] if len(r) > 9 else '']], None, None),
    ('hundred', 'Metas do 100%', 'hundred.js', 'HUNDRED', None, lambda r: (r[0] + '|' + r[1], r[3] or r[2], r[1]),
        lambda r: [['Meta', r[3] or r[2]], ['Peso no 100%', r[4]], ['Total', r[11] if len(r) > 11 else ''], ['Situação do dado', r[9]], ['Fontes', ', '.join(r[10] or [])]], None, None),
    ('places', 'Lugares do mapa', 'data.js', 'ATLAS_PLACES', None, lambda r: (r[0], r[1] or '(sem nome)', ' · '.join(x for x in (r[3], r[2]) if x)),
        lambda r: [['Rua', r[2]], ['Região', r[3]], ['Categorias', ', '.join(r[5] or [])], ['Na vida real', r[6]], ['Posição no mapa', '%s, %s' % tuple(r[4]) if r[4] else '']], 'P', None),
]
CHUNK = 450

def load(www, f):
    s = open(os.path.join(www, f), encoding='utf-8').read().strip()
    m = re.match(r'window\.(\w+)\s*=\s*', s)
    v, end = json.JSONDecoder().raw_decode(s, m.end())          # o arquivo pode ter mais comandos depois do dado
    return m.group(1), v, s[end:]

def globals_of(www, f):
    try: s = open(os.path.join(www, f), encoding='utf-8').read()
    except Exception: return {}
    out = {}
    for m in re.finditer(r'window\.(\w+)\s*=\s*', s):
        try: out[m.group(1)] = json.JSONDecoder().raw_decode(s, m.end())[0]
        except Exception: pass
    return out

def save(www, f, g, v, rest):
    open(os.path.join(www, f), 'w', encoding='utf-8').write('window.%s=%s%s' % (g, json.dumps(v, ensure_ascii=False, separators=(',', ':')), rest))

def rows_of(v, path): return v if path is None else v.get(path, [])
def doc_id(kind, key): return hashlib.sha1(('%s|%s' % (kind, key)).encode()).hexdigest()[:16]
def nk(s): return re.sub(r'[^a-z0-9]+', '', re.sub(r"'s\b", '', str(s).lower()))

def read_hidden(path):
    if not path or not os.path.exists(path): return {}
    H = json.load(open(path))
    return {k: (v if isinstance(v, dict) else {x: [x, ''] for x in v}) for k, v in H.items() if v}

def photo_map(www):
    """chave -> todas as fotos do item, na ordem em que o app escolhe a principal (personagens, gta.wiki, outras, extras da galeria)"""
    P = {}
    for f, g in (('chars.js', 'CHAR_PHOTOS'), ('ig.js', 'IGP'), ('hq.js', 'HQP')):
        for k, p in (globals_of(www, f).get(g) or {}).items():
            if p not in P.setdefault(k, []): P[k].append(p)
    for k, ps in (globals_of(www, 'ig_more.js').get('IGPX') or {}).items():
        for p in ps:
            if p not in P.setdefault(k, []): P[k].append(p)
    return P, set(globals_of(www, 'photos.js').get('PLACE_PHOTOS', []))

def build_sprites(www, out, paths):
    """folhas de 80 miniaturas (10 x 8, 200 x 134 px) com tools/sprite.swift; devolve {caminho: [folha, posição]}"""
    sp = os.path.join(out, 'sprites'); os.makedirs(sp, exist_ok=True)
    binp = os.path.join(out, 'sprite-bin')
    if not os.path.exists(binp):
        subprocess.run(['swiftc', '-O', os.path.join(HERE, 'sprite.swift'), '-o', binp], check=True)
    paths = [p for p in paths if os.path.exists(os.path.join(www, p))]
    ref = {}
    for i in range(0, len(paths), 80):
        part = paths[i:i + 80]; n = i // 80
        subprocess.run([binp, os.path.join(sp, 's%d.jpg' % n), '10', '200', '134'] + [os.path.join(www, p) for p in part], check=True, capture_output=True)
        for j, p in enumerate(part): ref[p] = [n, j]
    return ref

def catalog(www, out, hidden_path='', videos_path='', cand_path=''):
    os.makedirs(os.path.join(out, 'catalog'), exist_ok=True)
    HID = read_hidden(hidden_path)
    VID = json.load(open(videos_path)).get('items', {}) if videos_path and os.path.exists(videos_path) else {}
    PH, PLACEPH = photo_map(www)
    chapters = {}
    try: chapters = load(www, 'missions.js')[1].get('chapters', {})
    except Exception: pass
    kinds, index = {}, []
    for kind, label, f, g, path, fn, det, phx, vx in KINDS:
        try: _, v, _ = load(www, f)
        except Exception as e: print('  sem', f, e); continue
        det = det or mission_detail(chapters)
        rows = []
        for r in rows_of(v, path):
            try: k, n, sub = fn(r)
            except Exception: continue
            if not n or re.match(r'\s*Unnamed\b', str(n)): continue
            try: d = [[a, str(b)[:300]] for a, b in det(r) if b not in ('', None)]
            except Exception: d = []
            phs = []
            if phx == 'P': phs = ['ph/%s.jpg' % k] if k in PLACEPH else []
            elif phx: phs = PH.get('%s:%s' % (phx, n), [])
            elif kind == 'missions': phs = PH.get('ms:' + k, [])
            ph = phs[0] if phs else ''
            vid = VID.get(('m:' + k) if vx == 'm' else ('%s:%s' % (vx, nk(n))) if vx else '', None)
            rows.append({'k': str(k), 'n': str(n), 's': str(sub or '')[:60], 'id': doc_id(kind, k), 'st': 'app', 'd': d, 'ph': ph, 'phs': phs,
                         'pk': ('%s:%s' % (phx, n)) if phx and phx != 'P' else ('ms:' + k if kind == 'missions' else ''),
                         'v': {'t': vid['title'], 'c': vid['channel'], 'u': vid['url']} if vid else None})
        have = {r['k'] for r in rows}
        for k, (n, sub) in HID.get(kind, {}).items():          # já fora do app: some dos .js, continua aqui para poder voltar
            if k not in have: rows.append({'k': k, 'n': n, 's': (sub or '')[:60], 'id': doc_id(kind, k), 'st': 'app', 'd': [], 'ph': '', 'v': None})
        kinds[kind] = (label, rows)
    # guardado na base, mas não sobe para o app
    try:
        E = load(www, 'eggs.js')[1]['eggs']
        kinds['eggs'] = ('Easter eggs (guardados)', [{'k': e['id'], 'n': e['name'], 's': e.get('region', '')[:60], 'id': doc_id('eggs', e['id']), 'st': 'stored',
            'd': [[a, str(e.get(b))] for a, b in (('Tipo', 'kind'), ('Região', 'region'), ('Lugar', 'place'), ('Como achar', 'how'), ('Confirmação', 'conf'), ('Nota', 'note')) if e.get(b)],
            'ph': '', 'v': (lambda x: {'t': x['title'], 'c': x['channel'], 'u': x['url']} if x else None)(VID.get('e:' + e['id']))} for e in E])
    except Exception as e: print('  sem eggs', e)
    if cand_path and os.path.exists(cand_path):
        GN = {'strangers': 'Side missions', 'guns': 'Loja de armas', 'drones': 'Corrida de drone', 'cards': 'Carta colecionável', 'playlists': 'Unique Playlist',
              'vehicles': 'Veículo', 'places': 'Lugar', 'areas': 'Contorno de região', 'smash': "Smash 'n' Grab", 'payday': 'Payday Loans'}
        pts = [p for p in json.load(open(cand_path))['points'] if not p['on_map']]
        kinds['mappoints'] = ('Pontos da gta.wiki (não desenhados)', [{'k': p['id'], 'n': p['label'], 's': GN.get(p['group'], p['group']), 'id': doc_id('mappoints', p['id']), 'st': 'stored',
            'd': [['Camada', GN.get(p['group'], p['group'])], ['Seção da página', p['section']], ['Posição no mapa', '%s, %s' % (round(p['x']), round(p['y']))],
                  ['Fonte', 'gta.wiki: ' + p['page']], ['Visto pela primeira vez', p['first_seen']]], 'ph': '', 'v': None, 'url': p['url']} for p in pts])
    # fotos em folhas de miniaturas (todas as fotos de cada item, não só a principal)
    paths = sorted({p for _, rows in kinds.values() for r in rows for p in (r.get('phs') or ([r['ph']] if r['ph'] else []))})
    ref = build_sprites(www, out, paths)
    used = {}
    for _, rows in kinds.values():
        for r in rows:
            for p in r.get('phs') or []: used.setdefault(p, set()).add(r['id'])
    for _, rows in kinds.values():
        for r in rows:
            r['ph'] = ref.get(r['ph'], '') if r['ph'] else ''
            if len(r.get('phs') or []) > 1: r['phx'] = [[ref.get(p, ''), p] for p in r['phs']]     # várias fotos: o dono escolhe a principal
            if any(len(used.get(p, ())) > 1 for p in r.get('phs') or []): r['dup'] = 1               # a mesma foto em outro item
            r.pop('phs', None)
    for kind, (label, rows) in kinds.items():
        parts = [rows[i:i + CHUNK] for i in range(0, len(rows), CHUNK)] or [[]]
        for i, part in enumerate(parts):
            json.dump({'kind': kind, 'label': label, 'part': i, 'parts': len(parts), 'rows': part},
                      open(os.path.join(out, 'catalog', '%s-%d.json' % (kind, i)), 'w'), ensure_ascii=False, separators=(',', ':'))
        index.append({'kind': kind, 'label': label, 'n': len(rows), 'parts': len(parts), 'photos': sum(1 for r in rows if r['ph']),
                      'videos': sum(1 for r in rows if r['v']), 'stored': sum(1 for r in rows if r['st'] == 'stored')})
        print('  %-11s %5d itens · %4d fotos · %3d vídeos · %d parte(s)' % (kind, len(rows), index[-1]['photos'], index[-1]['videos'], len(parts)))
    json.dump({'kinds': index, 'sheets': len({v[0] for v in ref.values()})}, open(os.path.join(out, 'catalog', 'index.json'), 'w'), ensure_ascii=False)

def apply(www, hidden_path):
    H = {k: set(v) for k, v in read_hidden(hidden_path).items()}
    if not H: print('nada fora do app'); return
    by_file = {}
    for kind, label, f, g, path, fn, det, phx, vx in KINDS:
        if kind in H: by_file.setdefault(f, []).append((kind, path, fn))
    for f, specs in by_file.items():
        g, v, rest = load(www, f)
        for kind, path, fn in specs:
            rows = rows_of(v, path)
            keep = [r for r in rows if str(fn(r)[0]) not in H[kind]]
            print('  %-11s %d fora do app' % (kind, len(rows) - len(keep)))
            if path is None: v = keep
            else: v[path] = keep
        save(www, f, g, v, rest)

if __name__ == '__main__':
    a = sys.argv
    if a[1] == 'catalog': catalog(a[2], a[3], *(a[4:7] + [''] * (3 - len(a[4:7]))))
    elif a[1] == 'apply': apply(a[2], a[3])
    else: raise SystemExit(__doc__)
