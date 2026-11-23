#!/usr/bin/env python3
"""Aplica a foto PRINCIPAL que o dono escolheu na aba Dados do app (coleção "photomain" do banco da página Aprovações).
usage: photo_main.py <app/www> <photomain.json>      photomain.json: [{"pk": "c:Jason Duval", "path": "ig/c-jason-duval.jpg"}, ...]

O app mostra a primeira que achar nesta ordem: personagens (chars.js CHAR_PHOTOS), gta.wiki (ig.js IGP), outras (hq.js HQP).
Para a escolhida aparecer, ela vai para o lugar de cima e as outras descem para a galeria guardada (ig_more.js IGPX). Nenhuma foto é apagada."""
import sys, os, re, json

APP, SRC = sys.argv[1], sys.argv[2]

def load(f, var):
    p = os.path.join(APP, f)
    if not os.path.exists(p): return {}, ''
    t = open(p, encoding='utf-8').read(); m = re.search(r'window\.' + var + r'\s*=\s*', t)
    if not m: return {}, ''
    v, end = json.JSONDecoder().raw_decode(t, m.end())
    return v, t[end:]

def save(f, var, v, rest):
    open(os.path.join(APP, f), 'w', encoding='utf-8').write('window.%s=%s%s' % (var, json.dumps(v, ensure_ascii=False, separators=(',', ':')), rest or ';'))

def main():
    CH, rch = load('chars.js', 'CHAR_PHOTOS'); IG, rig = load('ig.js', 'IGP'); HQ, rhq = load('hq.js', 'HQP'); X, rx = load('ig_more.js', 'IGPX')
    done = 0
    for c in json.load(open(SRC)):
        pk, path = c.get('pk'), c.get('path')
        if not pk or not path: continue
        allp = [p for p in [CH.get(pk), IG.get(pk), HQ.get(pk)] + X.get(pk, []) if p]
        if path not in allp: print('  %s: foto %s não está mais no item' % (pk, path)); continue
        if allp[0] == path: continue                                   # já é a principal
        rest = [p for p in allp if p != path]
        CH.pop(pk, None); HQ.pop(pk, None)
        IG[pk] = path                                                  # a escolhida fica no IGP (sem foto de personagem por cima)
        X[pk] = rest
        done += 1; print('  %s: principal agora %s (%d guardadas na galeria)' % (pk, path, len(rest)))
    save('chars.js', 'CHAR_PHOTOS', CH, rch); save('ig.js', 'IGP', IG, rig); save('hq.js', 'HQP', HQ, rhq); save('ig_more.js', 'IGPX', X, rx)
    print('fotos principais trocadas:', done)

if __name__ == '__main__':
    main()
