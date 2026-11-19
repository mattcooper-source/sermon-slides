"""Experimental native ProPresenter 7 bundle builder using a verified user-supplied sample.
No external packages needed. The application does NOT claim ProPresenter-side rendering verification.
"""
import re, uuid, io, zipfile, copy, os
from pathlib import Path

TEMPLATE = Path(__file__).parent / 'templates' / 'reference.proBundle'
UUID_RE = re.compile(rb'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}')

def vint(num):
    out=bytearray()
    while num >= 128:
        out.append((num & 127)|128);num >>=7
    out.append(num)
    return bytes(out)

def dvint(data,pos):
    n=0;sh=0
    while pos<len(data):
        b=data[pos];pos+=1;n|=(b&127)<<sh
        if b<128:return n,pos
        sh+=7
        if sh>70:raise ValueError('Invalid varint')
    raise ValueError('Truncated varint')

def decode(data):
    fields=[];pos=0
    while pos<len(data):
        key,pos=dvint(data,pos);f,w=key>>3,key&7
        if f==0: raise ValueError('Invalid field')
        if w==0:v,pos=dvint(data,pos)
        elif w==1:v=data[pos:pos+8];pos+=8
        elif w==5:v=data[pos:pos+4];pos+=4
        elif w==2:
            n,pos=dvint(data,pos);v=data[pos:pos+n];pos+=n
        else:raise ValueError('Unsupported protobuf wire type')
        fields.append((f,w,v))
    return fields

def encode(fields):
    result=bytearray()
    for f,w,v in fields:
        result+=vint((f<<3)|w)
        if w==0:result+=vint(v)
        elif w==2:result+=vint(len(v))+v
        else:result+=v
    return bytes(result)

def rtfs(buf):
    """Collect RTF leaf strings within protobuf recursively."""
    try:fields=decode(buf)
    except Exception:return []
    out=[]
    for f,w,v in fields:
        if w!=2:continue
        if v.startswith(b'{\\rtf'):out.append(v)
        elif len(v)>8:out.extend(rtfs(v))
    return out

def encode_rtf(text):
    # RTF unicode escapes ensure en/em dashes, smart quotes, and verse numbers survive.
    parts=[]
    # The ^NN convention inserts upper-baseline verse numbers in RTF.
    text=re.sub(r'\^(\d{1,3})(?=\s|$)', lambda m: '\x01'+m.group(1)+'\x02',text)
    for c in text:
        if c=='\x01': parts.append('\\super ');continue
        if c=='\x02':parts.append('\\nosupersub ');continue
        if c in '\\{}': parts.append('\\'+c)
        elif c=='\n':parts.append('\\line ')
        elif c=='\t':parts.append('\\tab ')
        elif ord(c)>127:
            code=ord(c)
            if code>32767:code-=65536
            parts.append(f'\\u{code} ?')
        else:parts.append(c)
    return ''.join(parts).encode('ascii')

def replace_rtf(raw,text):
    """Keep original paragraph and font properties; replace trailing paragraph contents."""
    r=raw.decode('latin1')
    # The slide text occurs after the last formatting \cbN control near its end.
    matches=list(re.finditer(r'\\cb\d+\s',r))
    if not matches: raise ValueError('Unrecognized template RTF')
    m=matches[-1]
    tail=r[m.end():]
    if not tail.endswith('}') : raise ValueError('Unexpected template RTF ending')
    start=r[:m.end()].encode('latin1')
    return start+encode_rtf(text)+b'}'

def update_leafs(buf, body, reference):
    """Replace body and reference RTF; duplicated text models are updated together."""
    fields=decode(buf);out=[]
    for f,w,v in fields:
        if w==2:
            if v.startswith(b'{\\rtf'):
                # Background body normally uses white/gray palette with cb3; reference uses cb2.
                # The sample contains both ProPresenter slide and reflow RTF copies.
                hit=re.search(rb'\\cb([0-9]+)\s[^}]*}$',v)
                color=hit.group(1) if hit else b'3'
                v=replace_rtf(v,reference if color==b'2' else body)
            elif len(v)>10:
                try:v=update_leafs(v,body,reference)
                except (ValueError,OverflowError): pass
        out.append((f,w,v))
    return encode(out)

def duplicate_ids(buf, slide_id):
    # Only this slide's own root UUID is replaced; object UUIDs are regenerated,
    # while cross-presentation IDs could refer to master layouts, so preserve others.
    entries=decode(buf)
    old_id=decode(entries[0][2])[0][2]
    old_uuid=old_id[2:] if old_id.startswith(b'\n$') else None
    if old_uuid:
        buf=buf.replace(old_uuid,slide_id.encode('ascii'))
    return buf

def to_bundle(slides,title='Sermon Slides'):
    if not 1<=len(slides)<=300:raise ValueError('Add between 1 and 300 slides')
    with zipfile.ZipFile(TEMPLATE) as z:
        name=next(x for x in z.namelist() if x.endswith('.pro'))
        main=decode(z.read(name))
    samples=[v for k,w,v in main if k==13]
    scripture=samples[0]
    point=samples[18]
    blank=samples[1]
    generated=[]; ids=[]
    for i,item in enumerate(slides):
        typ=item.get('type','scripture')
        if typ not in ('scripture','point','blank'):raise ValueError('Invalid slide type')
        body=str(item.get('text','')).strip()
        ref=str(item.get('reference','')).strip()
        if len(body)>2500 or len(ref)>120:raise ValueError('Slide text exceeds allowed length')
        if typ=='scripture' and not ref:raise ValueError('Scripture slides need a passage reference')
        if typ=='blank':body='';ref=''
        source=scripture if typ=='scripture' else point if typ=='point' else blank
        sid=str(uuid.uuid4());ids.append(sid)
        altered=update_leafs(source,body,ref)
        altered=duplicate_ids(altered,sid)
        generated.append(altered)
    # Update the presentation's slide order list and slide record array.
    result=[]
    for k,w,v in main:
        if k==13:continue
        if k==12:
            items=decode(v)
            head=[x for x in items if x[0]!=2]
            head.extend((2,2,b'\n$'+sid.encode('ascii')) for sid in ids)
            v=encode(head)
        elif k==3:
            # Preserve original identifier if no reliable title field is known.
            pass
        result.append((k,w,v))
    result += [(13,2,s) for s in generated]
    payload=encode(result)
    with zipfile.ZipFile(io.BytesIO(),mode='w') as _:pass
    output=io.BytesIO()
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as z:
        clean=re.sub(r'[^\w .-]','',title)[:70].strip() or 'Sermon Slides'
        z.writestr(clean+'.pro',payload)
    return output.getvalue()

if __name__=='__main__':
    test=to_bundle([{'type':'scripture','text':'What then is Apollos? And what is Paul?','reference':'1 Corinthians 3:5–16'},{'type':'point','text':'God builds His church.'},{'type':'blank'}],'Test')
    with zipfile.ZipFile(io.BytesIO(test)) as z:
        data=z.read(z.namelist()[0]);arr=decode(data)
        assert sum(x[0]==13 for x in arr)==3
        assert sum(x[0]==2 for x in decode(next(v for f,w,v in arr if f==12)))==3
        assert b'God builds His church.' in data
    print('Native bundle ZIP/protobuf structural smoke test passed:',len(test),'bytes')
