"""Static package, references, and canonical-copy tests. No third-party dependencies."""
from pathlib import Path
from html.parser import HTMLParser
import hashlib,json
ROOT=Path(__file__).resolve().parents[1]
SITE=ROOT/'site'
class References(HTMLParser):
    def __init__(self): super().__init__(); self.refs=[]; self.ids=[]; self.autoplay=False
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if 'id' in attrs:self.ids.append(attrs['id'])
        for key in ('src','href'):
            if key in attrs:self.refs.append(attrs[key])
        if tag in ('audio','video') and 'autoplay' in attrs:self.autoplay=True
for file in (SITE/'index.html',SITE/'credits.html'):
    parser=References();parser.feed(file.read_text())
    assert not parser.autoplay, 'Autoplay must be opt-in only'
    assert len(parser.ids)==len(set(parser.ids)),f'Duplicate IDs in {file}'
    for ref in parser.refs:
        if ref.startswith(('http:','https:','mailto:','data:','#')):continue
        assert (file.parent/ref.split('#')[0]).is_file(),f'Broken local link: {ref}'
scores=list((ROOT/'music/performances').glob('*.json'))
assert len(scores)==18
digests=[]
for score in scores:
    d=json.loads(score.read_text())
    for suffix in ('.json','.mid'):
        source=score.with_suffix(suffix);target=SITE/'data'/source.name
        assert source.read_bytes()==target.read_bytes(),f'Stale public score: {target.name}'
    mp3=SITE/'audio'/f'{score.stem}.mp3'
    assert mp3.is_file() and mp3.stat().st_size>300000,f'Missing/empty recording: {mp3.name}'
    digests.append(hashlib.sha256(mp3.read_bytes()).hexdigest())
assert len(set(digests))==18, 'Recordings must not duplicate each other'
assert len(list((SITE/'audio').glob('*.mp3')))==18
print('PASS: 18 unique recordings, 36 exact score copies, local references, IDs, no autoplay')
