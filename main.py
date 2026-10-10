import argparse
import sys
from pathlib import Path
def main():
    parser=argparse.ArgumentParser(description="Local puzzle solver; read-only ADB")
    parser.add_argument("--solve",metavar="STATE.json")
    parser.add_argument("--smoke-test",action="store_true")
    args=parser.parse_args()
    if args.solve:
        import json
        from engine.game_state import GameState
        from solver.beam_search import BeamSolver
        state=GameState.from_json(Path(args.solve).read_text(encoding="utf-8-sig"))
        result=BeamSolver().solve(state)
        print(json.dumps({"elapsed_ms":result.elapsed_ms,"explored":result.explored,"depth":result.depth,
            "timed_out":result.timed_out,"plans":[{"value":p.value,"cleared":p.cleared,
            "moves":[{"piece_id":m.piece_id,"row":m.row,"col":m.col} for m in p.moves]} for p in result.plans]},indent=2))
        return
    from PySide6.QtCore import QTimer
    from PySide6.QtGui import QFontDatabase
    from PySide6.QtWidgets import QApplication
    from ui.main_window import MainWindow
    app=QApplication(sys.argv[:1])
    # The Windows offscreen plugin has no system fonts until explicitly registered.
    if not QFontDatabase.families():
        import os
        font=Path(os.environ.get("WINDIR","C:/Windows"))/"Fonts"/"segoeui.ttf"
        if font.exists(): QFontDatabase.addApplicationFont(str(font))
    window=MainWindow()
    window.show()
    if args.smoke_test:
        window.demo()
        window.analyze()
        def finish():
            if window.job:
                QTimer.singleShot(100,finish)
                return
            output=Path.cwd()/"artifacts"
            output.mkdir(exist_ok=True)
            window.grab().save(str(output/"ui-preview.png"))
            app.quit()
        QTimer.singleShot(1200,finish)
    sys.exit(app.exec())
if __name__=="__main__": main()
