#!/usr/bin/env python3
"""Posição aproximada por comparação de mapas (pedido do dono, 23/11/2026: "se você comparar o seu mapa com o mapa deles deve ser
possível o local aproximado"). Só usa o que aparece NA TELA do mapa público: fotos da mesma vista, sem mexer no mapa entre elas.

  map_compare.py blobs <base.jpg> <camada.jpg> [limiar] [área mín] [área máx]
      ícones que aparecem na camada e não na base (diferença de pixels), em pixels da foto: [[x, y, área], ...]
  map_compare.py fit <pares.json>
      pares = [[px, py, X, Y], ...] (pixel da foto, coordenada do nosso mapa); devolve a conversão (afim, mínimos quadrados)
      e o erro de cada ponto e o médio, em unidades do mapa (≈ metros)
  map_compare.py match <ícones.json> <nossos.json> [iterações]
      casa ícones de controle (sem nome) com pontos nossos de posição exata ([[nome, X, Y], ...]): chute inicial pelas caixas
      (y da tela para baixo = y do jogo para cima) e depois vizinho mais próximo + reajuste (ICP). Devolve pares e erro.
  map_compare.py apply <conversão.json> <ícones.json>
      converte pixels em coordenadas do nosso mapa

Sem bibliotecas: a foto vira BMP com o `sips` do macOS e é lida em Python puro."""
import sys, os, json, struct, subprocess, tempfile, math

def load(path):
    tmp = tempfile.NamedTemporaryFile(suffix='.bmp', delete=False).name
    subprocess.run(['sips', '-s', 'format', 'bmp', path, '--out', tmp], check=True, capture_output=True)
    b = open(tmp, 'rb').read(); os.unlink(tmp)
    off = struct.unpack_from('<I', b, 10)[0]; w, h = struct.unpack_from('<ii', b, 18); bpp = struct.unpack_from('<H', b, 28)[0]
    bot = h > 0; h = abs(h); step = bpp // 8; row = (w * step + 3) & ~3
    px = []
    for y in range(h):
        r = off + ((h - 1 - y) if bot else y) * row
        px.append(b[r:r + w * step])
    return w, h, step, px

def blobs(base, layer, thr=70, amin=40, amax=4000):
    w, h, s, A = load(base); w2, h2, s2, B = load(layer)
    if (w, h) != (w2, h2): raise SystemExit('fotos de tamanhos diferentes: %sx%s e %sx%s' % (w, h, w2, h2))
    mask = bytearray(w * h)
    for y in range(h):
        ra, rb = A[y], B[y]
        for x in range(w):
            i = x * s
            if max(abs(ra[i] - rb[i]), abs(ra[i + 1] - rb[i + 1]), abs(ra[i + 2] - rb[i + 2])) > thr: mask[y * w + x] = 1
    seen = bytearray(w * h); out = []
    for start in range(w * h):
        if not mask[start] or seen[start]: continue
        st = [start]; seen[start] = 1; xs = ys = n = 0; x0 = y0 = 10 ** 9; x1 = y1 = -1
        while st:
            p = st.pop(); y, x = divmod(p, w); n += 1; xs += x; ys += y
            x0, x1, y0, y1 = min(x0, x), max(x1, x), min(y0, y), max(y1, y)
            for q in (p - 1 if x else -1, p + 1 if x < w - 1 else -1, p - w, p + w):
                if 0 <= q < w * h and mask[q] and not seen[q]: seen[q] = 1; st.append(q)
        out.append([(x0 + x1) / 2, (y0 + y1) / 2, n, x1 - x0 + 1, y1 - y0 + 1])
    # junta pedaços do mesmo ícone (cores internas diferentes)
    out.sort(key=lambda b: -b[2]); merged = []
    for b in out:
        for m in merged:
            if abs(m[0] - b[0]) < 14 and abs(m[1] - b[1]) < 14: m[2] += b[2]; break
        else: merged.append(list(b))
    return [[round(b[0], 1), round(b[1], 1), b[2]] for b in merged if amin <= b[2] <= amax]

def solve(P):
    """afim X = a*px + b*py + c ; Y = d*px + e*py + f, mínimos quadrados (equações normais 3x3)"""
    def ls(vals):
        M = [[0.0] * 3 for _ in range(3)]; v = [0.0] * 3
        for (px, py, *_), t in zip(P, vals):
            r = (px, py, 1.0)
            for i in range(3):
                v[i] += r[i] * t
                for j in range(3): M[i][j] += r[i] * r[j]
        n = 3
        for c in range(n):
            p = max(range(c, n), key=lambda r: abs(M[r][c])); M[c], M[p] = M[p], M[c]; v[c], v[p] = v[p], v[c]
            for r in range(n):
                if r != c and M[c][c]:
                    f = M[r][c] / M[c][c]
                    for k in range(n): M[r][k] -= f * M[c][k]
                    v[r] -= f * v[c]
        return [v[i] / M[i][i] for i in range(n)]
    return ls([p[2] for p in P]) + ls([p[3] for p in P])

def conv(T, px, py): return T[0] * px + T[1] * py + T[2], T[3] * px + T[4] * py + T[5]

def fit(P):
    T = solve(P); errs = [math.hypot(*(a - b for a, b in zip(conv(T, p[0], p[1]), p[2:4]))) for p in P]
    return T, errs

def match(icons, ours, it=8):
    ix = [i[0] for i in icons]; iy = [i[1] for i in icons]; ox = [o[1] for o in ours]; oy = [o[2] for o in ours]
    sx = (max(ox) - min(ox)) / max(1e-9, max(ix) - min(ix)); sy = (max(oy) - min(oy)) / max(1e-9, max(iy) - min(iy)); s = (sx + sy) / 2
    T = [s, 0, min(ox) - s * min(ix), 0, -s, max(oy) + s * min(iy)]
    for _ in range(it):
        pairs = []
        for o in ours:
            best = min(icons, key=lambda i: math.hypot(*(a - b for a, b in zip(conv(T, i[0], i[1]), o[1:3]))))
            pairs.append([best[0], best[1], o[1], o[2], o[0]])
        # descarta os 20% piores antes de reajustar (ícone que falta ou sobra)
        T0, e0 = fit(pairs); keep = sorted(range(len(pairs)), key=lambda k: e0[k])[:max(4, int(len(pairs) * .8))]
        T = solve([pairs[k] for k in keep])
    T, errs = fit(pairs)
    return T, pairs, errs

if __name__ == '__main__':
    a = sys.argv
    if a[1] == 'blobs':
        print(json.dumps(blobs(a[2], a[3], *(int(x) for x in a[4:7]))))
    elif a[1] == 'fit':
        T, e = fit(json.load(open(a[2]))); print(json.dumps({'T': T, 'erro_medio': sum(e) / len(e), 'erros': [round(x) for x in e]}))
    elif a[1] == 'match':
        T, pairs, e = match(json.load(open(a[2])), json.load(open(a[3])), int(a[4]) if len(a) > 4 else 8)
        print(json.dumps({'T': T, 'erro_medio': round(sum(e) / len(e)), 'pares': [[p[4], round(p[0], 1), round(p[1], 1), round(err)] for p, err in zip(pairs, e)]}, ensure_ascii=False))
    elif a[1] == 'apply':
        T = json.load(open(a[2]))['T']; print(json.dumps([[round(c) for c in conv(T, i[0], i[1])] for i in json.load(open(a[3]))]))
    else: raise SystemExit(__doc__)
