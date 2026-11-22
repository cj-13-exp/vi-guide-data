#!/usr/bin/env python3
"""Revisão diária de TODAS as seções: confere o app contra as fontes e avisa quando surge algo novo.
uso: sections_watch.py <app/www> <work dir> <state dir>
Fonte: gta.wiki (API aberta, nome de cliente genérico, 0,6 s entre pedidos). Só fatos; nada é copiado.
O que faz:
 1. lista TODAS as categorias da wiki sobre GTA VI e compara com tools/sections_registry.json; categoria fora do registro = SEÇÃO NOVA;
 2. para cada seção coberta, lista o que a wiki tem e o app não tem (foi assim que os Kingfishers ficaram de fora); gangues = infobox type gang/mc;
 3. páginas novas nas categorias vigiadas (Gameplay, Itens, Mídia...) desde o último dia;
 4. páginas vigiadas que passam a existir (Gang Operations, Bank Jobs, Collectibles...) ou mudam (Easter Eggs, Smash 'n' Grabs...);
 5. contagem por categoria (crescimento).
Saída: <work>/revisao-diaria.md (resumo em português), <work>/sections_report.json, estado novo em <state>/sections_prev.json.
Regras que valem para o que aparecer (ver CLAUDE.md e .claude/agents/revisao-diaria.md): só fatos e texto nosso, nada 'Unnamed', foto só de dentro do jogo e sem repetição, nada novo no mapa sem perguntar ao dono."""
import sys, os, re, json, time, datetime, urllib.request, urllib.parse
APP, WORK, STATE = sys.argv[1], sys.argv[2], sys.argv[3]
HERE = os.path.dirname(os.path.abspath(__file__))
REG = json.load(open(HERE + '/sections_registry.json', encoding='utf-8'))
UA = {'User-Agent': 'LeonidaCompanionPrototype/0.1 (fan app prototype; generic-client)'}
def get(**p):
    p['format'] = 'json'
    for i in range(3):
        try:
            r = json.load(urllib.request.urlopen(urllib.request.Request('https://gta.wiki/api.php?' + urllib.parse.urlencode(p), headers=UA), timeout=60)); time.sleep(0.6); return r
        except Exception: time.sleep(3)
    raise SystemExit('gta.wiki not reachable')
dec = json.JSONDecoder()
def jsvar(f, var):
    t = open(APP + '/' + f, encoding='utf-8').read(); i = t.index(var + '=') + len(var) + 1
    return dec.raw_decode(t, i)[0]
W, W2, W3 = jsvar('wiki.js', 'window.WIKI'), jsvar('wiki2.js', 'window.WIKI2'), jsvar('wiki3.js', 'window.WIKI3')
APPNAMES = {'wiki.vehicles': [r[0] for r in W['vehicles']], 'wiki.weapons': [r[0] for r in W['weapons']], 'wiki.characters': [r[0] for r in W['characters']],
            'wiki2.animals': [r[0] for r in W2['animals']], 'wiki2.gangs': [r[0] for r in W2['gangs']], 'wiki3.orgs': [r[0] for r in W3['orgs']]}
norm = lambda s: re.sub(r'[^a-z0-9]+', '', re.sub(r'\([^)]*\)', '', s.lower()))
today = datetime.date.today().isoformat()
try: prev = json.load(open(STATE + '/sections_prev.json', encoding='utf-8'))
except Exception: prev = {}
alerts, lines = [], []
# 1. todas as categorias sobre GTA VI
cats, cont = [], {}
while True:
    d = get(action='query', list='allcategories', aclimit='500', acprop='size', **cont)
    cats += d['query']['allcategories']
    if 'continue' in d: cont = {'accontinue': d['continue']['accontinue']}
    else: break
vi = {c['*']: c['pages'] for c in cats if re.search(r'\bGTA VI\b|Grand Theft Auto VI', c['*'])}
reg = REG['categories']
def status(n):
    if n in reg: return reg[n]['status']
    for p, s in REG['prefix_status'].items():
        if n.startswith(p): return s
    return None
new_cats = sorted(n for n in vi if status(n) is None)
for n in new_cats: alerts.append('SEÇÃO NOVA na gta.wiki: categoria "%s" (%d páginas). Decidir: virar seção, dado guardado ou ignorar, e registrar em tools/sections_registry.json.' % (n, vi[n]))
gone = sorted(n for n in reg if n not in vi)
for n in gone: lines.append('- Categoria do registro sumiu da wiki: %s (renomeada ou apagada?)' % n)
counts_prev = prev.get('counts', {})
grown = [(n, counts_prev[n], vi[n]) for n in vi if n in counts_prev and vi[n] != counts_prev[n] and status(n) in ('covered', 'partial', 'stored')]
# 2. lacunas das seções cobertas
def members(cat):
    t, cont = [], {}
    while True:
        d = get(action='query', list='categorymembers', cmtitle='Category:' + cat, cmlimit='500', cmnamespace='0', **cont)
        t += [m['title'] for m in d['query']['categorymembers']]
        if 'continue' in d: cont = {'cmcontinue': d['continue']['cmcontinue']}
        else: return t
mem = {}
gaps = {}
for cat, info in reg.items():
    if info['status'] not in ('covered', 'partial') and cat not in REG['watch_categories']: continue
    if cat not in vi: continue
    if vi[cat] > 700: continue
    mem[cat] = [t for t in members(cat) if not re.match(r'\s*Unnamed\b', t) and not re.search(r'\b(in GTA VI|Tracklist)$', t)]
for cat, info in reg.items():
    if info.get('status') != 'covered' or cat not in mem: continue
    have = {norm(x) for x in APPNAMES[info['app']]}
    miss = sorted(t for t in mem[cat] if norm(t) not in have)
    if miss: gaps[cat] = miss
# gangues: organizações com infobox type gang ou mc
orgs = mem.get('Organizations in GTA VI', [])
gang_titles, org_titles = [], []
for i in range(0, len(orgs), 40):
    d = get(action='query', prop='revisions', rvprop='content', rvslots='main', titles='|'.join(orgs[i:i + 40]), redirects='1')
    for p in d['query']['pages'].values():
        tx = ((p.get('revisions') or [{}])[0].get('slots', {}).get('main', {}) or {}).get('*', '')
        ty = re.search(r'\|\s*type\s*=\s*([^\n|]*)', tx)
        tt = ty.group(1).strip().lower() if ty else ''
        if tt in ('gang', 'mc'): gang_titles.append(p['title'].replace(' (The Families set)', ''))
        elif tt not in ('band', 'artist', 'b', 'd') and not re.match(r'\s*Unnamed\b', p['title']): org_titles.append(p['title'])
have = {norm(x) for x in APPNAMES['wiki2.gangs']}
gmiss = sorted(t for t in gang_titles if norm(t) not in have)
if gmiss: gaps['Gangues (organizações type gang/mc)'] = gmiss
have_o = {norm(x) for x in APPNAMES['wiki3.orgs']}
omiss = sorted(t for t in org_titles if norm(t) not in have_o)
if omiss: gaps['Organizações (tudo que não é gangue nem banda)'] = omiss
for k, v in gaps.items(): alerts.append('LACUNA em "%s": a wiki tem e o app não: %s' % (k, ', '.join(v[:12]) + (' …(+%d)' % (len(v) - 12) if len(v) > 12 else '')))
# 3. páginas novas nas categorias vigiadas
seen_prev = prev.get('members', {}); newpages = {}
for cat in REG['watch_categories']:
    if cat not in mem: continue
    if cat in seen_prev:
        add = sorted(set(mem[cat]) - set(seen_prev[cat]))
        if add: newpages[cat] = add
for k, v in newpages.items(): alerts.append('PÁGINAS NOVAS em "%s": %s' % (k, ', '.join(v[:15])))
# 4. páginas vigiadas
wp = prev.get('pages', {}); pages = {}
for i in range(0, len(REG['watch_pages']), 40):
    chunk = REG['watch_pages'][i:i + 40]
    d = get(action='query', prop='revisions', rvprop='timestamp', rvslots='main', titles='|'.join(chunk), redirects='1')
    redirects = {r['from']: r['to'] for r in d['query'].get('redirects', [])}
    for p in d['query']['pages'].values():
        pages[p['title']] = None if 'missing' in p else ((p.get('revisions') or [{}])[0].get('timestamp', '') or 'x')
    for a, b in redirects.items(): pages[a] = pages.get(b)
for t, ts in sorted(pages.items()):
    before = wp.get(t, 'novo-no-registro')
    if before == 'novo-no-registro': continue
    if before is None and ts: alerts.append('PÁGINA PASSOU A EXISTIR: "%s" (fonte nova para o app). Guardar fatos; coordenadas só depois de o dono aprovar a fonte e o desenho no mapa.' % t)
    elif before and ts and before != ts and t in ("Secrets and Easter Eggs in GTA VI", "Smash 'n' Grabs", "Payday Loans", "Fences"): alerts.append('PÁGINA MUDOU: "%s" (revisão %s). Rodar o gerador correspondente e conferir.' % (t, ts[:10]))
# relatório
md = ['# Revisão diária das seções (%s)\n' % today]
md.append('**Alertas: %d.** %s\n' % (len(alerts), 'Nada novo nas fontes.' if not alerts else 'Ver abaixo; cada item precisa de uma decisão ou de uma correção.'))
for a in alerts: md.append('- ' + a)
md.append('\n## Seções da gta.wiki sobre GTA VI (%d categorias)\n\n| Categoria | Páginas | Situação |\n|---|---|---|' % len(vi))
for n in sorted(vi): md.append('| %s | %d | %s |' % (n, vi[n], status(n) or '**NOVA**'))
if grown: md.append('\n## Mudou de tamanho desde o último dia\n' + '\n'.join('- %s: %d → %d' % g for g in grown))
if lines: md.append('\n## Avisos do registro\n' + '\n'.join(lines))
md.append('\n## Páginas vigiadas\n' + '\n'.join('- %s: %s' % (t, 'existe (revisão %s)' % ts[:10] if ts else 'ainda não existe') for t, ts in sorted(pages.items())))
md.append('\n## Regras que valem para tudo o que entrar\nSó fatos e texto nosso; nenhum item "Unnamed"; foto só de dentro do jogo, sem repetição; nada novo no mapa sem perguntar ao dono; coletado / descoberto / concluído / visitado conforme o tipo; 12 idiomas.')
os.makedirs(WORK, exist_ok=True); os.makedirs(STATE, exist_ok=True)
open(WORK + '/revisao-diaria.md', 'w', encoding='utf-8').write('\n'.join(md) + '\n')
json.dump({'date': today, 'alerts': alerts, 'new_categories': new_cats, 'gaps': gaps, 'new_pages': newpages, 'pages': pages}, open(WORK + '/sections_report.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
json.dump({'date': today, 'counts': vi, 'members': {**seen_prev, **mem}, 'pages': pages}, open(STATE + '/sections_prev.json', 'w', encoding='utf-8'), ensure_ascii=False)
print('seções:', len(vi), '| alertas:', len(alerts)); [print('  -', a) for a in alerts]
