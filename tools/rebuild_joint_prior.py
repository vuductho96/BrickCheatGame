"""Recover whole verified refills without inventing score or stage labels."""
import json
from pathlib import Path
from engine.game_state import Piece
from solver.stochastic import ShapePrior


def rebuild(log_path, profile_path):
    prior=ShapePrior.load(profile_path)
    trays=[]
    for line in Path(log_path).read_text(encoding='utf8').splitlines():
        event=json.loads(line)
        before=event.get('before') or {};actual=event.get('actual') or {}
        if (event.get('event')=='verified' and len(before.get('pieces',()))==1
                and len(actual.get('pieces',()))==3):
            trays.append(tuple(Piece(p['id'],p['cells']).cells for p in actual['pieces']))
    data=json.loads(Path(profile_path).read_text(encoding='utf8'))
    # Existing lifetime counts stay intact; replay only reconstructs context.
    data['trays']=trays[-48:]
    data['recent']=[shape for tray in trays[-24:] for shape in tray]
    temporary=Path(profile_path).with_suffix('.tmp')
    temporary.write_text(json.dumps(data,indent=2),encoding='utf8')
    temporary.replace(profile_path)
    return len(trays)


if __name__=='__main__':
    print('Verified joint refills:',rebuild('artifacts/auto-moves.jsonl','config/shape-prior.json'))
