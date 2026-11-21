# Builds the app's data.js (window.ATLAS_PLACES) from a pinned GTADB landmarks catalogue.
# usage: places_build.py <landmarks.json> <out data.js>
# Accepts GTADB's own map/data/6/landmarks.json ({id: [address, coords, igPhotoSize, realAddress, ...]})
# or the Leonida Atlas copy of it ({landmarks: [{id, inGameAddress, ...}]}).
import json,sys
KEEP={'hotel','residential','construction','transportation','public','service','unconfirmed','restaurant','may-not-exist','retail','landmark','leisure','infrastructure','utilities','demolished','industrial','government','office','agriculture','safehouse','natural','events','fictional','cancelled'}
TYPO={'uncomfirmed':'unconfirmed','redisential':'residential','infr':'infrastructure','maynot exist':'may-not-exist'}
AREA={'Vice Dale County':'Vice-Dale County'}
def row(r):
    p=[s.strip() for s in (r.get("inGameAddress") or "").split(",")]
    name="" if "?" in p[0] else p[0]
    street=", ".join(p[1:-1]) if len(p)>2 else ""
    area=p[-1]
    area=AREA.get(area,area).replace("VIce","Vice").replace("CIty","City")
    tags=[]
    for t in r.get("tags",[]):
        t=TYPO.get(t,t).lstrip("/#"); t=TYPO.get(t,t)
        if t in KEEP and t not in tags: tags.append(t)
    c=r.get("inGameCoordinates")
    return [r["id"],name,street,area,[round(c[0],1),round(c[1],1)] if c else None,tags,r.get("realWorldAddress") or ""]
src=json.load(open(sys.argv[1]))
if "landmarks" in src: recs=src["landmarks"]
else: recs=[{"id":k,"inGameAddress":v[0],"inGameCoordinates":v[1] or None,"realWorldAddress":v[3],"tags":v[6]} for k,v in src.items()]
recs.sort(key=lambda r:int(r["id"][1:]))
rows=[row(r) for r in recs]
open(sys.argv[2],"w").write("window.ATLAS_PLACES="+json.dumps(rows,ensure_ascii=False,separators=(",",":"))+";")
print(len(rows),"rows")
