import hashlib
import time
from dataclasses import replace
from pathlib import Path
import cv2
import numpy as np
from PySide6.QtCore import Qt, QThread, QTimer, Signal, Slot
from PySide6.QtWidgets import (QMainWindow,QWidget,QLabel,QPushButton,QVBoxLayout,QHBoxLayout,
    QSplitter,QGroupBox,QPlainTextEdit,QComboBox,QSpinBox,QCheckBox,QFileDialog,QMessageBox,QInputDialog)
from engine.game_state import GameState,Piece
from engine.game_rules import Rules
from engine.simulator import apply_move,is_game_over
from solver.beam_search import BeamSolver
from solver.heuristics import Weights
from capture.adb_capture import ADBCapture
from capture.frame_stabilizer import FrameStabilizer
from vision.board_detector import Rect,suggest_board
from vision.cell_classifier import classify_cells
from vision.piece_detector import detect_piece
from config.settings import load_settings,save_settings
from .board_widget import BoardWidget
from .screen_widget import ScreenWidget
from .move_preview import parse_pieces,format_pieces,describe_move

class Job(QThread):
    result=Signal(object)
    error=Signal(str)
    def __init__(self,fn,parent=None):
        super().__init__(parent)
        self.fn=fn
    def run(self):
        try: self.result.emit(self.fn())
        except Exception as exc: self.error.emit(str(exc))

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings=load_settings()
        self.rules=Rules(self.settings["points_per_cell"],self.settings["points_per_line"])
        self.solver=BeamSolver(self.settings["beam_width"],self.settings["time_limit"],Weights(**self.settings["weights"]),self.rules)
        self.state=GameState(self.settings["size"])
        self.history=[]
        self.plans=()
        self.path=()
        self.cursor=0
        self.confirmed=False
        self.frame=None
        self.frame_stable=False
        self.frame_token=None
        self.last_recognition=None
        self.last_observed=None
        self.job=None
        self.stabilizer=FrameStabilizer()
        self.setWindowTitle("Shopee Puzzle Solver · Local / ADB read-only")
        self.resize(1260,870)
        root=QWidget()
        self.setCentralWidget(root)
        layout=QVBoxLayout(root)
        title=QLabel("SHOPEE  /  PUZZLE LAB")
        title.setStyleSheet("font-size:24px;font-weight:700;color:#36d6ac")
        layout.addWidget(title)
        layout.addWidget(QLabel("Tính nước đi trên PC · bạn tự kéo thả trên điện thoại · luật và điểm số đang giả định"))
        bar=QHBoxLayout()
        self.buttons=[]
        for text,fn in (("Demo",self.demo),("Mở ảnh",self.open_image),("Refresh ADB",self.capture),
                        ("Chọn ADB",self.choose_adb),("Thiết bị",self.choose_device),("Nhận diện",self.recognize),
                        ("Mở JSON",self.load_json),("Lưu JSON",self.save_json)):
            btn=QPushButton(text)
            btn.clicked.connect(fn)
            self.buttons.append(btn)
            bar.addWidget(btn)
        self.live=QCheckBox("Live ADB")
        self.live.toggled.connect(self.toggle_live)
        bar.addWidget(self.live)
        layout.addLayout(bar)
        splitter=QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter,1)
        phone=QGroupBox("Ảnh điện thoại")
        pv=QVBoxLayout(phone)
        self.screen=ScreenWidget()
        self.screen.roi_selected.connect(self.set_roi)
        self.screen.color_selected.connect(self.set_empty_color)
        pv.addWidget(self.screen,1)
        self.roi_mode=QComboBox()
        self.roi_mode.addItems(["Kéo chọn bàn cờ","Kéo chọn khối A","Kéo chọn khối B","Kéo chọn khối C"])
        pv.addWidget(self.roi_mode)
        self.auto_button=QPushButton("Gợi ý vùng bàn cờ")
        self.auto_button.clicked.connect(self.auto_board)
        pv.addWidget(self.auto_button)
        self.pitch=QSpinBox()
        self.pitch.setRange(4,160)
        self.pitch.setValue(self.settings["piece_pitch"])
        self.pitch.valueChanged.connect(self.set_pitch)
        ph=QHBoxLayout()
        ph.addWidget(QLabel("Pitch khối (px)"))
        ph.addWidget(self.pitch)
        pv.addLayout(ph)
        hint=QLabel("Kéo từ mép ô đầu đến mép ô cuối.\nChuột phải vào tâm ô trống để lấy màu nền.\nChọn từng vùng khối A/B/C riêng.")
        hint.setWordWrap(True)
        pv.addWidget(hint)
        splitter.addWidget(phone)
        center=QGroupBox("Bàn cờ hiện tại · bấm ô để sửa")
        cv=QVBoxLayout(center)
        size_row=QHBoxLayout()
        size_row.addWidget(QLabel("Kích thước"))
        self.size_spin=QSpinBox()
        self.size_spin.setRange(2,16)
        self.size_spin.setValue(self.state.size)
        self.size_spin.valueChanged.connect(self.resize_board)
        size_row.addWidget(self.size_spin)
        cv.addLayout(size_row)
        self.board=BoardWidget()
        self.board.cell_clicked.connect(self.toggle_cell)
        cv.addWidget(self.board,1)
        self.editor=QPlainTextEdit()
        self.editor.setPlaceholderText("A:11/11\nB:111\nC:10/11")
        self.editor.setMaximumHeight(110)
        self.editor.textChanged.connect(self.piece_text_changed)
        cv.addWidget(QLabel("Khối: mỗi dòng TÊN:mẫu, / phân cách hàng"))
        cv.addWidget(self.editor)
        self.confirm_button=QPushButton("Áp dụng khối & xác nhận bàn cờ")
        self.confirm_button.clicked.connect(self.confirm)
        cv.addWidget(self.confirm_button)
        splitter.addWidget(center)
        preview=QGroupBox("Gợi ý & mô phỏng")
        vv=QVBoxLayout(preview)
        self.plan_combo=QComboBox()
        self.plan_combo.currentIndexChanged.connect(self.select_plan)
        vv.addWidget(self.plan_combo)
        self.instruction=QLabel("Nạp Demo hoặc nhập bàn cờ để bắt đầu.")
        self.instruction.setWordWrap(True)
        vv.addWidget(self.instruction)
        self.after=BoardWidget(editable=False)
        vv.addWidget(self.after,1)
        self.step_info=QLabel("Kết quả sau bước đang được gợi ý")
        self.step_info.setWordWrap(True)
        vv.addWidget(self.step_info)
        score_note=QLabel("Điểm mô phỏng theo cấu hình; chưa đối chiếu Shopee.")
        score_note.setWordWrap(True)
        vv.addWidget(score_note)
        actions=QHBoxLayout()
        self.analyze_button=QPushButton("Analyze")
        self.analyze_button.clicked.connect(self.analyze)
        self.next_button=QPushButton("Next Move")
        self.next_button.clicked.connect(self.next_move)
        self.undo_button=QPushButton("Undo")
        self.undo_button.clicked.connect(self.undo)
        for b in (self.analyze_button,self.next_button,self.undo_button): actions.addWidget(b)
        vv.addLayout(actions)
        self.metrics=QLabel("Chưa phân tích")
        self.metrics.setWordWrap(True)
        vv.addWidget(self.metrics)
        splitter.addWidget(preview)
        splitter.setSizes([330,450,440])
        self.status=QLabel("ADB qua USB hoặc Wi-Fi đã pair/connect. Chọn adb.exe → Thiết bị → Refresh ADB.")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.timer=QTimer(self)
        self.timer.setInterval(1800)
        self.timer.timeout.connect(self.capture)
        self.setStyleSheet("""
            QMainWindow,QWidget {background:#111b2b;color:#e2e8f1;font-family:'Segoe UI';font-size:13px;}
            QGroupBox {border:1px solid #324157;border-radius:8px;margin-top:12px;padding:12px;}
            QGroupBox::title {subcontrol-origin:margin;left:12px;color:#a9bad0;}
            QPushButton {background:#263950;border:1px solid #3b526d;border-radius:5px;padding:8px;}
            QPushButton:hover {background:#37516e;}
            QPushButton:disabled {color:#66778d;background:#1a2536;}
            QPlainTextEdit,QComboBox,QSpinBox {background:#1b293c;border:1px solid #40516b;padding:5px;}
        """)
        self.render()
        self.update_regions()
    def invalidate(self,unconfirm=True):
        self.plans=()
        self.path=()
        self.cursor=0
        self.plan_combo.blockSignals(True)
        self.plan_combo.clear()
        self.plan_combo.blockSignals(False)
        self.plan_combo.setEnabled(True)
        if unconfirm: self.confirmed=False
        self.instruction.setText("Kiểm tra bàn cờ và khối, sau đó xác nhận rồi Analyze.")
        self.render()
    def sync_editor(self):
        self.editor.blockSignals(True)
        self.editor.setPlainText(format_pieces(self.state.pieces))
        self.editor.blockSignals(False)
    def piece_text_changed(self):
        self.invalidate()
    def toggle_cell(self,row,col):
        self.history.append(self.state)
        self.state=replace(self.state,board=self.state.board ^ (1 << (row*self.state.size+col)))
        self.invalidate()
    def resize_board(self,size):
        self.state=GameState(size)
        self.history.clear()
        self.settings["size"]=size
        self.stabilizer.reset()
        self.frame_stable=False
        self.last_observed=None
        save_settings(self.settings)
        self.invalidate()
    def confirm(self):
        try:
            pieces=parse_pieces(self.editor.toPlainText())
            if any(p.height>self.state.size or p.width>self.state.size for p in pieces):
                raise ValueError("Khối lớn hơn bàn cờ.")
            self.history.append(self.state)
            self.state=replace(self.state,pieces=pieces)
            self.invalidate()
            self.confirmed=True
            self.status.setText("Đã xác nhận thủ công. Có thể Analyze; ảnh nhận diện vẫn cần kiểm tra bằng mắt.")
            self.render()
        except Exception as exc: self.show_error(str(exc))
    def demo(self):
        n=self.state.size
        board=sum(1 << ((n-1)*n+c) for c in range(n-2))
        board|=sum(1 << ((n-2)*n+c) for c in range(min(3,n)))
        pieces=(Piece("A",((0,0),(0,1))),Piece("B",((0,0),(1,0),(1,1))),Piece("C",((0,0),)))
        self.state=GameState(n,board,pieces)
        self.history.clear()
        self.sync_editor()
        self.invalidate()
        self.confirmed=True
        self.status.setText("Demo tổng hợp: Analyze để xem 3 phương án. Không phải dữ liệu Shopee thật.")
        self.render()
    def render(self):
        move=self.path[self.cursor] if self.cursor<len(self.path) else None
        self.board.set_state(self.state,move)
        if move:
            step=apply_move(self.state,move,self.rules)
            self.after.set_state(step.state)
            self.instruction.setText(describe_move(move))
            self.step_info.setText(f"Bước {self.cursor+1}/{len(self.path)} · xóa {len(step.rows)} hàng + {len(step.cols)} cột\nĐiểm mô phỏng +{step.points} → {step.state.score}")
        else:
            self.after.set_state(self.state)
            self.step_info.setText(f"Điểm mô phỏng: {self.state.score}")
        busy=self.job is not None
        self.analyze_button.setEnabled(self.confirmed and bool(self.state.pieces) and not busy)
        self.next_button.setEnabled(move is not None and not busy)
        self.undo_button.setEnabled(bool(self.history) and not busy)
    def start_job(self,fn,handler):
        if self.job is not None: return
        self.job=Job(fn,self)
        self.job.result.connect(handler)
        self.job.error.connect(self.job_error)
        self.job.finished.connect(self.job_finished)
        for widget in [*self.buttons,self.board,self.editor,self.confirm_button,self.size_spin,
                       self.pitch,self.roi_mode,self.auto_button,self.screen,self.plan_combo]:
            widget.setEnabled(False)
        self.render()
        self.job.start()
    @Slot()
    def job_finished(self):
        job=self.job
        self.job=None
        job.deleteLater()
        for widget in [*self.buttons,self.board,self.editor,self.confirm_button,self.size_spin,
                       self.pitch,self.roi_mode,self.auto_button,self.screen]:
            widget.setEnabled(True)
        self.plan_combo.setEnabled(self.cursor==0)
        self.render()
    @Slot(str)
    def job_error(self,message):
        self.live.setChecked(False)
        self.frame_stable=False
        self.invalidate()
        self.status.setText(message)
    def analyze(self):
        if self.job or not self.confirmed or not self.state.pieces: return
        self.live.setChecked(False)
        state=self.state
        self.status.setText("Đang tìm nước đi trong giới hạn thời gian...")
        self.start_job(lambda:self.solver.solve(state),self.analyzed)
    @Slot(object)
    def analyzed(self,result):
        self.plans=result.plans
        self.plan_combo.blockSignals(True)
        self.plan_combo.clear()
        for i,p in enumerate(result.plans):
            self.plan_combo.addItem(f"#{i+1} · đánh giá {p.value:.1f} · {p.depth} bước · {p.cleared} dòng")
        self.plan_combo.blockSignals(False)
        self.metrics.setText(f"{result.elapsed_ms:.0f} ms · {result.explored:,} trạng thái · sâu {result.depth}\n"
            +("Hết ngân sách thời gian; phương án có thể là tiền tố." if result.timed_out else "Beam Search: không bảo đảm tối ưu toàn cục.")
            +(" · cache" if result.cached else ""))
        if result.plans:
            self.select_plan(0)
            self.status.setText("Gợi ý sẵn sàng. Next Move chỉ mô phỏng trên PC; tự đặt khối trên điện thoại.")
        else:
            self.status.setText("Không còn nước hợp lệ theo trạng thái đã xác nhận." if is_game_over(self.state) else "Khay trống: chụp hoặc nhập khối mới.")
    def select_plan(self,index):
        if 0<=index<len(self.plans):
            self.path=self.plans[index].moves
            self.cursor=0
            self.render()
    def next_move(self):
        if self.job or self.cursor>=len(self.path): return
        step=apply_move(self.state,self.path[self.cursor],self.rules)
        self.history.append(self.state)
        self.state=step.state
        self.cursor+=1
        self.plan_combo.setEnabled(False)
        self.sync_editor()
        if self.cursor>=len(self.path):
            self.instruction.setText("Hết phương án. Chụp ảnh để đối chiếu và nạp khối mới.")
        self.status.setText("Đã mô phỏng. Sau khi tự đặt trên điện thoại, Refresh ADB → Nhận diện để đối chiếu.")
        self.render()
    def undo(self):
        if self.job or not self.history: return
        self.state=self.history.pop()
        self.sync_editor()
        self.invalidate()
        self.status.setText("Undo trên PC. Xác nhận lại trạng thái trước khi Analyze.")
    def choose_adb(self):
        path,_=QFileDialog.getOpenFileName(self,"Chọn adb.exe","","ADB (adb.exe)")
        if path:
            self.settings["adb_path"]=path
            save_settings(self.settings)
    def choose_device(self):
        adb=ADBCapture(self.settings["adb_path"])
        self.start_job(adb.devices,self.devices_found)
    @Slot(object)
    def devices_found(self,devices):
        if not devices:
            self.status.setText("Chưa có thiết bị ADB. Ghép nối S23+ bằng adb pair, rồi adb connect với cổng kết nối.")
            return
        serial,ok=QInputDialog.getItem(self,"Chọn thiết bị ADB","USB hoặc Wi-Fi đã kết nối:",devices,0,False)
        if ok:
            self.settings["serial"]=serial
            save_settings(self.settings)
            self.stabilizer.reset()
            self.frame_stable=False
            self.invalidate()
            self.status.setText("Đã chọn "+serial+". Bấm Refresh ADB để chụp màn hình.")
    def toggle_live(self,enabled):
        if enabled:
            self.timer.start()
            self.capture()
        else: self.timer.stop()
    def capture(self):
        if self.job: return
        adb=ADBCapture(self.settings["adb_path"],self.settings.get("serial"))
        def capture_burst():
            frames=[]
            for i in range(3):
                frames.append(adb.screenshot())
                if i<2: time.sleep(0.15)
            return frames
        self.start_job(capture_burst,self.captured)
    @Slot(object)
    def captured(self,frames):
        regions=[r for r in [self.settings.get("board_roi"),*self.settings.get("piece_rois",[])] if r]
        for frame in frames: stable=self.stabilizer.update(frame,regions)
        try:
            self.set_frame(frames[-1],stable)
            self.status.setText("Ảnh ổn định theo ngưỡng cấu hình. Bấm Nhận diện." if stable else "Ảnh đang thay đổi: chưa cho phép nhận diện. Refresh lại khi animation kết thúc.")
        except Exception as exc:
            self.job_error(str(exc))
    def set_frame(self,frame,stable):
        token=hashlib.sha256()
        regions=[r for r in [self.settings.get("board_roi"),*self.settings.get("piece_rois",[])] if r]
        try:
            for region in regions: token.update(Rect(*region).crop(frame).tobytes())
        except ValueError:
            # Let the new screenshot appear so the user can recalibrate its resolution.
            self.settings["board_roi"]=None
            self.settings["piece_rois"]=[]
            save_settings(self.settings)
            self.stabilizer.reset()
            self.last_observed=None
            regions=[]
            token=hashlib.sha256()
        if not regions: token.update(frame.tobytes())
        digest=token.digest()
        if digest!=self.frame_token or not stable:
            self.invalidate()
            self.frame_token=digest
        self.frame,self.frame_stable=frame,stable
        self.screen.set_frame(frame)
        self.update_regions()
    def open_image(self):
        path,_=QFileDialog.getOpenFileName(self,"Mở ảnh","","Ảnh (*.png *.jpg *.jpeg)")
        if not path: return
        self.live.setChecked(False)
        try:
            frame=cv2.imdecode(np.fromfile(path,dtype=np.uint8),cv2.IMREAD_COLOR)
            if frame is None: raise ValueError("Không đọc được ảnh.")
            self.stabilizer.reset()
            self.set_frame(frame,True)
            self.status.setText("Ảnh tĩnh đã mở; không thể kiểm tra animation từ một ảnh.")
        except Exception as exc: self.show_error(str(exc))
    def update_regions(self):
        self.screen.regions=[r for r in [self.settings.get("board_roi"),*self.settings.get("piece_rois",[])] if r]
        self.screen.update()
    def calibration_changed(self):
        self.stabilizer.reset()
        self.frame_token=None
        self.last_observed=None
        self.invalidate()
        save_settings(self.settings)
        self.update_regions()
    def set_roi(self,rect):
        index=self.roi_mode.currentIndex()
        if index==0: self.settings["board_roi"]=list(rect)
        else:
            rois=self.settings["piece_rois"]
            while len(rois)<index: rois.append(None)
            rois[index-1]=list(rect)
        self.calibration_changed()
        self.status.setText("Đã lưu vùng. Kiểm tra kích thước bàn cờ, màu ô trống và pitch khối.")
    def set_empty_color(self,rgb):
        self.settings["empty_rgb"]=list(rgb)
        self.calibration_changed()
        self.status.setText(f"Đã lấy màu ô trống RGB {rgb}.")
    def set_pitch(self,pitch):
        self.settings["piece_pitch"]=pitch
        self.calibration_changed()
    def auto_board(self):
        if self.frame is None: return
        candidate=suggest_board(self.frame)
        if candidate:
            self.roi_mode.setCurrentIndex(0)
            self.set_roi(candidate.tuple())
            self.status.setText("Vùng tự động chỉ là đề xuất. Kéo sửa để vùng bao đúng toàn bộ lưới ô.")
        else: self.status.setText("Không có vùng vuông phù hợp; kéo chọn bàn cờ thủ công.")
    def recognize(self):
        if self.frame is None: return self.show_error("Chưa có ảnh.")
        if not self.frame_stable: return self.show_error("Ảnh chưa ổn định. Chụp lại sau animation.")
        if not self.settings["board_roi"]: return self.show_error("Kéo chọn vùng bàn cờ trước.")
        try:
            result=classify_cells(self.frame,Rect(*self.settings["board_roi"]),self.state.size,
                self.settings["empty_rgb"],self.settings["color_tolerance"])
            pieces,issues=[],[]
            rois=self.settings["piece_rois"]
            for i,roi in enumerate(rois):
                if not roi: issues.append(f"Thiếu vùng khối {chr(65+i)}"); continue
                try: pieces.append(detect_piece(self.frame,Rect(*roi),chr(65+i),self.settings["piece_pitch"]))
                except ValueError as exc: issues.append(str(exc))
            if not rois: issues.append("Chưa hiệu chỉnh khay: nhập toàn bộ khối thủ công.")
            if result.ambiguous: issues.append(f"{len(result.ambiguous)} ô không chắc chắn: "+str([(r+1,c+1) for r,c in result.ambiguous]))
            match=result.board==self.state.board
            changed=self.last_observed is not None and result.board!=self.last_observed
            self.last_observed=result.board
            self.history.append(self.state)
            self.state=GameState(self.state.size,result.board,tuple(pieces),self.state.score)
            self.last_recognition=result
            self.sync_editor()
            self.invalidate()
            message=("Bàn cờ ảnh khớp mô phỏng." if match else "Bàn cờ ảnh khác mô phỏng; đã nạp để bạn sửa.")
            if changed: message+=" Phát hiện bàn cờ thay đổi."
            self.status.setText(message+" "+(" | ".join(issues) if issues else "Đã nhận diện các vùng cấu hình.")+" Kiểm tra toàn bộ ô/khối rồi xác nhận.")
        except Exception as exc: self.show_error(str(exc))
    def load_json(self):
        path,_=QFileDialog.getOpenFileName(self,"Mở GameState","","JSON (*.json)")
        if not path: return
        try:
            state=GameState.from_json(Path(path).read_text(encoding="utf-8-sig"))
            if len(state.pieces)>6: raise ValueError("Tối đa 6 khối.")
            self.size_spin.blockSignals(True)
            self.size_spin.setValue(state.size)
            self.size_spin.blockSignals(False)
            self.state=state
            self.history.clear()
            self.sync_editor()
            self.invalidate()
        except Exception as exc: self.show_error(str(exc))
    def save_json(self):
        path,_=QFileDialog.getSaveFileName(self,"Lưu GameState","state.json","JSON (*.json)")
        if path:
            try: Path(path).write_text(self.state.to_json(),encoding="utf8")
            except Exception as exc: self.show_error(str(exc))
    def show_error(self,message):
        QMessageBox.warning(self,"Kiểm tra dữ liệu",message)
    def closeEvent(self,event):
        self.timer.stop()
        if self.job:
            event.ignore()
            self.status.setText("Đang hoàn tất công việc nền; đóng lại khi xong.")
            return
        super().closeEvent(event)
