#!/usr/bin/env python3
"""Põe no app as fotos que o dono aprovou na página Aprovações (cartões "Fotos sugeridas").
usage: photo_apply.py <app/www> <state dir> <aprovados.json> <sharp bin> <dhash bin>

<aprovados.json>: lista de cartões aprovados e ainda não feitos, cada um {id, key, title, cands:[...], chosen:[i,...]} (lido do banco).
Mesmo critério da coleta antiga (gtawiki_fetch.py): cópia de 900 px da gta.wiki, nitidez >= 25 (variância do Laplaciano) e nada
parecido (dhash <= 6) com foto que já está no app. A 1ª foto de um item SEM foto entra em ig.js (window.IGP); as outras ficam em
ig_more.js (window.IGPX = {chave: [caminhos]}), guardadas para a galeria do item (recurso que ainda precisa da aprovação do dono).
Saída: imprime e grava <state>/photo_apply_result.json {id: {ok: [...], skipped: [...]}} para a rotina marcar "done" no banco."""
import sys, os, re, json, time, subprocess, urllib.request, urllib.parse

APP, STATE, APPROVED, SHARP, DH = sys.argv[1:6]
UA = {'User-Agent': 'LeonidaCompanionPrototype/0.1 (fan app prototype; generic-client)'}

def load_js(f, var):
    p = os.path.join(APP, f)
    if not os.path.exists(p): return {}
    t = open(p, encoding='utf-8').read()
    m = re.search(r'window\.' + var + r'\s*=\s*', t)
    return json.JSONDecoder().raw_decode(t, m.end())[0] if m else {}

def dh(path):
    out = subprocess.run([DH, path], capture_output=True, text=True).stdout.split()
    return out[1] if len(out) > 1 else None
ham = lambda a, b: bin(int(a, 16) ^ int(b, 16)).count('1')

def thumb900(file):
    q = urllib.parse.urlencode({'action': 'query', 'prop': 'imageinfo', 'iiprop': 'url', 'iiurlwidth': '900', 'titles': 'File:' + file, 'format': 'json'})
    d = json.load(urllib.request.urlopen(urllib.request.Request('https://gta.wiki/api.php?' + q, headers=UA), timeout=60))
    ii = (list(d['query']['pages'].values())[0].get('imageinfo') or [{}])[0]
    return ii.get('thumburl') or ii.get('url')

def main():
    igp, igx = load_js('ig.js', 'IGP'), load_js('ig_more.js', 'IGPX')
    kf = os.path.join(STATE, 'known_hashes.json')
    known = json.load(open(kf)) if os.path.exists(kf) else {}
    for p in list(igp.values()) + [x for v in igx.values() for x in v]:
        if p not in known and os.path.exists(os.path.join(APP, p)): known[p] = dh(os.path.join(APP, p))
    os.makedirs(os.path.join(APP, 'ig'), exist_ok=True); dl = os.path.join(STATE, 'photo_dl'); os.makedirs(dl, exist_ok=True)
    result = {}
    for card in json.load(open(APPROVED)):
        key, ok, skip = card['key'], [], []
        for i in card.get('chosen', []):
            c = card['cands'][i]
            try:
                u = thumb900(c['file']); raw = os.path.join(dl, re.sub(r'[^A-Za-z0-9._-]', '_', c['file']))
                open(raw, 'wb').write(urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=60).read()); time.sleep(1.1)
            except Exception as e: skip.append([c['file'], 'download: %s' % e]); continue
            n = len(igx.get(key, [])) + (1 if key in igp else 0)
            slug = re.sub(r'[^a-z0-9]+', '-', key.lower()).strip('-') + ('' if n == 0 else '-%d' % (n + 1))
            rel = 'ig/%s.jpg' % slug; dst = os.path.join(APP, rel)
            subprocess.run(['sips', '-s', 'format', 'jpeg', '-s', 'formatOptions', '76', '-Z', '900', raw, '--out', dst], capture_output=True)
            if not os.path.exists(dst) or os.path.getsize(dst) < 6000: skip.append([c['file'], 'conversão falhou']); continue
            w = int(subprocess.run(['sips', '-g', 'pixelWidth', dst], capture_output=True, text=True).stdout.split()[-1])
            h = int(subprocess.run(['sips', '-g', 'pixelHeight', dst], capture_output=True, text=True).stdout.split()[-1])
            sv = subprocess.run([SHARP, dst, '1', str(w), str(h)], capture_output=True, text=True).stdout.split()
            sharp = float(sv[1]) if len(sv) > 1 else 0
            hh = dh(dst)
            dup = next((p for p, x in known.items() if x and hh and p != rel and ham(hh, x) <= 6), None)
            if sharp < 25: os.remove(dst); skip.append([c['file'], 'borrada (%.0f)' % sharp]); continue
            if dup: os.remove(dst); skip.append([c['file'], 'parecida com ' + dup]); continue
            known[rel] = hh
            if key not in igp: igp[key] = rel
            else: igx.setdefault(key, []).append(rel)
            ok.append(rel)
        result[card['id']] = {'ok': ok, 'skipped': skip}
        print('  %s: %d no app, %d recusadas %s' % (card.get('title', key), len(ok), len(skip), [s[1] for s in skip]))
    open(os.path.join(APP, 'ig.js'), 'w', encoding='utf-8').write('window.IGP=' + json.dumps(igp, ensure_ascii=False, separators=(',', ':')) + ';')
    open(os.path.join(APP, 'ig_more.js'), 'w', encoding='utf-8').write('window.IGPX=' + json.dumps(igx, ensure_ascii=False, separators=(',', ':')) + ';')
    json.dump(known, open(kf, 'w'))
    json.dump(result, open(os.path.join(STATE, 'photo_apply_result.json'), 'w'), ensure_ascii=False, indent=1)

if __name__ == '__main__':
    main()
