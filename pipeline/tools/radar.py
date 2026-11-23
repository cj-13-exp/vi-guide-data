#!/usr/bin/env python3
"""Radar de pistas: o que os sites de jogos publicaram hoje sobre GTA VI e que o app ainda não tem.
usage: radar.py <app/www> <state dir> <out radar.json>

Fontes (só canais feitos para máquina, sem driblar bloqueio de site):
  - Google Notícias (RSS de busca): reúne Insider Gaming, IGN, Game Rant, Push Square, Sportskeeda, theclick.gg,
    Overgear, VGTimes, endgametools, Map Genie, Polygon, Kotaku e outros, inclusive os que barram robôs.
  - RSS próprio dos sites que oferecem (Push Square, Sportskeeda, Game Rant, Insider Gaming).
Cada manchete vira um ASSUNTO ("Kraken", "Pegassi Tempesta", "Tommy Vercetti outfit") com um TEMA (easter egg, veículo,
colecionável...). Assuntos repetidos em vários sites somam fontes. O radar marca se o app já tem o assunto (busca o nome
em todos os dados do app). Nada aqui entra no app: vira pista para a tela de aprovação do dono.
Estado em <state>/radar_seen.json (primeira vez que cada assunto apareceu)."""
import sys, os, re, json, html, time, hashlib, datetime, urllib.request, urllib.parse, email.utils

WWW, STATE, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
UA = {'User-Agent': 'Mozilla/5.0 (compatible; generic-client/1.0)'}
TODAY = datetime.date.today().isoformat()
KEEP_DAYS = 45                                   # pista sem notícia nova há 45 dias sai do radar

def gnews(q, lang='en'):
    hl, gl, ceid = {'en': ('en-US', 'US', 'US:en'), 'pt': ('pt-BR', 'BR', 'BR:pt-419'), 'es': ('es-419', 'MX', 'MX:es-419')}[lang]
    return 'https://news.google.com/rss/search?' + urllib.parse.urlencode({'q': q + ' when:7d', 'hl': hl, 'gl': gl, 'ceid': ceid})

G6 = '("GTA 6" OR "GTA VI")'
FEEDS = [gnews(G6 + ' "easter egg"'), gnews(G6 + ' "where to find"'), gnews(G6 + ' "how to find"'),
         gnews(G6 + ' locations'), gnews(G6 + ' collectibles'), gnews(G6 + ' secret OR hidden'),
         gnews(G6 + ' "how to unlock" OR "how to get"'), gnews(G6 + ' map POI OR "points of interest"'),
         gnews(G6 + ' side mission OR "strangers" OR questline'), gnews(G6 + ' rare car OR vehicle location'),
         gnews('GTA 6 site:theclick.gg'), gnews('GTA 6 site:overgear.com'), gnews('GTA 6 site:vgtimes.com'),
         gnews('GTA 6 site:endgametools.com'), gnews('GTA 6 site:mapgenie.io'), gnews('GTA 6 site:pushsquare.com'),
         gnews('GTA 6 site:sportskeeda.com'), gnews('GTA 6 site:gamerant.com'), gnews('GTA 6 site:insider-gaming.com'),
         gnews('"GTA 6" easter egg OR segredo OR "onde encontrar"', 'pt'), gnews('"GTA 6" easter egg OR secreto OR "dónde encontrar"', 'es'),
         'https://www.pushsquare.com/feeds/latest', 'https://www.sportskeeda.com/feed/gta',
         'https://gamerant.com/feed/', 'https://insider-gaming.com/feed/']
# mais sites, pela busca do Google Notícias (cobre também os que barram robôs)
MORE_SITES = ['ign.com', 'gamespot.com', 'polygon.com', 'kotaku.com', 'pcgamer.com', 'gamesradar.com', 'eurogamer.net', 'thegamer.com',
              'screenrant.com', 'dualshockers.com', 'mobalytics.gg', 'rockpapershotgun.com', 'vg247.com', 'videogameschronicle.com',
              'powerpyx.com', 'gamingbible.com', 'escorenews.com', 'keengamer.com']
FEEDS += [gnews('GTA 6 site:' + s) for s in MORE_SITES]
FEEDS += [gnews('"GTA 6" site:' + s, 'pt') for s in ('br.ign.com', 'tecmundo.com.br', 'theenemy.com.br', 'adrenaline.com.br', 'gameblast.com.br', 'voxel.com.br')]
FEEDS += [gnews('"GTA 6" site:' + s, 'es') for s in ('3djuegos.com', 'vandal.elespanol.com', 'as.com', 'hobbyconsolas.com')]

# vídeos: feed público de cada canal (sem chave). Só canais que postam guias de GTA 6; o oficial da Rockstar primeiro.
YT = {'UC6VcWc1rAoWdBCM0JxrRQ3A': 'Rockstar Games', 'UCKy1dAqELo0zrOtPkf0eTMw': 'IGN', 'UC4LKeEyIBI7kyntQMFXTh0Q': 'IGN Guides',
      'UCbu2SsF-Or3Rsn3NxqODImw': 'GameSpot', 'UCWBA1-H9A5IldSb3tNwQmtQ': 'PowerPyx', 'UC0PMQXAwF6O6aeTpv962miA': 'MrBossFTW',
      'UCuWcjpKbIDAbZfHoru1toFg': 'GTA Series Videos', 'UC1bwliGvJogr7cWK0nT2Eag': 'MKIceAndFire', 'UCpqXJOEqGS-TCnazcHCo0rA': 'theRadBrad',
      'UCVS9tA3PI8Gard_LrTx0YsQ': 'Kotaku', 'UCGCpa--gJo5Dzi0oxNgUPrw': 'Mobalytics', 'UCk2ipH2l8RvLG0dr-rsBiZw': 'GamesRadar'}
# especialistas em LOCALIZAÇÃO (referência ideal do dono, 23/11/2026): achados pela busca do YouTube ("all locations",
# "where to find", "collectibles"). O vídeo deles vem antes dos outros quando casa com uma pista.
YT_LOC = {'UC-zjH-e5XBzMpy_VtwIGRxQ': 'Arekkz Gaming', 'UCCMZ64wccR-qFxsSG1koAeQ': 'How to Everything', 'UCRsRAdNBF14yVqRzc4TZ7Tg': 'JFL VIDEOS',
          'UCM4cg8hf_jwGPez7Gj6ZJqg': 'Imack Studios', 'UCFXmIUDNofRpYSG7lku0i_Q': 'Trophy Tom', 'UCRL1kBjkg-F5KY7vZUZgTeA': 'HarryNinetyFour',
          'UC4E3u9S6YVG5sIIJ80N-DHQ': 'EPICTREASURE', 'UClBnxUXbfpnwZjchDz52B7Q': 'Caspahz', 'UC9CRwKx1Dt7ZosyO1AR8IHw': 'Vexies',
          'UC4mW2bRHWfVUS9zT5FokISg': 'Misleading', 'UCZojkqUeuaZyAQc8KaBNrJw': 'Maka91Productions', 'UC_DgclLC9mCRVsUqi6opwnw': 'KingAlexHD',
          'UCBrY2UkXYINiBW_-Zj-jsew': 'TheGamingRevolution', 'UCmF3ZcCBFUD-mcwg-r3SMyA': 'LunarGaming', 'UC_dsjLrQY-L8rHxRS-wtpGA': 'Millzaa',
          'UCYBetkejPxK8t_41zueazcA': 'T5G', 'UCMUP9j-QidC_S0KLlO06uCg': 'MrDalekJD',
          'UCWBA1-H9A5IldSb3tNwQmtQ': 'PowerPyx', 'UCuWcjpKbIDAbZfHoru1toFg': 'GTA Series Videos'}
YT.update(YT_LOC)
VIDEO_DAYS = 120                                  # vídeo guardado por 120 dias depois de visto pela última vez

def videos(state):
    """lê os feeds dos canais e acumula em state (id -> vídeo). Só títulos de GTA 6."""
    for cid, name in YT.items():
        x = fetch('https://www.youtube.com/feeds/videos.xml?channel_id=' + cid)
        for e in re.findall(r'<entry>(.*?)</entry>', x, re.S):
            vid = (re.search(r'<yt:videoId>([\w-]{11})</yt:videoId>', e) or [None, None])[1]
            title = html.unescape((re.search(r'<title>(.*?)</title>', e, re.S) or [None, ''])[1]).strip()
            pub = (re.search(r'<published>(\d{4}-\d\d-\d\d)', e) or [None, TODAY])[1]
            if not vid or not re.search(r'GTA\s*(?:6|VI)|Grand Theft Auto\s*(?:6|VI)', title, re.I): continue
            v = state.setdefault(vid, {'id': vid, 'title': title[:160], 'channel': name, 'official': name == 'Rockstar Games',
                                       'url': 'https://www.youtube.com/watch?v=' + vid, 'published': pub, 'first_seen': TODAY})
            v['last_seen'] = TODAY; v['loc'] = cid in YT_LOC or bool(re.search(r'\b(locations?|where to find|how to find|all \d+)\b', title, re.I))
    cut = (datetime.date.today() - datetime.timedelta(days=VIDEO_DAYS)).isoformat()
    return {k: v for k, v in state.items() if v.get('last_seen', TODAY) >= cut or v.get('published', TODAY) >= cut}

def match_videos(subject, vids):
    """vídeos cujo título contém o assunto (mesma normalização das pistas)"""
    k = norm_app(subject)
    if len(k) < 5: return []
    hit = [v for v in vids.values() if k in norm_app(v['title'])]
    hit.sort(key=lambda v: v['published'], reverse=True)                     # mais novo primeiro...
    hit.sort(key=lambda v: (not v['official'], not v.get('loc')))            # ...mas oficial e especialista em local na frente
    return hit[:4]

def fetch(url):
    if 'news.google.com' in url: time.sleep(2.5)          # educado com o Google: uma busca a cada 2,5 s (evita o 429)
    try:
        return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40).read().decode('utf-8', 'replace')
    except Exception as e:
        print('  falhou', url[:90], '-', e); return ''

def items(xml):
    for it in re.findall(r'<item>(.*?)</item>', xml, re.S):
        g = lambda t: (re.search(r'<%s[^>]*>(.*?)</%s>' % (t, t), it, re.S) or [None, ''])[1]
        title = html.unescape(re.sub(r'<!\[CDATA\[|\]\]>', '', g('title'))).strip()
        link = html.unescape(re.sub(r'<!\[CDATA\[|\]\]>', '', g('link'))).strip()
        src = html.unescape(g('source')).strip()
        date = g('pubDate').strip()
        if not src:
            src = re.sub(r'^www\.', '', urllib.parse.urlparse(link).netloc)
        else:
            title = re.sub(r'\s+-\s+' + re.escape(src) + r'$', '', title)    # Google Notícias põe " - Site" no fim
        try: d = email.utils.parsedate_to_datetime(date).date().isoformat()
        except Exception: d = TODAY
        yield title, link, src, d

# ---- assunto e tema de uma manchete ------------------------------------------------------------------------------
GTA = r'(?:in\s+)?(?:GTA\s*(?:6|VI)|Grand Theft Auto\s*(?:6|VI))'
PATTERNS = [
    r'where to find (?:the |a |an |all )?(?P<s>.+?)(?:\s+' + GTA + r'|$)',
    r'how to (?:find|get|unlock|complete|start|catch|beat|reach|visit|do) (?:the |a |an |all )?(?P<s>.+?)(?:\s+' + GTA + r'|$)',
    r'(?:all|every) (?P<s>.+?) locations?',
    r'(?P<s>.+?) (?:easter egg|location|locations) (?:explained|guide)',
    r'onde encontrar (?:o |a |os |as )?(?P<s>.+?)(?:\s+(?:no|em) GTA|$)',
    r'dónde encontrar (?:el |la |los |las )?(?P<s>.+?)(?:\s+en GTA|$)',
]
TOPICS = [('veiculo', r'\b(car|cars|vehicle|bike|motorcycle|boat|plane|helicopter|jet ?ski|supercar|randy|moses|wishlist|pegassi|grotti|bravado|truffade|pfister|invetero|ocelot|dinka|maibatsu|declasse|vapid|benefactor|ubermacht|buckingham|annis|karin)\b'),
          ('colecionavel', r'\b(collectibles?|cards?|magazines?|murals?|signal jammers?|letter scraps?|spaceship parts?|peyote|figurines?|books?|playlists?|souvenirs?)\b'),
          ('easter_egg', r'\b(easter eggs?|reference|references|secret|hidden|mystery|ufo|alien|bigfoot|skunk ape|kraken|ghost|cult)\b'),
          ('missao', r'\b(missions?|questline|quest|side ?quest|strangers|freaks|heist|manhunt|walkthrough|ending)\b'),
          ('atividade', r'\b(fishing|race|racing|stunt jumps?|base jump|golf|arcade|gym|hunting|activities|minigames?|drones?|basketball)\b'),
          ('arma', r'\b(weapons?|guns?|rifle|pistol|shotgun|knife|sniper)\b'),
          ('roupa', r'\b(outfits?|shirt|hat|clothes|clothing|tattoos?|haircuts?)\b'),
          ('animal', r'\b(animals?|alligators?|gators?|dogs?|crabs?|panther|wildlife|flamingos?)\b'),
          ('lugar', r'\b(map|locations?|poi|points of interest|island|building|resort|warehouse|interior|apartment|house|beach|bar|club)\b')]
NOISE = r'\b(review|reviews|sales|sold|price|patch|update|pc version|pc port|trailer|stock|delay|release date|preorder|pre-order|leak|leaks|leaked|lawsuit|layoffs?|take-two|strauss|gta online|gta 7|gta 5|gta v\b|ps5 pro|xbox series|switch 2|metacritic|score|interview|actor|actress|voice actor|cast|soundtrack|tracklist|refund|bug|glitch|crash|performance|fps|best settings)'
SKIP_SUBJ = {'gta 6', 'gta vi', 'everything', 'it', 'them', 'more', 'money', 'fast money', 'cash', 'secrets', 'easter eggs', 'all easter eggs', 'collectibles', 'all collectibles'}

LEAD = r"^(?:(?:has|have|had|is|are|this|that|these|the|a|an|its|it's|gta\s*(?:6|vi)(?:'s)?|amazing|hidden|legendary|terrifying|wild|new|best|brilliant|hilarious|secret|incredible|little|huge|real|super|official|first|another|one|some|players?|fans?)\s+)+"
TAIL = r"\s+(?:easter eggs?|reference|references|secret|location|locations|explained|guide)$"
def clean_subj(s):
    s = re.sub(r"\s+(?:in|on|at|for|and|to|with)$", '', s.strip(" .,!?'\""), flags=re.I)
    s = re.sub(r'\s+' + GTA + r'.*$', '', s, flags=re.I).strip()
    for _ in range(2):
        s = re.sub(LEAD, '', s, flags=re.I).strip()
        s = re.sub(TAIL, '', s, flags=re.I).strip()
    return s

def subject(title):
    t = re.sub(r'[‘’]', "'", re.sub(r'[—–|:]', ' — ', title))
    for part in [t] + [p for p in t.split(' — ') if p.strip()]:
        for pat in PATTERNS:
            m = re.search(pat, part, re.I)
            if m:
                s = clean_subj(m.group('s'))
                if 2 < len(s) < 60 and s.lower() not in SKIP_SUBJ: return s
    m = re.search(r"(?P<s>[A-Z][\w'&.-]*(?:\s+[A-Z0-9][\w'&.-]*){0,4})\s+(?:Easter Egg|easter egg|Reference|reference)", t)
    if m:
        s = clean_subj(m.group('s'))
        if len(s) > 2 and not re.match(r'(?:GTA|Best|Top|Every|All|\d+)\b', s): return s
    return ''

def topic(text):
    for name, rx in TOPICS:
        if re.search(rx, text, re.I): return name
    return 'outro'

def norm_app(s):
    """mais agressiva, só para saber se o app já tem o assunto ("Hometown Heroes side mission" = missão Hometown Heroes)"""
    s = re.sub(r"'s\b", '', s.lower())
    s = re.sub(r'\([^)]*\)?', ' ', s)
    s = re.sub(r'\b(the|a|an|gta|6|vi|easter egg|easter eggs|location|locations|secret|hidden|supercar|car|cars|vehicle|standout|outfit|all|every|side|main|mission|missions|quest)\b', ' ', s)
    return re.sub(r'[^a-z0-9]+', '', s)

def norm(s):
    """chave estável da pista (o id do cartão vem dela: não mudar, a curadoria depende)"""
    s = re.sub(r"'s\b", '', s.lower())
    s = re.sub(r'\b(the|a|an|gta|6|vi|easter egg|easter eggs|location|locations|secret|hidden|supercar|car|vehicle|outfit|all|every)\b', ' ', s)
    return re.sub(r'[^a-z0-9]+', '', s)

# ---- o que o app já tem ---------------------------------------------------------------------------------------------
def app_names():
    blob = []
    for f in os.listdir(WWW):
        if f.endswith('.js') and f not in ('analytics.js', 'datasync.js', 'native.js', 'dataver.js'):
            try: blob.append(open(os.path.join(WWW, f), encoding='utf-8').read())
            except Exception: pass
    return re.sub(r'[^a-z0-9]+', '', ' '.join(blob).lower().replace("'s", ''))

def main():
    os.makedirs(STATE, exist_ok=True)
    seenf = os.path.join(STATE, 'radar_seen.json')
    seen = json.load(open(seenf)) if os.path.exists(seenf) else {}
    have = app_names()
    leads = {}
    for url in FEEDS:
        xml = fetch(url)
        for title, link, src, d in items(xml):
            if not re.search(r'GTA\s*(?:6|VI)|Grand Theft Auto\s*(?:6|VI)', title, re.I): continue
            if re.search(NOISE, title, re.I): continue
            s = subject(title)
            if not s: continue
            k = norm(s)
            if len(k) < 3: continue
            L = leads.setdefault(k, {'subject': s, 'sources': {}, 'text': ''})
            L['text'] += ' ' + title
            L['sources'].setdefault(src, {'site': src, 'title': title[:160], 'url': link, 'date': d})
    vidf = os.path.join(STATE, 'radar_videos.json')
    vids = videos(json.load(open(vidf)) if os.path.exists(vidf) else {})
    json.dump(vids, open(vidf, 'w'), ensure_ascii=False, indent=0)
    week = (datetime.date.today() - datetime.timedelta(days=7)).isoformat()
    for v in vids.values():                         # título de vídeo também é pista ("All 18 Delights Card Locations")
        if v['published'] < week or re.search(NOISE, v['title'], re.I): continue
        s = subject(v['title'])
        if not s: continue
        k = norm(s)
        if len(k) < 3: continue
        L = leads.setdefault(k, {'subject': s, 'sources': {}, 'text': ''})
        L['text'] += ' ' + v['title']
        L['sources'].setdefault('YouTube · ' + v['channel'], {'site': 'YouTube · ' + v['channel'], 'title': v['title'], 'url': v['url'], 'date': v['published']})
    out = []
    for k, L in leads.items():
        first = seen.get(k, {}).get('first', TODAY)
        last = max(x['date'] for x in L['sources'].values())
        seen[k] = {'first': first, 'last': max(last, seen.get(k, {}).get('last', last)), 'subject': L['subject']}
        out.append({'id': hashlib.sha1(k.encode()).hexdigest()[:10], 'key': k, 'subject': L['subject'],
                    'topic': topic(L['subject'] + ' ' + L['text']), 'first_seen': first, 'last_seen': seen[k]['last'],
                    'n_sources': len(L['sources']), 'in_app': k in have or (len(norm_app(L['subject'])) >= 6 and norm_app(L['subject']) in have),
                    'sources': sorted(L['sources'].values(), key=lambda x: x['date'], reverse=True)[:6],
                    'videos': [{'title': v['title'], 'channel': v['channel'], 'url': v['url'], 'official': v['official'], 'loc': v.get('loc', False)} for v in match_videos(L['subject'], vids)]})
    cut = (datetime.date.today() - datetime.timedelta(days=KEEP_DAYS)).isoformat()
    seen = {k: v for k, v in seen.items() if v.get('last', TODAY) >= cut}
    out.sort(key=lambda x: (x['in_app'], -x['n_sources'], x['first_seen']), reverse=False)
    json.dump(seen, open(seenf, 'w'), ensure_ascii=False, indent=0)
    new = [x for x in out if not x['in_app']]
    json.dump({'ts': datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'), 'n': len(out), 'n_new': len(new), 'leads': out,
               'videos': sorted(vids.values(), key=lambda v: v['published'], reverse=True)},
              open(OUT, 'w'), ensure_ascii=False, indent=1)
    print('radar: %d assuntos, %d que o app ainda não tem, %d vídeos de GTA 6 (%d com pista)' % (
        len(out), len(new), len(vids), sum(1 for x in out if x['videos'])))
    for x in new[:25]: print('  [%s] %s (%d fontes)' % (x['topic'], x['subject'], x['n_sources']))

if __name__ == '__main__':
    main()
