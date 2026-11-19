import sys,json,re,collections,time,urllib.request,urllib.parse
sys.path.insert(0,sys.argv[3])
from wiki_lib import infobox,clean
R=json.load(open(sys.argv[1]))
A="https://gta.fandom.com/api.php"
def get(params):
    params['format']='json'
    req=urllib.request.Request(A+'?'+urllib.parse.urlencode(params),headers={'User-Agent':'generic-client'})
    return json.load(urllib.request.urlopen(req,timeout=40))
# character infobox subpages
missing=[t for t,p in R['characters'].items() if not infobox(p['text'])[0]]
sub={}
if missing:
    d=get(dict(action='query',prop='revisions',rvprop='content',rvslots='main',titles='|'.join(t+'/infobox' for t in missing)))
    for p in d['query']['pages'].values():
        r=(p.get('revisions') or [{}])[0]; sub[p['title'].rsplit('/',1)[0]]=(r.get('slots',{}).get('main',{}) or {}).get('*','')
G={'O':'GTA Online','V':'GTA V','IV':'GTA IV','EFLC':'Episodes from Liberty City','TBOGT':'Episodes from Liberty City','TLAD':'Episodes from Liberty City','CW':'Chinatown Wars','SA':'San Andreas','VC':'Vice City','VCS':'Vice City Stories','LCS':'Liberty City Stories','III':'GTA III','A':'GTA Advance'}
def games(f):
    out=[]
    for k in re.findall(r'\|\s*([A-Za-z0-9]+)\s*=',f.get('games','')):
        n=G.get(k)
        if n and n not in out: out.append(n)
    return out
VG={}
for g,ts in {'Carros':'fullsize midsize sports muscle grandtourer sportcompact supercar compact sports_car off-road buggy personal','SUVs, picapes e vans':'lighttruck pickup_truck','Caminhões e ônibus':'heavytruck mediumtruck tractortrailer lighttrailer coach transitbus tracked','Motos e quadriciclos':'streetbike dirtbike compactbike atv','Bicicletas':'bicycle','Barcos':'motorboat yacht ship humanboat','Aviões':'monoplane biplane airship','Helicópteros':'singleheli','Trens':'loco passengerrail apm'}.items():
    for t in ts.split(): VG[t.replace('_',' ')]=g
WG={'handgun':'Pistolas','melee':'Corpo a corpo','bat':'Corpo a corpo','blade':'Corpo a corpo','cue':'Corpo a corpo','tool':'Ferramentas','flashlight':'Ferramentas','sniper':'Rifles de precisão','submachinegun':'Submetralhadoras','assault':'Fuzis','shotgun':'Escopetas','thrown':'Arremessáveis','flash grenade':'Arremessáveis','fragmentation grenade':'Arremessáveis','molotov cocktail':'Arremessáveis','projectile':'Arremessáveis','canister':'Arremessáveis','heavymachinegun':'Pesadas','rocketlauncher':'Pesadas'}
def skip(text): return bool(re.match(r'\s*\{\{\s*Delete',text,re.I))
out={'ts':max(p['ts'] for k in R for p in R[k].values() if p['ts']),'vehicles':[],'weapons':[],'characters':[]}
pers=[]
for t,p in sorted(R['vehicles'].items()):
    if skip(p['text']): continue
    n,f=infobox(p['text']); ty=clean(f.get('type','')).lower()
    if ty=='personal': pers.append(t)
    cap=clean(f.get('capacity',''))
    out['vehicles'].append([t,VG.get(ty,'Outros'),clean(f.get('body_style','')),clean(f.get('manufacturer','')),cap[:60],games(f)])
for t,p in sorted(R['weapons'].items()):
    if skip(p['text']): continue
    n,f=infobox(p['text']); ty=clean(f.get('type','')).lower()
    out['weapons'].append([t,WG.get(ty,'Outros'),clean(f.get('firemode',''))[:60],clean(f.get('manufacturer',''))[:50],'',games(f)])
for t,p in sorted(R['characters'].items()):
    if skip(p['text']): continue
    n,f=infobox(p['text'])
    if not n: n,f=infobox('{{Infobox character'+sub.get(t,'').split('infobox',1)[-1]) if sub.get(t) else (None,{})
    st=clean(f.get('status','')); st={'Alive':'Vivo','Active':'Ativo','Deceased':'Morto','Incarcerated':'Preso'}.get(st,'')
    occ=clean(f.get('occupation',''));occ='' if occ=='Not given' else occ
    out['characters'].append([t,'Protagonistas' if t in('Jason Duval','Lucia Caminos') else 'Personagens',occ[:90],clean(f.get('affiliations',''))[:120],clean(f.get('home',''))[:70],[st] if st else []])
open(sys.argv[2],'w').write('window.WIKI='+json.dumps(out,ensure_ascii=False,separators=(',',':'))+';')
print({k:len(v) for k,v in out.items() if k!='ts'}, out['ts']); print('personal:',pers)
print(collections.Counter(v[1] for v in out['vehicles'])); print(collections.Counter(v[1] for v in out['weapons']))
print(sum(1 for v in out['vehicles'] if not v[5]),'vehicles only in VI')
for k in out:
    if k!='ts': print(out[k][:3])
print([c for c in out['characters'] if c[0] in('Jason Duval','Cal Hampton')])
