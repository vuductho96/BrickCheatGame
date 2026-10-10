from pathlib import Path
import cv2
from web_bridge import PhoneBridge

ROOT=Path(__file__).resolve().parents[1]

def test_classic_terminal_labels_survive_stream_compression_and_score_changes():
    bridge=PhoneBridge()
    frame=cv2.imread(str(ROOT/'artifacts/play-until-loss-log/final-screen.png'))
    # The high-score numbers are variable and excluded from the templates.
    frame[1100:1260,320:760]=0
    small=cv2.resize(frame,(540,1170))
    _,jpeg=cv2.imencode('.jpg',small,[cv2.IMWRITE_JPEG_QUALITY,78])
    streamed=cv2.resize(cv2.imdecode(jpeg,1),(1080,2340),interpolation=cv2.INTER_NEAREST)
    assert bridge.parse(streamed)['phase']=='game_over'

def test_classic_terminal_requires_both_labels_and_rejects_playing_win():
    bridge=PhoneBridge()
    frame=cv2.imread(str(ROOT/'artifacts/play-until-loss-log/final-screen.png'))
    frame[1720:1920,220:860]=0
    assert not bridge.is_over(frame)
    for name in ('trial-current.png','shopee-win-reference.png'):
        assert not bridge.is_over(cv2.imread(str(ROOT/'captures'/name)))


def test_ordinary_classic_loss_is_not_mistaken_for_hidden_board_or_win():
    bridge=PhoneBridge()
    frame=cv2.imread(str(ROOT/'artifacts/loss-16668/reported-loss.png'))
    for quality in (78,95):
        _,jpeg=cv2.imencode('.jpg',cv2.resize(frame,(540,1170)),[cv2.IMWRITE_JPEG_QUALITY,quality])
        streamed=cv2.resize(cv2.imdecode(jpeg,1),(1080,2340),interpolation=cv2.INTER_NEAREST)
        assert bridge.parse(streamed)['phase']=='game_over'
    playing=cv2.imread(str(ROOT/'artifacts/loss-16668/current-phone-readonly.png'))
    assert not bridge.is_over(playing)
