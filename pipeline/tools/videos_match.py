#!/usr/bin/env python3
"""Um vídeo de guia para cada item do app que o jogador FAZ ou ACHA (decisão do dono, 23/11/2026):
missões (passo a passo), veículos, armas, animais, easter eggs e assaltos. Personagens, gangues, organizações e rádios ficam de fora.
usage: videos_match.py <app/www> <state dir> <out item_videos.json> [buscas_por_dia]

1) Casa com os vídeos que o radar já juntou dos canais (state/radar_videos.json).
2) Para itens ainda sem vídeo, faz até N buscas por dia no YouTube (padrão 40), uma a cada 2 s, e guarda o melhor resultado
   (o título precisa citar GTA 6 e o nome do item; canal especialista em localização ou guia vem na frente).
Estado: state/item_videos_state.json (o que já foi achado ou buscado; item buscado sem sucesso só volta à fila depois de 7 dias).
O app só mostra o link (abre o YouTube); nada é baixado nem incorporado."""
import sys, os, re, json, time, datetime, urllib.request, urllib.parse

WWW, STATE, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
PER_DAY = int(sys.argv[4]) if len(sys.argv) > 4 else 40
TODAY = datetime.date.today().isoformat()
UA = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36',
      'Accept-Language': 'en-US,en;q=0.9'}
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
GOOD = {'Rockstar Games', 'PowerPyx', 'GTA Series Videos', 'How to Everything', 'JFL VIDEOS', 'Imack Studios', 'Trophy Tom', 'HarryNinetyFour',
        'EPICTREASURE', 'Arekkz Gaming', 'IGN', 'IGN Guides', 'GameSpot', 'MKIceAndFire', 'MrBossFTW', 'Caspahz', 'Vexies', 'Misleading',
        'Maka91Productions', 'KingAlexHD', 'TheGamingRevolution', 'theRadBrad'}

def js(name, var_obj=True):
    s = open(os.path.join(WWW, name), encoding='utf-8').read()
    a = s.index('{') if var_obj else s.index('[')
    b = s.rindex('}') if var_obj else s.rindex(']')
    return json.loads(s[a:b + 1])

def nk(s): return re.sub(r'[^a-z0-9]+', '', re.sub(r"'s\b", '', str(s).lower()))

def items():
    """(kind, key, name, busca) dos itens com ação no jogo"""
    out = []
    for r in js('missions.js')['rows']:
        if r[1] and not r[1].lower().startswith('unnamed'):
            out.append(('missions', 'm:' + r[0], r[1], 'GTA 6 "%s" mission walkthrough' % r[1]))
    W = js('wiki.js')
    for r in W['vehicles']: out.append(('vehicles', 'v:' + nk(r[0]), r[0], 'GTA 6 %s location' % r[0]))
    for r in W['weapons']: out.append(('weapons', 'w:' + nk(r[0]), r[0], 'GTA 6 %s location' % r[0]))
    for r in js('wiki2.js')['animals']: out.append(('animals', 'a:' + nk(r[0]), r[0], 'GTA 6 %s location' % r[0]))
    for e in js('eggs.js')['eggs']:
        q = e.get('place') or e.get('name')
        out.append(('eggs', 'e:' + e['id'], e.get('name'), 'GTA 6 %s easter egg' % e['id'].replace('-', ' ')))
    for p in js('heists.js')['places']:
        out.append(('heists', 'h:' + nk(p[1]), p[1], 'GTA 6 %s robbery' % p[1]))
    seen, uniq = set(), []
    for x in out:
        if x[1] not in seen: seen.add(x[1]); uniq.append(x)
    return uniq

CONTEXT = {'missions': r'walkthrough|mission|missão|gold medal|guide|how to (?:complete|beat|finish|unlock)',
           'vehicles': r'locations?|where to find|how to (?:get|find|unlock)|spawn|rare|free',
           'weapons': r'locations?|where to find|how to (?:get|find|unlock)|secret|free|unique|legendary',
           'animals': r'locations?|where to find|how to (?:find|hunt|catch)|hunting|fishing|wildlife',
           'eggs': r'easter egg|secret|location|how to|mystery', 'heists': r'robbery|rob|heist|valuables|safe|smash|payday|walkthrough'}

GENERIC = {nk(x) for x in ('Pistol', 'Knife', 'Shotgun', 'Sniper Rifle', 'Grenade Launcher', 'Grenade', 'Rifle', 'Assault Rifle', 'SMG',
           'Machete', 'Bat', 'Baseball Bat', 'Hammer', 'Crowbar', 'Molotov', 'Fish', 'Birds', 'Dogs', 'Cats', 'Bus', 'Taxi', 'Boat',
           'Truck', 'Bike', 'Plane', 'Helicopter', 'Train', 'Tank', 'Minigun', 'Flare', 'Rocket Launcher', 'Dump', 'Shuttle')}

def title_ok(title, name, kind):
    """o título cita GTA 6, o NOME INTEIRO do item (palavra inteira) e um contexto de guia para aquele tipo"""
    if not re.search(r'GTA\s*(?:6|VI)|Grand Theft Auto\s*(?:6|VI)', title, re.I): return False
    n = re.sub(r'\s+', ' ', re.sub(r'[^\w\s]', ' ', str(name))).strip()
    if len(nk(n)) < 4: return False
    if kind in ('weapons', 'vehicles', 'animals') and nk(n) in GENERIC: return False   # "Pistol" casaria com "Gold Pistol"
    t = re.sub(r'\s+', ' ', re.sub(r'[^\w\s]', ' ', title.replace("'s", '')))
    words = n.split(' ')
    if not re.search(r'(?<!\w)' + r'\s+'.join(re.escape(w) for w in words) + r'(?:s|es)?(?!\w)', t, re.I): return False
    return bool(re.search(CONTEXT[kind], title, re.I))

def yt_search(q):
    u = 'https://www.youtube.com/results?' + urllib.parse.urlencode({'search_query': q})
    s = urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=30).read().decode('utf-8', 'replace')
    m = re.search(r'var ytInitialData = (\{.*?\});</script>', s)
    if not m: return []
    res = []
    def walk(o):
        if isinstance(o, dict):
            v = o.get('videoRenderer')
            if v:
                try:
                    res.append({'id': v['videoId'], 'title': ''.join(r['text'] for r in v['title']['runs'])[:160],
                                'channel': v['ownerText']['runs'][0]['text'],
                                'url': 'https://www.youtube.com/watch?v=' + v['videoId']})
                except Exception: pass
            for x in o.values(): walk(x)
        elif isinstance(o, list):
            for x in o: walk(x)
    walk(json.loads(m.group(1)))
    return res[:12]

def best(cands):
    cands.sort(key=lambda v: v['channel'] not in GOOD)
    return cands[0] if cands else None

def main():
    os.makedirs(STATE, exist_ok=True)
    stf = os.path.join(STATE, 'item_videos_state.json')
    st = json.load(open(stf)) if os.path.exists(stf) else {}
    pool = {}
    pf = os.path.join(STATE, 'radar_videos.json')
    if os.path.exists(pf): pool = json.load(open(pf))
    IT = items()
    NAME = {key: (kind, name) for kind, key, name, q in IT}
    for key in list(st):                             # regra de casamento mudou? revalida o que estava guardado
        v = st[key].get('video')
        if v and key in NAME and not title_ok(v['title'], NAME[key][1], NAME[key][0]): del st[key]
    # 1) vídeos que o radar já tem
    for kind, key, name, q in IT:
        if st.get(key, {}).get('video'): continue
        c = [{'id': v['id'], 'title': v['title'], 'channel': v['channel'], 'url': v['url']} for v in pool.values() if title_ok(v['title'], name, kind)]
        b = best(c)
        if b: st[key] = {'video': b, 'how': 'canal', 'date': TODAY}
    # 2) busca no YouTube para quem ainda não tem (missões primeiro: é onde o vídeo mais ajuda)
    order = {'missions': 0, 'eggs': 1, 'heists': 2, 'animals': 3, 'weapons': 4, 'vehicles': 5}
    retry = (datetime.date.today() - datetime.timedelta(days=7)).isoformat()
    todo = [x for x in IT if not st.get(x[1], {}).get('video') and st.get(x[1], {}).get('tried', '0') < retry]
    todo.sort(key=lambda x: order[x[0]])
    done = 0
    for kind, key, name, q in todo[:PER_DAY]:
        try: res = yt_search(q)
        except Exception as e:
            print('  busca falhou:', e); time.sleep(10); continue
        b = best([v for v in res if title_ok(v['title'], name, kind)])
        st[key] = {'video': b, 'how': 'busca', 'date': TODAY} if b else {'tried': TODAY}
        done += 1; time.sleep(2)
    json.dump(st, open(stf, 'w'), ensure_ascii=False, indent=0)
    by = {}
    for kind, key, name, q in IT:
        B = by.setdefault(kind, {'kind': kind, 'total': 0, 'with_video': 0, 'sample': []})
        B['total'] += 1
        v = st.get(key, {}).get('video')
        if v:
            B['with_video'] += 1
            if len(B['sample']) < 6: B['sample'].append({'item': name, 'title': v['title'], 'channel': v['channel'], 'url': v['url']})
    json.dump({'ts': TODAY, 'kinds': list(by.values()),
               'items': {key: st[key]['video'] for kind, key, name, q in IT if st.get(key, {}).get('video')}},
              open(OUT, 'w'), ensure_ascii=False, indent=1)
    print('vídeos por item: %d buscas hoje' % done)
    for B in by.values(): print('  %-9s %3d de %3d com vídeo' % (B['kind'], B['with_video'], B['total']))

if __name__ == '__main__':
    main()
