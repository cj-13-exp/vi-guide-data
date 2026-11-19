import re
def infobox(text):
    m=re.search(r'\{\{\s*Infobox[^\n|]*',text,re.I)
    if not m: return None,{}
    i=m.end(); depth=2; j=i; n=len(text)
    # find matching close
    k=m.start()+2; depth=1
    while k<n and depth>0:
        if text.startswith('{{',k): depth+=1;k+=2
        elif text.startswith('}}',k): depth-=1;k+=2
        else: k+=1
    body=text[i:k-2]
    # split top-level pipes
    parts=[];cur='';d=0;b=0;x=0
    while x<len(body):
        if body.startswith('{{',x): d+=1;cur+='{{';x+=2;continue
        if body.startswith('}}',x): d-=1;cur+='}}';x+=2;continue
        if body.startswith('[[',x): b+=1;cur+='[[';x+=2;continue
        if body.startswith(']]',x): b-=1;cur+=']]';x+=2;continue
        if body[x]=='|' and d==0 and b==0: parts.append(cur);cur=''
        else: cur+=body[x]
        x+=1
    parts.append(cur)
    f={}
    for p in parts:
        if '=' in p:
            a,v=p.split('=',1); f[a.strip().lower()]=v.strip()
    return m.group(0)[2:].strip(),f
def clean(v):
    v=re.sub(r'<ref[^>]*?/>','',v); v=re.sub(r'<ref.*?</ref>','',v,flags=re.S)
    v=re.sub(r'<!--.*?-->','',v,flags=re.S)
    for _ in range(4):
        v=re.sub(r'\{\{\s*(?:Small|small|nowrap|Nowrap)\s*\|([^{}]*)\}\}',r'\1',v)
        v=re.sub(r'\{\{[^{}]*\}\}','',v)
    v=re.sub(r'\[\[(?:File|Image):[^\]]*\]\]','',v)
    v=re.sub(r'\[\[:?[^\]|]*\|([^\]]*)\]\]',r'\1',v); v=re.sub(r'\[\[:?([^\]]*)\]\]',r'\1',v)
    v=re.sub(r"'{2,}",'',v); v=re.sub(r'<br\s*/?>',' · ',v); v=re.sub(r'<[^>]+>','',v)
    v=re.sub(r'^\s*\*\s*','',v,flags=re.M); v=' · '.join(x.strip() for x in v.split('\n') if x.strip())
    return re.sub(r'\s+',' ',v).strip(' ·')
