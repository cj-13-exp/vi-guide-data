/* Atualização de dados sem nova versão da loja. Só DADOS (JSON), nunca código.
   1) aplica já na abertura o pacote guardado no aparelho (se for mais novo que o embutido)
   2) em segundo plano consulta manifest.json, baixa só o que mudou, confere sha256/formato/tamanho e guarda para a próxima abertura
   Qualquer falha (sem rede, servidor fora, arquivo inválido) mantém o que já funciona. Gerado em conjunto com tools/publish_data.py. */
(function () {
  // photos: what the app was built with keeps its bundled file (works offline); a picture added later is loaded from the data server
  function mergePhotos(base, add) {
    var m = {}, k, u = window.DATA_URL || ''; base = base || {};
    for (k in base) m[k] = base[k];
    for (k in add) if (!(k in base) && (u || /^https?:/.test(add[k]))) m[k] = /^https?:/.test(add[k]) ? add[k] : u + add[k];
    return m;
  }
  var V = window.DATA_VER, URL = window.DATA_URL || '', K = 'dsync:';
  window.DATA_STATUS = { applied: [], updated: [], checked: 0, error: '' };
  if (!V) return;
  function get(k) { try { return localStorage.getItem(K + k); } catch (e) { return null; } }
  function put(k, v) { try { localStorage.setItem(K + k, v); return true; } catch (e) { return false; } }
  var meta = {}; try { meta = JSON.parse(get('meta') || '{}'); } catch (e) { meta = {}; }
  function cnt(o) {   // same rule as tools/publish_data.py: items one level inside each global
    function c(v) { if (Array.isArray(v)) return v.length; if (v && typeof v === 'object') { var n = 0; Object.keys(v).forEach(function (k) { n += (v[k] && typeof v[k] === 'object') ? Object.keys(v[k]).length : 1; }); return n; } return 1; }
    var n = 0; Object.keys(o).forEach(function (g) { n += c(o[g]); }); return n;
  }
  function fresh(e) { return e && e.fmt === V.format && e.gen && e.gen >= V.generated; }   // cache older than the embedded data is ignored
  Object.keys(V.files).forEach(function (n) {
    var e = meta[n]; if (!fresh(e)) return;
    try { var o = JSON.parse(get(n) || 'x'); Object.keys(o).forEach(function (g) { if (g === 'PLACE_PHOTOS') { var have = {}, extra = {}, u = window.DATA_URL || ''; (window.PLACE_PHOTOS || []).forEach(function (i) { have[i] = 1; }); window[g] = o[g].filter(function (i) { if (have[i]) return true; if (u) { extra[i] = 1; return true; } return false; }); window.PHOTOS_REMOTE = extra; } else window[g] = g === 'IGP' ? mergePhotos(window.IGP, o[g]) : o[g]; }); window.DATA_STATUS.applied.push(n); } catch (x) {}
  });
  if (!URL || !window.fetch || !window.crypto || !crypto.subtle) return;
  function hex(buf) { var a = new Uint8Array(buf), s = ''; for (var i = 0; i < a.length; i++) s += (a[i] < 16 ? '0' : '') + a[i].toString(16); return s; }
  function one(n, want, cur) {
    return fetch(URL + n + '.json', { cache: 'no-store' }).then(function (r) { if (!r.ok) throw new Error(n + ' ' + r.status); return r.text(); }).then(function (t) {
      return crypto.subtle.digest('SHA-256', new TextEncoder().encode(t)).then(function (d) {
        if (hex(d) !== want.sha256) throw new Error(n + ': sha256 não confere');
        var o = JSON.parse(t); if (!o || typeof o !== 'object' || Array.isArray(o)) throw new Error(n + ': formato');
        want.globals.forEach(function (g) { if (!(g in o)) throw new Error(n + ': falta ' + g); });
        if (cur >= 5 && cnt(o) < 0.6 * cur) throw new Error(n + ': encolheu demais');
        if (!put(n, t)) throw new Error(n + ': sem espaço');
        meta[n] = { sha: want.sha256, n: cnt(o), fmt: V.format, gen: window.DATA_STATUS.gen }; window.DATA_STATUS.updated.push(n);
      });
    });
  }
  function run() {
    fetch(URL + 'manifest.json', { cache: 'no-store' }).then(function (r) { if (!r.ok) throw new Error('manifest ' + r.status); return r.json(); }).then(function (m) {
      if (m.format !== V.format) throw new Error('formato ' + m.format + ' não suportado');
      window.DATA_STATUS.gen = m.generated;
      var jobs = Object.keys(m.files).filter(function (n) { var cur = fresh(meta[n]) ? meta[n].sha : (V.files[n] || {}).sha; return V.files[n] && m.files[n].sha256 !== cur; });
      return jobs.reduce(function (p, n) {
        return p.then(function () { var c = fresh(meta[n]) ? meta[n].n : V.files[n].n; return one(n, m.files[n], c).catch(function (e) { window.DATA_STATUS.error += e.message + '; '; }); });
      }, Promise.resolve()).then(function () {
        Object.keys(m.files).forEach(function (n) { if (meta[n] && meta[n].sha === m.files[n].sha256) meta[n].gen = m.generated; });   // unchanged files are as new as the package
        put('meta', JSON.stringify(meta)); window.DATA_STATUS.checked = Date.now();
      });
    }).catch(function (e) { window.DATA_STATUS.error = e.message; });
  }
  setTimeout(run, 2500);
})();
