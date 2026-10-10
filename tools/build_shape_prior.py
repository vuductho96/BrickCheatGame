"""Count verified refills only; repeated captures/retries are not new trays."""
import json,sys
from collections import Counter
from pathlib import Path

def build(path):
    counts=Counter();batches=0
    for line in Path(path).read_text(encoding='utf8').splitlines():
        e=json.loads(line)
        if e['event']!='verified':continue
        before=e.get('before') or {};after=e.get('actual') or {}
        if len(before.get('pieces',[]))==1 and len(after.get('pieces',[]))==3:
            batches+=1
            for piece in after['pieces']:
                counts[tuple(tuple(c) for c in piece['cells'])]+=1
    return {'source':'verified refill events only','batches':batches,
            'shapes':[{'cells':s,'count':n} for s,n in sorted(counts.items())]}

if __name__=='__main__':
    data=build('artifacts/auto-moves.jsonl')
    Path('config/shape-prior.json').write_text(json.dumps(data,indent=2),encoding='utf8')
    print(json.dumps({'batches':data['batches'],'shapes':len(data['shapes'])}))
