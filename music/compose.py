#!/usr/bin/env python3
"""Score and render-neutral performance instructions. Rebuild with python3 music/compose.py."""
import json, math, random, struct, zipfile, xml.etree.ElementTree as ET
from pathlib import Path
ROOT=Path(__file__).resolve().parent
PPQ=960
PIANO=[('lead','Right hand',0,68),('bass','Left hand',0,59),('inner','Inner voice',0,64)]
ORCH=[
 ('vln','Violins',48,39),('wind','Flute',73,89),('oboe','Oboe',68,76),
 ('clar','Clarinet',71,84),('vc','Cellos',42,67),('cb','Basses',43,76),
 ('viola','Violas',41,49),('pizz','Pizzicato strings',45,53),('horn','Horns',60,53),
 ('perc','Percussion',-1,72),('tpt','Trumpets',56,68),('bsn','Bassoon',70,85),
 ('harp','Harp',46,38),('picc','Piccolo',72,91),('timp','Timpani',47,62)]
SCALE=(0,2,4,5,7,9,11)
STEPS=dict(zip('CDEFGAB',SCALE))
TITLES={
'offenbach':('Infernal Galop','A shortened performance from the historic score'),
'mozart':('A Minuet in Miniature','Clipped questions, neat answers, and a minor-key trio'),
'bach':('The Contrapuntal Galop','A minor-key invention with a quickening echo'),
'beethoven':('The Dance Knocks Back','Insistent fragments resolve into a broad major coda'),
'rossini':('The Imaginary Overture','A comic aside and an accumulating stage crescendo'),
'poulenc':('A Waltz Refused','A dry four-beat dance interrupted by a lyric episode'),
'chopin':('Nocturne after Midnight','A singing line over rippling accompaniment'),
'liszt':('Infernal Paraphrase','A low invocation grows into a virtuoso apotheosis'),
'tchaikovsky':('The Underworld Ballroom','A high-sweeping waltz in three, with a darker middle')
}
def vlq(x):
    out=[x&127]; x>>=7
    while x: out.insert(0,(x&127)|128); x>>=7
    return bytes(out)
def chunk(tag,data):return tag+struct.pack('>I',len(data))+data
def meta(tag,data):return bytes([255,tag])+vlq(len(data))+data
def track(events,end):
    data=bytearray(); last=0
    for t,priority,raw in sorted(events):
        data+=vlq(t-last)+raw;last=t
    data+=vlq(max(last,end)-last)+b'\xff\x2f\x00'
    return chunk(b'MTrk',data)
class Score:
    def __init__(self,id,mode,bpm,meter,key):
        self.id,self.mode,self.bpm,self.meter,self.key=id,mode,bpm,meter,key
        self.parts=PIANO if mode=='piano' else ORCH;self.indices={x[0]:i for i,x in enumerate(self.parts)}
        self.rng=random.Random(id+'-'+mode); self.notes=[];self.tempi={0:bpm};self.cues=[];self.ctrl=[]
    def note(self,part,b,d,p,v,art=.86,offset=0,jitter=.013):
        if not 21<=p<=108 or d<=0:return
        idx=self.indices[part]; b+=offset+self.rng.uniform(-jitter,jitter)
        s=round(max(.2,b+.23)*PPQ); e=s+round(d*art*PPQ)
        self.notes.append((s,e,int(p),min(121,max(24,round(v+self.rng.uniform(-2,2)))),idx))
    def chord(self,part,b,d,ps,v,art=.84,roll=0):
        for i,p in enumerate(ps):
            self.note(part,b,d,p,v-(5 if i<len(ps)-1 else 0),art,roll*i)
    def tempo(self,at,bpm):self.tempi[round((at+.23)*PPQ)]=round(max(28,bpm),3)
    def cue(self,id,title,b,desc):self.cues.append((id,title,round((b+.23)*PPQ),desc))
    def cc(self,part,beat,no,value):self.ctrl.append((max(0,round((beat+.23)*PPQ)),self.indices[part],no,value))
    def save(self,out):
        out.mkdir(parents=True,exist_ok=True)
        # Eliminate overlapping same-channel/pitch events; their note-offs would otherwise mute later attacks.
        notes=[]; active={}
        for s,e,p,v,ch in sorted(self.notes):
            k=p if self.mode=='piano' else (p,ch)
            if k in active and notes[active[k]][1]>=s:
                old=notes[active[k]]
                if s-old[0]<36:
                    if v>old[3]:notes[active[k]]=(old[0],max(old[1],e),p,v,ch)
                    continue
                notes[active[k]]=(old[0],s-2,p,old[3],old[4])
            active[k]=len(notes);notes.append((s,e,p,v,ch))
        tempi=sorted((t,round(60e6/bpm)) for t,bpm in self.tempi.items())
        def seconds(tick):
            sec=0
            for i,(a,u) in enumerate(tempi):
                if tick<=a:break
                b=tempi[i+1][0] if i+1<len(tempi) else tick
                sec+=(min(b,tick)-a)*u/1e6/PPQ
            return round(sec,4)
        end=max(max(x[1] for x in notes),max((x[0] for x in self.ctrl),default=0))
        nb,den=map(int,self.meter.split('/'))
        th=[(0,0,meta(3,(self.id+' tempo map').encode())),(0,1,meta(88,bytes([nb,int(math.log2(den)),24,8])))]
        th.extend((t,2,meta(81,u.to_bytes(3,'big'))) for t,u in tempi)
        used=sorted({x[4] for x in notes}); tracks=[track(th,end)]
        for i in used:
            id,name,pg,pan=self.parts[i]; c=9 if pg==-1 else i
            assert c!=9 or pg==-1
            ev=[(0,0,meta(3,name.encode())),(0,2,bytes([0xb0|c,10,pan]))]
            if pg>=0:ev.append((0,1,bytes([0xc0|c,pg])))
            ev.extend((t,3,bytes([0xb0|c,no,v])) for t,j,no,v in self.ctrl if i==j)
            for a,b,p,v,j in notes:
                if j==i:ev.extend(((a,5,bytes([0x90|c,p,v])),(b,4,bytes([0x80|c,p,0]))))
            tracks.append(track(ev,end))
        name=f'{self.id}-{self.mode}'
        (out/f'{name}.mid').write_bytes(chunk(b'MThd',struct.pack('>HHH',1,len(tracks),PPQ))+b''.join(tracks))
        mapidx={old:new for new,old in enumerate(used)}
        title,subtitle=TITLES[self.id]
        data=dict(id=self.id,mode=self.mode,title=title,subtitle=subtitle,duration=seconds(end),bpm=self.bpm,meter=self.meter,key=self.key,
          parts=[dict(id=p[0],name=p[1],program=p[2],pan=p[3]) for i,p in enumerate(self.parts) if i in used],
          cues=[dict(id=id,title=title,time=seconds(t),description=desc) for id,title,t,desc in self.cues],
          controls=[[seconds(t),mapidx[i],n,v] for t,i,n,v in sorted(self.ctrl) if i in mapidx],
          notes=[[seconds(s),round(seconds(e)-seconds(s),4),p,v,mapidx[i]] for s,e,p,v,i in notes])
        (out/f'{name}.json').write_text(json.dumps(data,separators=(',',':'),ensure_ascii=False)+'\n')
        return data

def read_source():
    with zipfile.ZipFile(ROOT/'canonical.mxl') as z: tree=ET.fromstring(z.read('score.musicxml'))
    out={}
    for m in tree.find('part').findall('measure'):
        b=previous=0.; hits=[]; grace=[]
        for n in m:
            d=float(n.findtext('duration','0'))/24
            if n.tag=='backup':b-=d
            if n.tag=='forward':b+=d
            if n.tag!='note':continue
            ch=n.find('chord') is not None; g=n.find('grace') is not None
            if not ch:previous=b
            pitch=n.find('pitch')
            if pitch is not None:
                p=STEPS[pitch.findtext('step')]+int(pitch.findtext('alter','0'))+12*(1+int(pitch.findtext('octave')))
                hand=int(n.findtext('staff','1'))
                art=.52 if n.find('notations/articulations/staccato') is not None else .88
                if g:grace.append((previous,.105,p,hand,.85,True))
                else:
                    if grace:
                        hits.extend((max(0,b-.1*(len(grace)-i)),gd,gp,gh,ga,True) for i,(_,gd,gp,gh,ga,_) in enumerate(grace));grace=[]
                    hits.append((previous,d,p,hand,art,False))
            if not ch and not g:b+=d
        out[int(m.get('number'))]=hits
    return out
SOURCE=read_source()
def top_line(n):
    notes={}
    for b,d,p,h,a,g in SOURCE[n]:
        if h==1 and not g and (b not in notes or p>notes[b][1]):notes[b]=(d,p,a)
    return [(b,*notes[b]) for b in sorted(notes)]

def canonical(mode):
    s=Score('offenbach',mode,148 if mode=='piano' else 154,'2/4','D major · G major')
    # Start with the original D-pedal runway to the famous G-major refrain,
    # take its repeat, then keep the score's D-major return and full octave coda.
    order=list(range(43,63))+list(range(47,62))+list(range(63,117))
    cues={0:('runway','The runway','Alternating fifths and a repeated-note pedal springboard into the famous refrain.'),
          4:('refrain','The famous refrain','The stepwise tail answers the high leap in the bright G-major dance tune.'),
          20:('repeat','Around again','The refrain returns with a louder answer and turns back toward D major.'),
          36:('galop','Back to the galop','Offenbach’s earlier galop strain returns, with clipped chromatic replies.'),
          52:('up','Up a fifth','The familiar refrain is heard in D major, higher and brighter than its first pass.'),
          67:('coda','The octave coda','Repeated fanfare notes and falling octaves drive the final cadence.')}
    for i,n in enumerate(order):
        b=i*2; main=i%8; swell=5*math.sin(math.pi*(main+1)/8)
        if i in cues:
            id,title,desc=cues[i];s.cue(id,title,b,desc)
        factor=1+.017*math.sin(main*math.pi/4)+(.035 if i>=67 else 0)
        if i in (3,18,19,33,34,51,66) or i>=len(order)-3:factor*=.94 if i<len(order)-2 else .84
        s.tempo(b,s.bpm*factor)
        hits=SOURCE[n];base=(72 if i<4 else 86 if i>=67 else 79)+swell
        if mode=='piano':
            for at,d,p,h,a,g in hits:
                primary=max((q for t,_,q,j,_,_ in hits if abs(t-at)<.001 and j==h),default=p)==p
                s.note('lead' if h==1 else 'bass',b+at,d,p,base+(4 if primary and h==1 else -9 if h==1 else -19)+(5 if at==0 else 0)-12*g,a)
        else:
            melody=top_line(n); lead='clar' if 4<=i<12 else 'vln' if 12<=i<20 or i>=52 else 'oboe' if 36<=i<44 else 'vln'
            for at,d,p,a in melody:
                p=p-12 if p>=86 and i<52 else p
                s.note(lead,b+at,d,p,base+5,.94 if d>=1 else .70)
                if i>=20 and i not in range(35,43):
                    s.note('picc' if i>=67 else 'wind',b+at,d,p+12 if p<=79 else p,base-14,.84 if d>=1 else .66,.015)
                if i>=67 and at==0:s.note('tpt',b+at,d,p-12 if p>=79 else p,base-8,.82)
            for at,d,p,h,a,g in hits:
                if h!=2 or g: continue
                if p<53:
                    s.note('vc',b+at,d,max(36,p),base-17,.61)
                    if i>=14:s.note('cb',b+at,d,max(36,p-12),base-24,.67)
                elif at%1!=0 or d<.7:
                    s.note('pizz',b+at,d,p,base-13,.58)
                    if i>=52:s.note('bsn',b+at,d,p-12,base-24,.58)
                elif i>=20:s.note('horn',b+at,d,p,base-22,.83)
            if 0<=i<4 or i>=65:
                s.note('perc',b,.45,38,base-13,.55)
                if i%4==0:s.note('perc',b,.7,49,base-13,.9)
            if i==len(order)-1:
                s.chord('horn',b,.9,[50,57,62,66],94);s.chord('vln',b,1,[62,66,69,74],97)
                s.note('timp',b,1,38,99,.92)
    return s

# Degrees refer to the G-major source. The octave leap in phrase four,
# and the long-short-short profile, survive the transformations.
THEME=[[(b,d,p-67) for b,d,p,_ in top_line(n)] for n in range(47,55)]
ANSWER=[[(b,d,p-67) for b,d,p,_ in top_line(n)] for n in [55,56,57,58,59,60,61,63]]
# Tonic, major/minor, quarter notes per bar, tempo, tonal plan by episode.
# Chord symbols are rendered below from spelled, register-independent voicings.
SPECS={
'mozart':(72,0,3,113,'C major',('C G7 C Am Dm G7 C G7','Am E7 Am Em F Dm G7 G7','C G7 Em Am Dm G7 C G7','C G7 C F Dm G7 C C')),
'bach':(62,1,4,140,'D minor',('Dm A7 Dm Gm Bb A7 Dm A7','F C7 F Am Gm A7 Bb A7','Gm D7 Gm Eb Cm D7 Gm A7','Dm A7 F Bb Gm A7 Dm D')),
'beethoven':(60,1,4,132,'C minor → C major',('Cm G7 Cm Ab Fm G7 Cm G7','Eb Bb7 Eb Cm Ab Fm G7 G7','Fm C7 Fm Db Ab Ddim G7 G7','C G7 C Am F G7 C C')),
'rossini':(65,0,4,157,'F major',('F C7 F Dm Gm C7 F C7','Dm A7 Dm Bb Gm F C7 C7','C G7 C Am F Dm G7 C7','F C7 F Bb Gm C7 F C7','F C7 F Bb Gm C7 F F')),
'poulenc':(62,0,4,134,'D major',('Dadd6 A7 Dmaj7 F#m7 Gmaj7 Gm6 D/F# A7b9','Bm7 E7 Amaj7 C#m7 F#7 Bm7 Em7 A7','Dmaj7 Bbadd6 Dadd6 F#m7 Gmaj7 Eb7 D/F# A7','Dadd6 A7 Dmaj7 B7 Em7 A7 Dadd6 Dadd6')),
'chopin':(65,1,4,103,'F minor → F major',('Fm C7 Fm Db Bbm C7 Fm C7','Ab Eb7 Ab Fm Db Bbm C7 C7','Db Ab7 Db Bbm Gb Gdim C7 C7','Fm C7 Ab Db Bbm C7 Fm F')),
'liszt':(66,1,4,126,'F♯ minor → F♯ major',('F#m C#7 F#m D Bm C#7 F#m C#7','A E7 A F#m D Bm C#7 C#7','Dm A7 Dm Bb Gm G#dim C#7 C#7','F# C#7 F# D#m B C#7 F# F#')),
'tchaikovsky':(63,0,3,115,'E♭ major',('Eb Bb7 Eb Cm Fm Bb7 Eb Bb7','Cm G7 Cm Ab Fm Eb Bb7 Bb7','Ab Eb7 Ab Fm Db Fm Bb7 Bb7','Eb Bb7 Eb Ab Fm Bb7 Eb Eb'))
}
CUES={
'mozart':[('Question','A light minuet gives each clipped question a neatly rounded answer.'),('Trio','The trio leans toward A minor; listen for the register to drop.'),('Return','The opening balance returns with answering flourishes.'),('Cadence','A small turn of ornament delays the last C-major cadence.')],
'bach':[('Subject','The age-old repeated notes become a minor-key invention subject.'),('Answer','A lower voice enters, answering the same figure rather than furnishing chords alone.'),('Sequence','Short motifs travel through G minor and back over a rising line.'),('Stretto','The entries draw closer and end with a major third above the bass.')],
'beethoven':[('Knocks','The first measure is reduced to percussive fragments and abrupt silences.'),('Lyrical answer','Longer lines and a softer register turn toward the relative major.'),('Development','Sharp accents press through new harmonies and break on the dominant.'),('Coda','A major-mode arrival turns the earlier fragments into a broad affirmative close.')],
'rossini':[('Curtain up','The bass runs like stage machinery while the melody trades comic little answers.'),('Aside','The textures thin out and the melody softens into a conspiratorial aside.'),('Build','Repeated gestures, louder and more crowded each time, set up the Rossini crescendo.'),('Tutti','The refrain bursts in at full weight.'),('Finale','Short calls and orchestral punctuation bring the curtain down.')],
'poulenc':[('Dry wit','The motif lands on clipped, added-note chords with deliberate gaps between the replies.'),('Cantabile','A legato line steps out against more widely spaced harmony.'),('False turn','A borrowed-flat-side chord interrupts the dance, then the bass quietly sidesteps home.'),('Afterthought','The first snap returns; the bright added sixth is allowed to hang.')],
'chopin':[('Nocturne','The tune stretches over a rolling left hand; the melody can arrive just after the bass.'),('Decorated answer','Small written-out lead-ins and echoes decorate the returning melody.'),('Unrest','A fuller middle register and a sequence of bass changes disturb the nocturne.'),('Candle out','The line unwinds over a widening cadential breath and a major final chord.')],
'liszt':[('Invocation','The motif sounds low and alone, surrounded by widening arpeggios.'),('Cantabile','The line climbs toward the top of the keyboard as its bass opens out.'),('Tremolo','Rapid repeated inner gestures and dark harmonic shifts raise the tension.'),('Apotheosis','Octaves and brass lift the theme into a brilliant major-mode ending.')],
'tchaikovsky':[('The ballroom','The can-can’s long and short notes become a sweeping three-beat line.'),('Minor episode','A quieter minor episode shifts the melody into the middle voices.'),('Grand arc','The line spreads upward while the two lighter beats keep turning underneath.'),('Return','The dance returns with broad downbeats, then softens into its final sweep.')]
}
PC={'C':0,'D':2,'E':4,'F':5,'G':7,'A':9,'B':11}
def rootname(s):
    name=s[0]; i=1
    if len(s)>1 and s[1] in '#b':name+=s[1];i+=1
    return (PC[name[0]]+(1 if name.endswith('#') else -1 if name.endswith('b') else 0))%12,s[i:]
def harmony(symbol):
    name,_,sl=symbol.partition('/'); rt,q=rootname(name)
    pcs=([0,3,6] if q=='dim' else [0,3,7] if q.startswith('m') and not q.startswith('maj') else [0,4,7])
    if '7' in q:pcs.append(11 if 'maj7' in q else 10)
    if '6' in q:pcs.append(9)
    if 'b9' in q:pcs.append(13)
    return rt,tuple((rt+p)%12 for p in pcs),rootname(sl)[0] if sl else rt
def register(p,lo,hi):
    while p<lo:p+=12
    while p>hi:p-=12
    return p
def chord_voice(pcs,target=63):
    return sorted(register(p,target-7,target+4) for p in pcs)
def retune(p,index,pcs,strict=False):
    if p%12 in pcs:return p
    if not strict:return p
    return min((p+i for i in range(-3,4) if (p+i)%12 in pcs), key=lambda n:(abs(p-n), n<p), default=p)
def melody_pitch(interval,tonic,minor):
    return tonic+interval-(1 if minor and interval%12 in (4,9) else 0)
def ornaments(s,voice,b,p,v,way=1):
    for i,tone in enumerate((p+way,p,p-way)):s.note(voice,b-.115+i*.036,.041,tone,v-13,.85,jitter=.003)

def variation(id,mode):
    root,minor,m,bpm,key,plans=SPECS[id]
    piano=mode=='piano'
    s=Score(id,mode,bpm if piano else bpm+(2 if id in ('rossini','mozart','tchaikovsky') else -2),f'{m}/4',key)
    plans=[line.split() for line in plans]
    for k,plan in enumerate(plans):
        title,desc=CUES[id][k];s.cue(f'part-{k+1}',title,k*8*m,desc)
        for j,symbol in enumerate(plan):
            b=(k*8+j)*m;rt,pcs,inv=harmony(symbol); ch=chord_voice(pcs,60 if id in ('chopin','bach') else 65)
            bass=register(inv,36,47)
            phrase=math.sin(math.pi*(j+.35)/8)
            power={'mozart':[0,-11,4,0], 'bach':[0,2,1,6], 'beethoven':[5,-16,10,18],
                   'rossini':[-6,-17,-4,12,16], 'poulenc':[0,-12,4,-2], 'chopin':[-4,0,11,-10],
                   'liszt':[-12,-6,9,18], 'tchaikovsky':[-3,-15,11,4]}[id][k]
            v=74+power+8*phrase
            if id=='rossini' and k==2:v+=j*3.7
            airy=id in ('chopin','tchaikovsky') or (id in ('liszt','poulenc','beethoven') and k==1)
            local_bpm=s.bpm*(1+(.043 if airy else .018)*phrase+(.04 if id in ('beethoven','liszt','rossini') and k>=2 else 0))
            if j==7:local_bpm*=.83 if airy else .92
            if j==7 and k==len(plans)-1:local_bpm*=.85
            s.tempo(b,local_bpm)
            if airy:s.tempo(b+m*.5,local_bpm*(1.045 if j in (1,2,5) else .95 if j in (3,7) else 1))
            if piano and (airy or id=='liszt'):
                s.cc('bass',b-.07,64,0);s.cc('lead',b-.07,64,0)
                if id!='liszt' or k!=2:
                    s.cc('bass',b+.13,64,95);s.cc('lead',b+.13,64,87)
                    s.cc('bass',b+m-.12,64,0);s.cc('lead',b+m-.12,64,0)
            last=j==7 and k==len(plans)-1
            if last:
                final=register(root,67,79)
                if piano:
                    s.chord('bass',b,m*1.18,[bass,bass+12],v-2,.99,.025)
                    ending=sorted(set([register(x,54,65) for x in pcs]+[final]))
                    s.chord('lead',b,m*1.16,ending,v+2,.97,.035 if airy else .009)
                else:
                    s.note('cb',b,m*1.12,bass,v-15,.99);s.note('vc',b,m*1.12,bass+12,v-9,.99)
                    s.chord('viola',b,m*1.12,ch[:3],v-14,.96)
                    s.note('vln',b,m*1.13,final,v+2,.98)
                    s.note('horn',b,m*1.08,register(pcs[1],55,69),v-18,.93)
                    if id in ('beethoven','rossini','liszt'):s.note('timp',b,m,register(rt,37,48),v+4,.94)
                continue
            notes=(ANSWER if k in (1,3) else THEME)[j]
            local_root=root
            local_minor=minor
            if id=='mozart' and k==1:local_root,local_minor=69,True
            if id=='bach' and k==1:local_root,local_minor=65,False
            if id=='bach' and k==2:local_root,local_minor=67,True
            if id=='beethoven' and k==1:local_root,local_minor=63,False
            if id=='beethoven' and k==3:local_minor=False
            if id=='rossini' and k==1:local_root,local_minor=62,True
            if id=='rossini' and k==2:local_root=60
            if id=='chopin' and k==1:local_root,local_minor=68,False
            if id=='chopin' and k==2:local_root,local_minor=61,False
            if id=='liszt' and k==1:local_root,local_minor=69,False
            if id=='liszt' and k==2:local_root,local_minor=62,True
            if id=='liszt' and k==3:local_minor=False
            if id=='tchaikovsky' and k==1:local_root,local_minor=60,True
            if id=='tchaikovsky' and k==2:local_root=68
            reg=12 if id in ('chopin','liszt') and k in (1,3) else 0
            if id=='liszt' and k==0:reg=-12
            if id=='poulenc' and k==1:reg=12
            if id=='tchaikovsky' and k==2:reg=12
            if id=='tchaikovsky' and k==1:reg=0
            line=[(at*m/2,d*m/2,melody_pitch(interval,local_root+reg,local_minor)) for at,d,interval in notes]
            if id=='beethoven' and k in (0,2):
                p=line[0][2];line=[(0,.46,p),(.5,.43,p),(1.25,.55,p),(2.25,1.15,line[-1][2])]
                if j in (3,7):line=line[:1]+[(1.5,1.55,retune(p-2,0,pcs,True))]
            if id=='bach':
                p=line[0][2]
                if len(line)<3:line=[(0,1,p),(1,.5,p+2),(1.5,.5,p),(2,1,p),(3,1,p-2)]
            if id=='rossini' and k==2:
                p=retune(line[0][2],0,pcs,True)
                line=[(0,.4,p),(.5,.4,p),(1,.43,p),(1.5,.48,p+2),(2.25,.55,p),(3,.55,p-2)]
            if id=='poulenc' and k!=1:
                p=line[0][2];line=[(.37,.38,p),(1.02,.33,p+2),(1.51,.41,p+5),(2.43,.46,p+4),(3.22,.43,line[-1][2])]
                if j%4==3:line=line[:3]
            if id=='mozart':
                line=[(0 if a==0 else min(m-.27,a+.10*(i%2)),d,p) for i,(a,d,p) in enumerate(line)]
            if id=='tchaikovsky' and len(line)==4:
                line=[(a,d,p) for (a,d),(_,_,p) in zip([(0,1), (1,.56),(1.58,.59),(2.22,.75)],line)]
            if id=='chopin' and len(line)>2:
                line=[(a+(.049 if i else 0),d,p) for i,(a,d,p) in enumerate(line)]
            if piano:lead='lead'
            else:
                lead={'mozart':('wind','oboe','vln','clar'),'bach':('oboe','vln','clar','vln'),'beethoven':('vln','clar','horn','tpt'),
                 'rossini':('clar','bsn','oboe','vln','tpt'),'poulenc':('oboe','clar','bsn','wind'),'chopin':('clar','vln','oboe','vln'),
                 'liszt':('vc','vln','horn','tpt'),'tchaikovsky':('vln','clar','vln','vln')}[id][k]
                s.cc(lead,b,11,min(127,82+round(v/4)))
                s.cc(lead,b+1,11,min(127,90+round(v/4)))
                s.cc(lead,b+m-.25,11,min(127,78+round(v/4)))
            for i,(at,d,p) in enumerate(line):
                if i==0 or j%4==3 and i==len(line)-1:p=retune(p,0,pcs,id!='poulenc' or k==1)
                if lead=='bsn':p=register(p,48,67)
                if lead=='horn':p=register(p,54,78)
                if lead=='vc':p=register(p,46,70)
                art=(.99 if airy else .75 if id in ('mozart','rossini','bach','tchaikovsky') else .5 if id=='poulenc' else .76)
                if i==0 and j%4==0 and id in ('mozart','chopin') and j>0:ornaments(s,lead,b+at,p,v)
                late=.04 if piano and airy else 0
                target=v+(6 if i==0 else 1 if i==len(line)-1 and j%4!=3 else -3)
                s.note(lead,b+at,d,p,target,art,late)
                if piano and (id=='liszt' and k>0 or id=='beethoven' and k==3) and (i==0 or v>=92):
                    s.note(lead,b+at,d,p-12,target-10,art,late-.009)
                if not piano:
                    if id in ('rossini','liszt','beethoven') and (k>=3 or k==2 and j>3):
                        secondary='vln' if lead!='vln' else 'tpt'
                        s.note(secondary,b+at,d,register(p,56,84),target-10,art,.017)
                    if (id=='tchaikovsky' and k in (0,2,3) or id=='mozart' and k==2) and i in (0,2):
                        s.note('wind',b+at,d,register(p,72,96),target-16,.84,.018)
                    if id=='poulenc' and j%2==1 and i in (1,3):
                        s.note('clar' if lead!='clar' else 'oboe',b+at+.13,d*.65,p-12,target-19,.72)
            accompany(s,id,k,j,b,m,bass,ch,pcs,rt,v,airy,line)
    return s

def accompany(s,id,k,j,b,m,bass,ch,pcs,rt,v,airy,line):
    piano=s.mode=='piano'
    fifth=register(rt+7,36,47)
    if piano:
        if id=='mozart':
            s.note('bass',b,.85,bass,v-18,.76)
            for at in (1,2):
                if j!=7 or at==1:s.chord('inner',b+at,.67,ch[:3],v-24+(at==1)*4,.62)
            if j in (2,6) and k!=1:
                high=register(pcs[-1],58,70)
                for i,p in enumerate((high,high+2,high)):s.note('inner',b+2.25+i*.23,.19,p,v-19,.78)
        elif id=='bach':
            # Countersubjects at the octave / fifth; intermediary passing
            # tones travel in contrary motion rather than repeating a chord figure.
            sub=[(t,d,p-12) for t,d,p in line]
            if k==1 and j%2==0 or k==3:
                if k==3 and j%2==0:delay=.5
                else:delay=1
                for at,d,p in sub:
                    if at+delay<m-.1:s.note('bass',b+at+delay,min(d,m-at-delay),register(p,43,65),v-10,.84)
            else:
                arpe=(bass,bass+7 if j%2==0 else fifth,register(pcs[1],44,55),register(rt,47,58))
                for i,p in enumerate(arpe):s.note('bass',b+i,1,p,v-15+(i==0)*5,.78)
            if k>=1 and j%2==1:
                a=register(pcs[1],53,64)
                for i,p in enumerate((a,a-2,register(pcs[0],52,63),a)):s.note('inner',b+.5+i*.75,.61,p,v-23,.86)
        elif id=='beethoven':
            if k in (0,2):
                for i,at in enumerate((0,.5,1.25,2.25) if j%4!=3 else (0,1.5)):
                    s.chord('bass',b+at,.62 if i==0 else .39,[bass,bass+12],v-9-(i%2)*5,.62,.008)
                    if i in (0,3):s.chord('inner',b+at,.5,ch,v-12,.51,.006)
            elif k==1:
                for i,at in enumerate((0,.5,1,1.5,2,2.5,3,3.5)):s.note('bass',b+at,.5,[bass,ch[0]-12,ch[1]-12,ch[-1]-12][i%4],v-22,.91)
            else:
                for at in (0,2):
                    s.chord('bass',b+at,.8,[bass,bass+12],v-6,.84);s.chord('inner',b+at+.25,1.25,ch,v-15,.9,.011)
        elif id=='rossini':
            for at in (0,1,2,3):
                s.note('bass',b+at,.5,bass if at%2==0 else fifth,v-17+(at==0)*5,.65)
                if j%4!=3 or at<2:s.chord('inner',b+at+.5,.45,ch[:3],v-17-(at%2)*3,.54)
                if k>=2 and at%2==1:s.chord('bass',b+at+.28,.21,[bass+12,register(rt+7,47,58)],v-20,.77)
        elif id=='poulenc':
            for at in ((0,2.5) if k!=1 else (0,2)):
                s.note('bass',b+at,1.4 if k==1 else .46,bass,v-15,.92 if k==1 else .42)
            for at in ((.68,1.6,3.14) if k!=1 else (.25,2.15)):
                if at>=3 and j%4==3:continue
                s.chord('inner',b+at,1.45 if k==1 else .44,ch,v-20,.97 if k==1 else .45,.009)
        elif id=='chopin':
            low=[bass,register(rt+7,bass+5,bass+16),register(pcs[1],48,59),register(pcs[-1],54,65),
                 register(pcs[0],55,66),register(pcs[1],48,59),register(rt+7,43,54),register(pcs[1],48,59)]
            for i,p in enumerate(low):
                s.note('bass',b+i*.5,.51,p,v-(21 if i==0 else 33)+(6 if k==2 and i%4==0 else 0),.97 if i<4 else .91,jitter=.008)
            if k in (1,2) and j in (1,3,5,6):
                p=register(pcs[-1],55,66); s.note('inner',b+2.12,1.38,p,v-24,.98)
                if k==2:s.note('inner',b+3.15,.76,p+2,v-20,.94)
        elif id=='liszt':
            figures=[bass,register(rt+7,43,54),*ch,*(p+12 for p in ch),*reversed(ch)]
            if k==0:
                s.note('bass',b,2.6,bass,v-20,.98)
                for i,p in enumerate(figures[:8]):s.note('inner',b+.45+i*.31,.26,p,v-26+i,.96)
            elif k==1:
                for i,p in enumerate((bass,*figures[1:7],figures[2])):s.note('bass' if i<3 else 'inner',b+i*.5,.44,p,v-25+(i==0)*8,.9)
            elif k==2:
                s.chord('bass',b,2,[bass,bass+12],v-11,.8)
                for i in range(13):
                    s.chord('inner',b+.5+i*.25,.21,ch[:2] if i%2==0 else ch[-2:],v-23+i*.55,.65)
            else:
                for at in (0,1.95):s.chord('bass',b+at,.88,[bass,bass+12],v-10,.79,.009)
                for i,p in enumerate((figures[2:7]+figures[4:9])[:8]):s.note('inner',b+.14+i*.44,.37,p,v-15+(i%4),.79)
        else:
            # Waltz: a planted downbeat, then two differently weighted lifts.
            s.note('bass',b,.96,bass,v-16,.91)
            if k>=2:s.note('bass',b,.84,bass+12,v-20,.86)
            for at,soft in ((1,-19),(2,-26)):
                s.chord('inner',b+at+(0.024 if at==2 else 0),.73,ch[:3],v+soft,.72,.012)
            if k==1 or j in (2,6):s.note('inner',b+2.5,.42,register(pcs[1],66,77),v-19,.95)
        return

    # Orchestral accompaniments are scored independently of the piano reduction:
    # section entries, sustained underlay, percussion and wind exchanges.
    if id=='bach':
        echo='vc' if k<2 else 'bsn'
        if k==0 and j==0:return
        if k in (1,3):
            delay=.5 if k==3 else 1
            for at,d,p in line:
                if at+delay<m-.1:s.note(echo,b+at+delay,min(d,m-at-delay),register(p,45,66),v-12,.87)
        else:
            for i,p in enumerate((bass+12,register(pcs[-1],47,58),register(pcs[1],48,59),register(rt,45,56))):
                s.note(echo,b+i,.96,p,v-15,.86)
        if not (k==0 and j<2):
            s.note('viola',b,1.9,register(pcs[1],53,64),v-25,.9)
            s.note('viola',b+2,1.75,register(pcs[-1],53,64),v-21,.91)
        if k>=2:s.note('cb',b,2,bass,v-27,.93)
    elif id in ('mozart','tchaikovsky'):
        s.note('vc',b,.9,bass+12,v-15,.77)
        if k>=2 or id=='tchaikovsky':s.note('cb',b,1.1,bass,v-26,.87)
        for i,a in enumerate((1,2)):
            s.chord('pizz',b+a,.73,ch[:3],v-20-i*5,.66)
        if id=='mozart':
            if j%2==1:s.note('bsn',b+1.3,1.2,register(pcs[0],48,59),v-19,.88)
            if j%4==2:
                for i,p in enumerate(ch[:3]):s.note('vln' if k!=2 else 'clar',b+1.32+i*.45,.39,p+7,v-16,.66)
        else:
            s.chord('viola',b,2.9,ch[:2],v-30 if k==1 else v-19,.91)
            if k in (2,3):
                s.chord('horn',b,2.9,[register(pcs[0],52,63),register(pcs[1],53,64)],v-24,.92)
                for i,p in enumerate([bass,register(pcs[-1],49,60),ch[0],ch[-1],ch[-1]+12]):
                    s.note('harp',b+i*.52,.46,p,v-19+i*.8,.95)
    elif id in ('rossini','beethoven'):
        build=(id=='rossini' and k==2)
        if id=='beethoven' and k==1:
            s.note('vc',b,3.9,bass+12,v-15,.97)
            s.chord('viola',b,3.9,ch[:3],v-22,.95)
            for i,p in enumerate(ch):s.note('wind',b+2.3+i*.48,.38,p+12,v-19,.82)
        else:
            for i,at in enumerate((0,1,2,3) if id=='rossini' else (0,.5,1.25,2.25)):
                bp=bass if i%2==0 else fifth
                s.note('vc',b+at,.64,bp+12,v-15,.65)
                if not (id=='rossini' and k==1):s.note('cb',b+at,.57,bp,v-23,.65)
                if id=='rossini':
                    s.chord('pizz',b+at+.5,.38,ch[:3],v-20,.54)
                    if k>=3 or build and j>=3:s.note('bsn',b+at+.5,.37,ch[i%len(ch)]-12,v-20,.68)
                elif i in (0,3):
                    s.chord('viola',b+at,.57,ch,v-15,.6)
            if id=='beethoven' and k in (2,3) or id=='rossini' and (k>=3 or build and j>=5):
                s.chord('horn',b,.9,ch[:2],v-22,.84)
                s.note('timp',b,.69,register(rt,36,47),v-7,.8)
                if j%4==0:s.note('perc',b,.55,49,v-16,.87)
                if j%2==1:s.note('perc',b+2,.38,38,v-15,.62)
    elif id=='poulenc':
        if k==1:
            s.note('vc',b,3.9,bass+12,v-16,.97)
            s.chord('viola',b,3.8,ch[:2],v-25,.96)
            s.note('wind',b+2,1.55,register(pcs[-1],72,83),v-22,.97)
        else:
            s.note('pizz',b,.49,bass+12,v-11,.52)
            for at,i in [(0.56,0),(1.57,1),(2.47,2),(3.39,3)]:
                if j%4==3 and i>=2:continue
                s.note('bsn',b+at,.42,register(pcs[i%len(pcs)],47,61),v-13,.46)
                s.chord('pizz',b+at,.48,ch,v-21,.45)
                if i in (1,3):s.note('horn',b+at+.06,.29,ch[-1],v-20,.6)
    else:
        s.note('cb',b,3.85,bass,v-25,.93)
        if id!='liszt' or k!=0:s.note('vc',b,3.8,bass+12,v-20,.96)
        s.chord('viola',b+.17,3.68,ch[:2],v-26+(3 if k>=2 else 0),.94,.025)
        if id=='liszt' and k>=2:
            for i in range(12):
                s.note('vln' if k==2 else 'wind',b+.45+i*.25,.23,ch[i%len(ch)]+(12 if k==3 else 0),v-25+i*.53,.69)
            if k==3:s.chord('horn',b,3.65,ch[:3],v-23,.95)
            if j in (0,4,6):s.note('timp',b,.9,register(rt,36,47),v-13,.89)
        else:
            for i,p in enumerate((bass,register(rt+7,43,54),ch[0],ch[-1],ch[-1]+12,ch[-2],ch[0],ch[-1])):
                s.note('harp',b+i*.5,.49,p,v-25+4*(i%4==0),.93)
            if k in (1,2) and j%2==1:s.note('horn',b+1.85,1.85,ch[-1],v-28,.92)

def main():
    import argparse
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output',type=Path,default=ROOT/'performances')
    ap.add_argument('--composer',choices=['all','offenbach',*SPECS],default='all')
    args=ap.parse_args()
    for id in (['offenbach',*SPECS] if args.composer=='all' else [args.composer]):
        for mode in ['piano','orchestra']:
            data=(canonical(mode) if id=='offenbach' else variation(id,mode)).save(args.output)
            print(f'{id:13} {mode:10} {data["duration"]:6.2f}s {len(data["notes"]):4} notes {len(data["parts"]):2} parts {len(data["cues"])} cues')
if __name__=='__main__':main()
