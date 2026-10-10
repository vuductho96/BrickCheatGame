import os
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from ui.main_window import MainWindow
from ui.move_preview import parse_pieces,format_pieces

def test_manual_edits_invalidate_plan_and_undo_restores():
    app=QApplication.instance() or QApplication([])
    window=MainWindow()
    window.demo()
    initial=window.state
    window.toggle_cell(0,0)
    assert window.state.board!=initial.board
    assert not window.confirmed and not window.analyze_button.isEnabled()
    window.undo()
    assert window.state==initial
    window.confirm()
    assert window.confirmed
    window.analyze()
    for _ in range(200):
        QTest.qWait(20)
        if window.job is None: break
    assert window.job is None and window.plans
    assert window.next_button.isEnabled()
    window.next_move()
    assert len(window.state.pieces)==2
    assert not window.plan_combo.isEnabled()
    window.undo()
    assert len(window.state.pieces)==3 and not window.path
    window.close()

def test_piece_editor_roundtrip():
    pieces=parse_pieces("A:11/01\nB:1")
    assert parse_pieces(format_pieces(pieces))==pieces
