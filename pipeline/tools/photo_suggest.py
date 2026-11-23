#!/usr/bin/env python3
"""Fotos sugeridas, todo dia, para o dono aprovar na página Aprovações (pedido de 23/11/2026: "sempre sugestões de mais fotos").
usage: photo_suggest.py <app/www> <state dir> <out photo_suggest.json> [itens_por_dia]

A coleta antiga (gtawiki_images.py + gtawiki_fetch.py) põe UMA foto por item sozinha. Aqui vêm as que faltam:
  1) itens SEM foto (veículos, armas, personagens, animais, rádios, gangues, organizações, mídia, missões, lugares do assalto);
  2) MAIS FOTOS para itens que têm só uma (galeria).
Mesmo filtro da coleta antiga: só arquivo com GTAVI/GTA6 no nome (tela do jogo, frame de trailer, render), nada de logo, mapa,
pôster, arte de fã, foto real ou de outro GTA; largura >= 640 px. Até 3 candidatas por item, nunca a mesma sugestão duas vezes.
Estado: <state>/photo_suggest_seen.json (arquivos já sugeridos)."""
import sys, os, re, json, time, datetime, urllib.request, urllib.parse

WWW, STATE, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
PER_DAY = int(sys.argv[4]) if len(sys.argv) > 4 else 40
TODAY = datetime.date.today().isoformat()
UA = {'User-Agent': 'LeonidaCompanionPrototype/0.1 (fan app prototype; generic-client)'}
BAD = re.compile(r'logo|icon|badge|map|poster|cover|box|art\b|artwork|fanart|concept|texture|sprite|signature|-GTAV[^I]|-GTAIV|-GTAO|-GTAOee|-GTAVee|real|stock', re.I)
GOOD = re.compile(r'GTAVI|GTA6', re.I)
KIND_BONUS = (('FrontQuarter', 30), ('Front', 12), ('Portrait', 30), ('Screenshot', 10), ('AnExtendedLook', 8), ('Trailer', 6), ('Render', 12), ('Model', 12), ('Pose', 8))

def get(**p):
    p['format'] = 'json'
    for i in range(3):
        try:
            r = json.load(urllib.request.urlopen(urllib.request.Request('https://gta.wiki/api.php?' + urllib.parse.urlencode(p), headers=UA), timeout=60))
            time.sleep(0.5); return r
        except Exception: time.sleep(3)
    raise SystemExit('gta.wiki fora do ar')

def globals_of(f):
    try: s = open(os.path.join(WWW, f), encoding='utf-8').read()
    except Exception: return {}
    out = {}
    for m in re.finditer(r'window\.(\w+)\s*=\s*', s):
        try: out[m.group(1)] = json.JSONDecoder().raw_decode(s, m.end())[0]
        except Exception: pass
    return out

def items():
    """(tipo, chave da foto no app, título da página na gta.wiki, nome mostrado)"""
    W, W2, W3 = globals_of('wiki.js').get('WIKI', {}), globals_of('wiki2.js').get('WIKI2', {}), globals_of('wiki3.js').get('WIKI3', {})
    out = []
    for k, p in (('vehicles', 'v'), ('weapons', 'w'), ('characters', 'c')):
        out += [(k, p + ':' + r[0], r[0], r[0]) for r in W.get(k, [])]
    for k, p in (('animals', 'a'), ('radios', 'r'), ('gangs', 'g')):
        out += [(k, p + ':' + r[0], r[0], r[0]) for r in W2.get(k, [])]
    for k, p in (('orgs', 'o'), ('media', 'm'), ('editions', 'e')):
        out += [(k, p + ':' + r[0], r[0], r[0]) for r in W3.get(k, [])]
    for r in globals_of('missions.js').get('MISSIONS', {}).get('rows', []):
        out.append(('missions', 'ms:' + r[0], r[1], r[1]))
    for r in globals_of('heists.js').get('HEISTS', {}).get('places', []):
        out.append(('heists', 'h:' + r[1], r[1], r[1]))
    return [x for x in out if x[2] and not re.match(r'\s*Unnamed\b', x[2])]

def photos_now():
    """quantas fotos cada item já tem no app"""
    have = {}
    for f in ('ig.js', 'hq.js', 'chars.js'):
        for g, v in globals_of(f).items():
            if isinstance(v, dict):
                for k in v: have[k] = have.get(k, 0) + 1
    return have

def main():
    os.makedirs(STATE, exist_ok=True)
    sf = os.path.join(STATE, 'photo_suggest_seen.json')
    seen = json.load(open(sf)) if os.path.exists(sf) else {}
    IT, HAVE = items(), photos_now()
    order = {'missions': 0, 'vehicles': 1, 'characters': 2, 'weapons': 3, 'animals': 4, 'heists': 5, 'orgs': 6, 'gangs': 7, 'radios': 8, 'media': 9, 'editions': 10}
    IT = [x for x in IT if HAVE.get(x[1], 0) < 2]
    rank = {}
    for x in sorted(IT, key=lambda x: order.get(x[0], 9)):                      # alterna os tipos: 1 missão, 1 veículo, 1 personagem...
        rank[x[1]] = sum(1 for y in rank if y.split(':')[0] == x[1].split(':')[0])
    IT.sort(key=lambda x: (min(HAVE.get(x[1], 0), 2), rank[x[1]], order.get(x[0], 9)))   # sem foto primeiro; depois quem tem só uma
    out, i = [], 0
    while len(out) < PER_DAY and i < len(IT):
        chunk = IT[i:i + 25]; i += 25
        names = {}
        cont = {}
        while True:
            d = get(action='query', prop='images', imlimit='500', titles='|'.join(sorted({c[2] for c in chunk})), redirects='1', **cont)
            red = {r['to']: r['from'] for r in d['query'].get('redirects', [])}
            for p in d['query']['pages'].values():
                for im in p.get('images', []): names.setdefault(red.get(p['title'], p['title']), []).append(im['title'][5:])
            if 'continue' in d: cont = {'imcontinue': d['continue']['imcontinue']}
            else: break
        files = sorted({n for v in names.values() for n in v if GOOD.search(n) and not BAD.search(n) and re.search(r'\.(png|jpe?g)$', n, re.I)
                        and n.replace(' ', '_') not in seen})
        info = {}
        for j in range(0, len(files), 40):
            d = get(action='query', prop='imageinfo', iiprop='url|size', iiurlwidth='320', titles='|'.join('File:' + f for f in files[j:j + 40]))
            for p in d['query']['pages'].values():
                ii = (p.get('imageinfo') or [{}])[0]
                if ii.get('url'): info[p['title'][5:].replace(' ', '_')] = ii
        for kind, key, title, name in chunk:
            cl = []
            for n in names.get(title, []):
                if n.replace(' ', '_') in seen: continue                        # a mesma foto não vai para dois itens
                u = info.get(n.replace(' ', '_'))
                if not u or u.get('width', 0) < 640: continue
                sc = min(u['width'], 2000) / 20 + sum(b for kk, b in KIND_BONUS if kk.lower() in n.lower())
                cl.append({'file': n.replace(' ', '_'), 'url': u['url'], 'thumb': u.get('thumburl') or u['url'], 'w': u['width'], 'h': u['height'],
                           'page': 'https://gta.wiki/wiki/File:' + urllib.parse.quote(n.replace(' ', '_')), 'score': round(sc, 1)})
            cl.sort(key=lambda x: -x['score'])
            if not cl: continue
            out.append({'kind': kind, 'key': key, 'title': title, 'name': name, 'has': HAVE.get(key, 0), 'cands': cl[:3]})
            for c in cl[:3]: seen[c['file']] = TODAY
            if len(out) >= PER_DAY: break
    json.dump(seen, open(sf, 'w'), indent=0)
    json.dump({'ts': TODAY, 'items': out}, open(OUT, 'w'), ensure_ascii=False, indent=1)
    from collections import Counter
    print('fotos sugeridas: %d itens (%d sem foto, %d com uma)' % (len(out), sum(1 for x in out if not x['has']), sum(1 for x in out if x['has'])),
          dict(Counter(x['kind'] for x in out)))

if __name__ == '__main__':
    main()
