from pathlib import Path
from PySide6.QtCore import Qt,QThread,QTimer,Signal,Slot
from PySide6.QtWidgets import (QMainWindow,QWidget,QVBoxLayout,QHBoxLayout,QLabel,
    QPushButton,QCheckBox,QMessageBox,QGroupBox)
from engine.session import PlaySession,PALETTE
from engine.game_rules import Rules
from solver.beam_search import BeamSolver
from solver.heuristics import Weights
from config.settings import load_settings
from .game_canvas import GameCanvas

class HintJob(QThread):
    ready=Signal(object,object)
    failed=Signal(str)
    def __init__(self,solver,state,parent):
        super().__init__(parent)
        self.solver,self.state=solver,state
    def run(self):
        try: self.ready.emit(self.state,self.solver.solve(self.state))
        except Exception as exc: self.failed.emit(str(exc))

class GameWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings=load_settings()
        self.rules=Rules(self.settings["points_per_cell"],self.settings["points_per_line"])
        self.session=PlaySession(size=8,rules=self.rules)
        self.solver=BeamSolver(self.settings["beam_width"],self.settings["time_limit"],
                               Weights(**self.settings["weights"]),self.rules)
        self.job=None
        self.pending=False
        self.plans=()
        self.toolbox=None
        self.setWindowTitle("Xếp Gạch · Chơi trên PC")
        self.resize(1000,820)
        self.setMinimumSize(800,670)
        root=QWidget()
        self.setCentralWidget(root)
        outer=QVBoxLayout(root)
        header=QHBoxLayout()
        title=QLabel("XẾP GẠCH")
        title.setStyleSheet("font-size:28px;font-weight:800;color:#b5f58c")
        header.addWidget(title)
        header.addStretch()
        self.score=QLabel()
        self.score.setStyleSheet("font-size:18px;font-weight:600;color:#ffeb7b")
        header.addWidget(self.score)
        outer.addLayout(header)
        content=QHBoxLayout()
        outer.addLayout(content,1)
        self.canvas=GameCanvas(self.session)
        self.canvas.dropped.connect(self.drop)
        self.canvas.invalid_drop.connect(self.bad_drop)
        content.addWidget(self.canvas,1)
        panel=QWidget()
        panel.setFixedWidth(280)
        pv=QVBoxLayout(panel)
        heading=QLabel("GỢI Ý TIẾP THEO")
        heading.setStyleSheet("font-size:13px;letter-spacing:2px;color:#79d6c0")
        pv.addWidget(heading)
        self.hint_text=QLabel("Đang tính nước đi...")
        self.hint_text.setWordWrap(True)
        self.hint_text.setStyleSheet("font-size:20px;font-weight:600")
        pv.addWidget(self.hint_text)
        self.hint_detail=QLabel()
        self.hint_detail.setWordWrap(True)
        self.hint_detail.setStyleSheet("color:#b0c8da")
        pv.addWidget(self.hint_detail)
        self.plan_buttons=[]
        for index in range(3):
            button=QPushButton(f"Phương án {index+1}")
            button.clicked.connect(lambda checked=False,i=index:self.select_plan(i))
            pv.addWidget(button)
            self.plan_buttons.append(button)
        self.show_hints=QCheckBox("Hiện vị trí gợi ý")
        self.show_hints.setChecked(True)
        self.show_hints.toggled.connect(self.toggle_hint)
        pv.addWidget(self.show_hints)
        pv.addSpacing(15)
        self.message=QLabel("Giữ chuột trên khối, kéo vào bàn rồi thả.\nÔ viền vàng là nước được gợi ý.")
        self.message.setWordWrap(True)
        pv.addWidget(self.message)
        pv.addStretch()
        for label,fn in (("Ván mới",self.new_game),("Undo",self.undo),("Nạp bàn điện thoại",self.load_phone),
                         ("Công cụ ADB / chỉnh bàn",self.open_toolbox)):
            button=QPushButton(label)
            button.clicked.connect(fn)
            pv.addWidget(button)
            if label=="Undo": self.undo_button=button
        self.stats=QLabel()
        self.stats.setWordWrap(True)
        self.stats.setStyleSheet("color:#7fa5c0;font-size:12px")
        pv.addWidget(self.stats)
        content.addWidget(panel)
        note=QLabel("Kéo–thả bằng chuột • Esc hủy kéo • Điểm mô phỏng; khối mới do app tạo")
        note.setStyleSheet("color:#90b0c8;font-size:12px")
        outer.addWidget(note)
        self.setStyleSheet("""
            QMainWindow,QWidget {background:#082647;color:#e9f1fa;font-family:'Segoe UI';font-size:14px;}
            QPushButton {background:#133e63;border:1px solid #376081;border-radius:8px;padding:12px;text-align:left;}
            QPushButton:hover {background:#205783;border-color:#6fe0bc;}
            QPushButton:disabled {color:#66849d;background:#102d4a;}
            QCheckBox {padding:8px 0;}
        """)
        self.debounce=QTimer(self)
        self.debounce.setSingleShot(True)
        self.debounce.setInterval(80)
        self.debounce.timeout.connect(self.start_analysis)
        self.state_changed()
    def state_changed(self):
        self.canvas.cancel_drag()
        self.canvas.hint=None
        self.plans=()
        for button in self.plan_buttons: button.setEnabled(False)
        self.score.setText(f"Điểm {self.session.state.score}  ·  {self.session.lines} dòng")
        self.undo_button.setEnabled(bool(self.session.history))
        if self.session.over:
            self.hint_text.setText("Hết nước đi")
            self.hint_detail.setText("Không còn vị trí đặt được các khối trong khay.")
            self.pending=False
        else:
            self.hint_text.setText("Đang tính nước đi...")
            self.hint_detail.setText("Bạn vẫn có thể kéo–thả trong lúc app tính.")
            self.pending=True
            self.debounce.start()
        self.canvas.update()
    def start_analysis(self):
        if self.job or not self.pending or self.session.over: return
        self.pending=False
        self.job=HintJob(self.solver,self.session.state,self)
        self.job.ready.connect(self.on_analysis)
        self.job.failed.connect(self.on_failure)
        self.job.finished.connect(self.on_finished)
        self.job.start()
    @Slot(object,object)
    def on_analysis(self,state,result):
        # Ignore a result for the board before the user's latest drop/Undo/new game.
        if state!=self.session.state: return
        self.plans=result.plans
        self.stats.setText(f"{result.elapsed_ms:.0f} ms · {result.explored:,} trạng thái\n"
                           +("Tìm kiếm trong giới hạn thời gian" if result.timed_out else f"Đã xét chuỗi {result.depth} bước"))
        for i,button in enumerate(self.plan_buttons):
            button.setEnabled(i<len(self.plans))
            if i<len(self.plans):
                p=self.plans[i]
                button.setText(f"#{i+1}   {p.depth} bước · {p.cleared} dòng xóa")
        if self.plans: self.select_plan(0)
    @Slot(str)
    def on_failure(self,message):
        self.hint_text.setText("Chưa tính được gợi ý")
        self.hint_detail.setText(message)
    @Slot()
    def on_finished(self):
        previous=self.job
        self.job=None
        previous.deleteLater()
        if self.pending: self.debounce.start()
    def select_plan(self,index):
        if not 0<=index<len(self.plans): return
        plan=self.plans[index]
        move=plan.moves[0]
        self.canvas.hint=move
        slot=self.session.slots.index(move.piece_id)
        name=("bên trái","ở giữa","bên phải")[slot]
        self.hint_text.setText(f"Khối {name}\n→ Hàng {move.row+1}, cột {move.col+1}")
        self.hint_detail.setText("Đặt góc trên trái của khối vào ô viền vàng.\n"+f"Chuỗi gợi ý đặt được {plan.depth} khối, xóa {plan.cleared} hàng/cột.")
        self.canvas.update()
    def toggle_hint(self,enabled):
        self.canvas.show_hint=enabled
        self.canvas.update()
    def drop(self,move):
        try:
            step=self.session.place(move)
            count=len(step.rows)+len(step.cols)
            self.message.setText(f"+{step.points} điểm"+(f" · Xóa {count} dòng!" if count else " · Đã đặt khối")
                                 +"\nGợi ý tự cập nhật cho bàn mới.")
            self.state_changed()
        except ValueError:
            self.bad_drop()
    def bad_drop(self):
        self.message.setText("Chưa đặt được: khối cần nằm trong bàn và không chồng ô đã có.")
    def undo(self):
        if self.session.undo():
            self.message.setText("Đã lùi một nước. Khay khối và bàn cờ được khôi phục.")
            self.state_changed()
    def new_game(self):
        self.session.new_game()
        self.message.setText("Ván mới. Kéo khối vào bàn để bắt đầu.")
        self.state_changed()
    def demo(self):
        from engine.game_state import GameState,Piece
        grid=((0,0,0,1,1,0,0,0),(0,1,0,1,1,0,1,0),(1,1,0,1,1,0,1,1),
              (0,)*8,(0,)*8,(0,0,0,1,1,0,0,0),(0,0,1,0,0,1,0,0),(0,)*8)
        board=sum(v << (r*8+c) for r,row in enumerate(grid) for c,v in enumerate(row))
        pieces=(Piece("A",((0,0),(0,1),(1,0),(1,1))),
                Piece("B",tuple((r,c) for r in range(2) for c in range(3))),
                Piece("C",tuple((r,c) for r in range(2) for c in range(3))))
        self.session.load(GameState(8,board,pieces),piece_colors={"A":"#06c5e8","B":"#a449db","C":"#62d700"})
        self.message.setText("Bàn mẫu từ ảnh S23+ đã chụp. Bạn chơi tiếp trên PC.")
        self.state_changed()
    def analyze(self):
        self.pending=True
        self.start_analysis()
    def open_toolbox(self):
        if self.toolbox is None:
            from .main_window import MainWindow
            self.toolbox=MainWindow()
        self.toolbox.show()
        self.toolbox.raise_()
    def load_phone(self):
        self.open_toolbox()
        self.toolbox.status.setText("Refresh ADB → hiệu chỉnh vùng → Nhận diện → xác nhận. Đóng cửa sổ này để nạp bàn sang simulator.")
        # A separate explicit import button makes the selected state reviewable.
        if not hasattr(self.toolbox,"import_to_game"):
            button=QPushButton("Chơi bàn này trên PC")
            button.clicked.connect(self.import_toolbox)
            self.toolbox.centralWidget().layout().addWidget(button)
            self.toolbox.import_to_game=button
    def import_toolbox(self):
        if not self.toolbox.confirmed:
            self.toolbox.show_error("Xác nhận bàn cờ và đủ khối trước khi nạp.")
            return
        if len(self.toolbox.state.pieces)>3:
            self.toolbox.show_error("Màn chơi hỗ trợ tối đa 3 khối trong khay.")
            return
        self.session.load(self.toolbox.state)
        self.toolbox.hide()
        self.state_changed()
    def closeEvent(self,event):
        self.debounce.stop()
        if self.job:
            event.ignore()
            self.message.setText("Đang hoàn tất gợi ý, bạn đóng lại sau một chút.")
            return
        if self.toolbox:
            if self.toolbox.job:
                event.ignore()
                self.message.setText("Công cụ ADB đang chụp ảnh; đóng lại khi xong.")
                return
            self.toolbox.close()
        super().closeEvent(event)
