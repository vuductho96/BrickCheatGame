"""Local session monitor: log this game, honor Stop, never start a new game."""
import json
import shutil
import time
import urllib.request
from pathlib import Path

BASE='http://127.0.0.1:8765'
ROOT=Path(__file__).resolve().parent
LOG=ROOT/'artifacts'/'play-until-loss-log'
RECOVERABLE=('Thả lệch ô dự kiến','Chưa xác minh bàn và khay sau hủy kéo')


def get(path):
    with urllib.request.urlopen(BASE+path,timeout=10) as response:
        return json.load(response)


def post(action):
    token=get('/api/session')['token']
    request=urllib.request.Request(BASE+'/api/auto',
        data=json.dumps({'action':action,'mode':'deep'}).encode(),
        headers={'Content-Type':'application/json','X-Session-Token':token})
    with urllib.request.urlopen(request,timeout=10) as response:
        return json.load(response)


def append(event,**data):
    with (LOG/'session.jsonl').open('a',encoding='utf8') as stream:
        stream.write(json.dumps({'time':time.time(),'event':event,**data},ensure_ascii=False)+'\n')


def save_failures():
    for name in ('auto-drag-failure.png','auto-drag-template.png','auto-before-release.png'):
        source=ROOT/'artifacts'/name
        if source.exists():
            target=LOG/f'{source.stem}-{source.stat().st_mtime_ns}.png'
            if not target.exists():shutil.copyfile(source,target)


def finish(reason,game_over):
    summary={'reason':reason,'game_over_confirmed':game_over,'finished_at':time.time()}
    rows=[]
    source=ROOT/'artifacts'/'auto-moves.jsonl'
    for line in source.read_text(encoding='utf8').splitlines():
        row=json.loads(line)
        if row['time']>=1791605890:rows.append(row)
    summary['events']={event:sum(row['event']==event for row in rows)
                       for event in sorted({row['event'] for row in rows})}
    (LOG/'moves.jsonl').write_text(''.join(json.dumps(row,ensure_ascii=False)+'\n' for row in rows),encoding='utf8')
    (LOG/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf8')
    try:
        with urllib.request.urlopen(BASE+'/api/screen.png',timeout=10) as response:
            (LOG/'final-screen.png').write_bytes(response.read())
    except Exception as exc:append('final_screen_error',error=str(exc))
    append('finished',**summary)


def run():
    LOG.mkdir(exist_ok=True,parents=True)
    append('monitor_started')
    stable_id=None
    stable_count=0
    while True:
        try:
            status=get('/api/auto')
            append('status',status=status)
            save_failures()
            if not status['active']:
                state=get('/api/state')
                if state.get('phase')=='game_over':
                    finish('game_over',True)
                    return
                if not any(reason in status['message'] for reason in RECOVERABLE):
                    finish(status['message'],False)
                    return  # Includes the user's Stop button and manual input.
                # Resume only after three consistent confirmed board/tray reads.
                # Replan the actual board; never reuse a pre-mismatch plan.
                signature=state.get('state_id') if state.get('phase')=='playing' else None
                stable_count=stable_count+1 if signature and signature==stable_id else 1 if signature else 0
                stable_id=signature
                if stable_count>=3:
                    append('resume_from_confirmed_board',state=state)
                    post('start')
                    stable_id=None
                    stable_count=0
            else:
                stable_id=None
                stable_count=0
        except Exception as exc:
            append('monitor_error',error=str(exc))
        time.sleep(2)


if __name__=='__main__':run()
