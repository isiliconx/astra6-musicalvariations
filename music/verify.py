#!/usr/bin/env python3
"""Read the generated MIDI without the compositor and cross-check the web event manifests."""
from pathlib import Path
from collections import Counter
from tempfile import TemporaryDirectory
import bisect, json, struct, subprocess, sys
ROOT=Path(__file__).resolve().parent

def events(blob):
    p,t=0,0
    def variable():
        nonlocal p
        x=0
        for _ in range(4):
            n=blob[p];p+=1;x=(x<<7)|(n&127)
            if n<128:return x
        raise AssertionError('invalid VLQ')
    while p<len(blob):
        t+=variable();status=blob[p];p+=1
        if status==0xff:
            a=blob[p];p+=1;size=variable();b=blob[p:p+size];p+=size
        else:
            a=blob[p];p+=1
            if status>>4 in (12,13):b=b''
            else:b=blob[p:p+1];p+=1
        yield t,status,a,b
    assert p==len(blob)

def midi(path):
    b=path.read_bytes()
    assert b[:8]==b'MThd\x00\x00\x00\x06'
    form,n,ppq=struct.unpack_from('>HHH',b,8)
    assert form==1 and ppq>0
    pos=14;tracks=[]
    for i in range(n):
        assert b[pos:pos+4]==b'MTrk'
        size=struct.unpack_from('>I',b,pos+4)[0]
        tracks.append(list(events(b[pos+8:pos+8+size])))
        assert tracks[-1][-1][1:]==(255,47,b'')
        pos+=8+size
    assert pos==len(b)
    tempo=[(t,int.from_bytes(val,'big')) for t,status,key,val in tracks[0] if status==255 and key==81]
    times=[x[0] for x in tempo]; elapsed=[0.]
    for (a,u),(z,_) in zip(tempo,tempo[1:]):elapsed.append(elapsed[-1]+(z-a)*u/(ppq*1e6))
    def sec(t):
        i=bisect.bisect_right(times,t)-1
        return elapsed[i]+(t-tempo[i][0])*tempo[i][1]/(ppq*1e6)
    notes=[]; controls=[]; parts=[]
    for i,tr in enumerate(tracks[1:]):
        active={}; pg=-1; pan=None; name=None
        for t,st,a,bb in tr:
            if st==255:
                if a==3:name=bb.decode()
                continue
            command=st>>4; ch=st&15
            if command==12:
                assert ch!=9;pg=a
            if command==11:
                val=bb[0]
                if a==10 and t==0:pan=val
                else:controls.append((round(sec(t),4),i,a,val))
            if command==9:
                assert a not in active
                active[a]=(t,bb[0])
            if command==8:
                start,v=active.pop(a)
                aa,zz=round(sec(start),4),round(sec(t),4)
                notes.append((aa,round(zz-aa,4),a,v,i))
        assert not active and pan is not None and name
        parts.append((name,pg,pan))
    return sorted(notes),sorted(controls),parts,round(sec(tracks[0][-1][0]),4)

def check(output):
    summary={}
    for path in sorted(output.glob('*.json')):
        d=json.loads(path.read_text())
        name=path.stem
        assert name==f'{d["id"]}-{d["mode"]}'
        notes,ctrl,parts,duration=midi(path.with_suffix('.mid'))
        assert notes==sorted(map(tuple,d['notes'])),name
        assert ctrl==sorted(map(tuple,d['controls'])),name
        assert parts==[(p['name'],p['program'],p['pan']) for p in d['parts']],name
        assert duration==d['duration'] and 48<duration<100,name
        assert len(notes)>250 and len(set(n[3] for n in notes))>=16,name
        assert len({c['id'] for c in d['cues']})==len(d['cues'])>=4,name
        assert 0<=d['cues'][0]['time']<.5
        assert all(a['time']<b['time'] for a,b in zip(d['cues'],d['cues'][1:]))
        assert d['cues'][-1]['time']<duration
        assert all(.01<dur and 21<=key<=108 and 1<=vel<=127
                   for at,dur,key,vel,i in notes),name
        summary[name]=(duration,len(notes))
    assert len(summary)==18 and all(n==2 for n in Counter(x.rsplit('-',1)[0] for x in summary).values())
    assert len(set(summary.values()))==18
    return summary

def score_labels(output):
    def first_theme(mode):
        d=json.loads((output/f'offenbach-{mode}.json').read_text())
        t=next(c['time'] for c in d['cues'] if c['id']=='refrain')
        lead=next(i for i,p in enumerate(d['parts']) if p['id']==('lead' if mode=='piano' else 'clar'))
        hits={}
        for a,du,n,v,i in d['notes']:
            if t-.02<=a<t+3.05 and i==lead:
                # roll and timing jitter can stagger the lower note of a chord slightly
                slot=round((a-t)/(60/d['bpm']*.5))
                hits[slot]=max(n,hits.get(slot,0))
        return [hits[i]%12 for i in sorted(hits)][:9]
    # G held | A C B A | D D | D E ...
    for mode in ('piano','orchestra'):
        assert first_theme(mode)==[7,9,0,11,9,2,2,2,4],(mode,first_theme(mode))

if __name__=='__main__':
    summary=check(ROOT/'performances')
    score_labels(ROOT/'performances')
    with TemporaryDirectory() as tmp:
        new=Path(tmp)
        subprocess.run([sys.executable,str(ROOT/'compose.py'),'--output',tmp],check=True,stdout=subprocess.DEVNULL)
        for p in (ROOT/'performances').iterdir():
            if p.suffix in ('.mid','.json'):assert p.read_bytes()==(new/p.name).read_bytes(),p.name
    print(f'PASS: {len(summary)} scores / {sum(x[1] for x in summary.values())} timed events, MIDI and JSON agree, iconic melody matches, clean rebuild byte-identical.')
