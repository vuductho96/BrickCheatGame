"""Observed-frame autopilot. Never invents the next random tray."""
import threading
import time
from dataclasses import dataclass,replace
import cv2
import numpy as np
from engine.simulator import apply_move,is_game_over
from solver.stochastic import StochasticSolver,ShapePrior
from solver.heuristics import SURVIVAL_WEIGHTS

@dataclass(frozen=True)
class AutoMode:
    label: str
    width: int
    budget: float
    drag_seconds: float
    pause: float

MODES={
    "fast":AutoMode("Nhanh",60,.18,.30,.15),
    "balanced":AutoMode("Cân bằng",240,.85,.45,.35),
    "deep":AutoMode("Kỹ",1000,3.0,.65,.65),
}

class AutoStopped(Exception): pass
class PlacementRetry(RuntimeError): pass
class PlacementMismatch(RuntimeError): pass

def grip_cell(cells):
    # Use a real cell nearest the geometric center, never an empty hole.
    center=(sum(r for r,c in cells)/len(cells),sum(c for r,c in cells)/len(cells))
    return min(cells,key=lambda cell:((cell[0]-center[0])**2+(cell[1]-center[1])**2,cell))


def clear_effect_baseline(before,current,state,rows,cols,board):
    """Exclude recoloring of existing cells on predicted clearing lines.

    Empty cells stay unchanged in the baseline, so a new misplaced sprite is
    still detected and cannot disappear into this exclusion.
    """
    if not rows and not cols:return before
    adjusted=before.copy()
    cw,ch=board.width/state.size,board.height/state.size
    for r in range(state.size):
        for c in range(state.size):
            if state.occupied(r,c) and (r in rows or c in cols):
                x0,x1=round(board.x+c*cw),round(board.x+(c+1)*cw)
                y0,y1=round(board.y+r*ch),round(board.y+(r+1)*ch)
                adjusted[y0:y1,x0:x1]=current[y0:y1,x0:x1]
    return adjusted


def unique_clear_target(state,move):
    """Whether this exact set of cleared lines identifies one legal placement."""
    from engine.game_rules import placements,clear_lines
    step=apply_move(state,move)
    if not step.rows and not step.cols:return False
    piece=next(p for p in state.pieces if p.id==move.piece_id)
    candidates=[]
    for r,c,mask in placements(state.size,piece.cells):
        if mask&state.board:continue
        _,rows,cols=clear_lines(state.board|mask,state.size)
        if (rows,cols)==(step.rows,step.cols):candidates.append((r,c))
    return candidates==[(move.row,move.col)]


def match_dragged_piece(frame, template, target, radius=320, color=None, cells=None, baseline=None):
    """Find the lifted piece near its intended cells, not elsewhere on the screen."""
    tx,ty=target
    th,tw=template.shape[:2]
    x0,y0=max(0,int(tx-radius)),max(0,int(ty-radius))
    x1,y1=min(frame.shape[1],int(tx+tw+radius)),min(frame.shape[0],int(ty+th+radius))
    area=frame[y0:y1,x0:x1]
    if area.shape[0]<th or area.shape[1]<tw: raise RuntimeError("Không tìm thấy khối đang kéo")
    template_score,template_point=-1.0,(0,0)
    if float(np.max(np.std(template.astype(float),axis=(0,1))))>3:
        scores=cv2.matchTemplate(area,template,cv2.TM_CCOEFF_NORMED)
        _,template_score,_,template_point=cv2.minMaxLoc(scores)
    if baseline is not None and template_score>=.68:
        bx,by=template_point[0]+x0,template_point[1]+y0
        change=np.linalg.norm(frame[by:by+th,bx:bx+tw].astype(float)-
                              baseline[by:by+th,bx:bx+tw].astype(float),axis=2)>30
        if float(np.mean(change))<.25:
            template_score=-1.0
    if np.isfinite(template_score) and template_score>.80 and not (color and cells):
        return (template_point[0]+x0,template_point[1]+y0),template_score
    if color and cells:
        from vision.piece_tracker import track_pattern
        try:
            point,confidence=track_pattern(area,color,cells,tw,th,
                baseline[y0:y1,x0:x1] if baseline is not None else None,
                (tx-x0,ty-y0))
            return (point[0]+x0,point[1]+y0),confidence
        except RuntimeError as exc:
            # A visually similar template is not evidence of the full colored
            # shape when the pattern tracker reports clipping or missing cells.
            raise RuntimeError("Không theo dõi được toàn bộ khối màu đang kéo") from exc
    score,point=template_score,template_point
    if not np.isfinite(score) or score<.68:
        raise RuntimeError(f"Khối đang kéo chưa rõ ({score:.2f}); Auto đã dừng")
    return (point[0]+x0,point[1]+y0),score

class Autopilot:
    def __init__(self,bridge):
        self.bridge=bridge
        self.guard=threading.Lock()
        self.cancel=threading.Event()
        self.thread=None
        self.mode="balanced"
        self.active=False
        self.message="Auto đang tắt"
        self.moves=0
        self.levels=0
        self.last_search=None
        self.last_move=None
        self.last_verified=False
        self.stage="idle"
        self.pending_move=None
        self.execution=None
        self.last_check=None
        self.anchors={}
        self.sprite_bias={}
        self.recoveries=0
        self.result=None
        self.result_state=None
        self.prior=ShapePrior.load()
        self.solvers={key:StochasticSolver(width=value.width,time_limit=value.budget,prior=self.prior,
            weights=SURVIVAL_WEIGHTS,commit_tray=True,samples={'fast':2,'balanced':4,'deep':16}[key],
            horizon={'fast':1,'balanced':2,'deep':3}[key])
            for key,value in MODES.items()}

    def status(self):
        with self.guard:
            return {"active":self.active,"mode":self.mode,"message":self.message,
                "moves":self.moves,"levels":self.levels,"search":self.last_search,
                "last_move":self.last_move,"verified":self.last_verified,
                "stage":self.stage,"pending_move":self.pending_move,"recoveries":self.recoveries,
                "execution":self.execution,"last_check":self.last_check,
                "modes":{k:{"label":v.label,"width":v.width,"budget_ms":int(v.budget*1000)}
                         for k,v in MODES.items()}}

    def update(self,message,**values):
        with self.guard:
            self.message=message
            for key,value in values.items():setattr(self,key,value)

    def set_mode(self,mode):
        if mode not in MODES:raise ValueError("Chế độ Auto không hợp lệ")
        with self.guard:
            if self.active:raise ValueError("Dừng Auto trước khi đổi chế độ")
            self.mode=mode
            self.result=self.result_state=None
        return self.status()
    def start(self,mode="balanced"):
        if mode not in MODES:raise ValueError("Chế độ Auto không hợp lệ")
        with self.guard:
            if self.active:raise ValueError("Auto đang chạy; dừng trước khi đổi chế độ")
            if not self.bridge.live or not self.bridge.live.status()["live"]:
                raise ValueError("Cần kết nối LIVE trước khi bật Auto")
            if self.bridge.live.pressed:raise ValueError("Thả thao tác tay trước khi bật Auto")
            self.cancel.clear()
            self.mode=mode
            self.active=True
            self.moves=self.levels=0
            self.recoveries=0
            self.last_verified=False
            self.result=self.result_state=None
            self.pending_move=None
            self.execution=self.last_check=None
            self.stage="waiting"
            self.message="Đang đọc bàn và khay hiện tại"
            self.thread=threading.Thread(target=self.run,daemon=True)
            self.thread.start()
        return self.status()

    def stop(self,reason="Đã dừng Auto",wait=False):
        self.cancel.set()
        self.update(reason)
        thread=self.thread
        if wait and thread and thread is not threading.current_thread():thread.join(timeout=5)
        return self.status()

    def check(self):
        if self.cancel.is_set():raise AutoStopped()

    def wait(self,seconds):
        if self.cancel.wait(seconds):raise AutoStopped()

    def touch(self,action,x,y):
        self.check()
        mirror=self.bridge.live
        status=mirror.status()
        mirror.touch(action,round(x*status["width"]/1080),round(y*status["height"]/2340))

    def release(self,cancel=False):
        mirror=self.bridge.live
        if mirror and mirror.pressed:
            mirror.touch(3 if cancel else 1,*mirror.touch_position)

    def move_pointer(self,source,target,seconds):
        steps=max(4,round(seconds/.025))
        for i in range(1,steps+1):
            self.touch(2,source[0]+(target[0]-source[0])*i/steps,
                          source[1]+(target[1]-source[1])*i/steps)
            self.wait(seconds/steps)

    def feedback_snapshot(self,after_sequence):
        mirror=self.bridge.live
        if type(after_sequence) is int and type(getattr(mirror,"sequence",None)) is int:
            deadline=time.monotonic()+1.5
            while mirror.sequence<=after_sequence:
                self.check()
                if time.monotonic()>=deadline:
                    raise PlacementRetry("Đợi khung mới để tự căn lại")
                self.wait(.05)
        return self.bridge.snapshot()

    def record_move(self,event,observed,move,expected,actual=None,details=None):
        # Publish the immutable planned board separately from live observations.
        if event=="planned":
            moves=(move,)
            if self.result_state==observed["state"] and self.result and self.result.plans:
                candidate=self.result.plans[0].moves
                if candidate and candidate[0]==move:moves=candidate
            with self.guard:
                self.execution={"state_id":observed["state_id"],"target":vars(move),
                    "pieces":observed["pieces"],"moves":[vars(m) for m in moves],
                    "before":observed["state"].matrix(),"expected":expected.matrix()}
        elif event in ("verified","mismatch","unverified_game_over","abort_mismatch"):
            with self.guard:
                self.last_check={"outcome":event,"move":vars(move),
                    "expected":expected.matrix(),
                    "actual":actual["state"].matrix() if actual and actual.get("state") else None,
                    "phase":actual.get("phase") if actual else None}
        from capture.adb_capture import ADBCapture
        if not isinstance(getattr(self.bridge,"adb",None),ADBCapture):return
        import json
        from pathlib import Path
        entry={"time":time.time(),"event":event,"move":vars(move),
               "before":observed["state"].to_dict(),"expected":expected.to_dict(),
               "actual":actual["state"].to_dict() if actual and actual.get("state") else None,
               "phase":actual.get("phase") if actual else None,"details":details}
        try:
            with (Path(__file__).parent/"artifacts"/"auto-moves.jsonl").open("a",encoding="utf-8") as stream:
                stream.write(json.dumps(entry,ensure_ascii=False)+"\n")
        except OSError:pass

    def settle_return(self,observed,move):
        """Do not publish a returning sprite as a newly placed block."""
        self.update("Đợi khối trở về khay và kiểm tra bàn",stage="settling",pending_move=None)
        time.sleep(.6)
        deadline=time.monotonic()+4
        actual={}
        matches=0
        while time.monotonic()<deadline:
            try:actual=self.bridge.parse(self.bridge.snapshot())
            except (RuntimeError,ValueError):
                matches=0
            else:
                matches=matches+1 if actual.get("state")==observed["state"] else 0
                if matches>=3:
                    if hasattr(self.bridge,"publish"):self.bridge.publish(actual)
                    return
            time.sleep(.15)
        self.record_move("abort_mismatch",observed,move,observed["state"],actual)
        raise PlacementMismatch("Chưa xác minh bàn và khay sau hủy kéo; Auto đã dừng")

    def perform_move(self,observed,move,profile):
        from web_bridge import BOARD
        try:
            frame=self.bridge.snapshot()
            fresh=self.bridge.parse(frame)
        except (RuntimeError,ValueError) as exc:raise PlacementRetry("Đợi dữ liệu bàn mới trước khi kéo") from exc
        if fresh["state_id"]!=observed["state_id"]:raise PlacementRetry("Bàn đã đổi; đang tính lại từ điện thoại")
        step=apply_move(fresh["state"],move)
        unique_clear=unique_clear_target(fresh["state"],move)
        self.record_move("planned",fresh,move,step.state)
        piece=next(p for p in fresh["pieces"] if p["id"]==move.piece_id)
        # Pick an actual occupied cell; this also supports L/T shapes.
        gr,gc=grip_cell(piece["cells"])
        x,y,w,h=piece["bounds"]
        source=(x+(gc+.5)*w/piece["width"],y+(gr+.5)*h/piece["height"])
        cw,ch=BOARD.width/8,BOARD.height/8
        desired=(BOARD.x+move.col*cw,BOARD.y+move.row*ch)
        template=cv2.resize(frame[y:y+h,x:x+w],
            (round(piece["width"]*cw),round(piece["height"]*ch)),interpolation=cv2.INTER_LINEAR)
        # Initial measured lift on S23+. Visual feedback corrects it for each shape.
        shape=(piece["width"],piece["height"],gr,gc)
        anchor=self.anchors.get(shape,(gc*cw+60,gr*ch+360))
        # Lift away from the edges first: an uncalibrated finger-to-sprite
        # offset can clip the shape before visual feedback has a chance to act.
        safe_origin=(BOARD.x+(BOARD.width-piece["width"]*cw)/2,
                     BOARD.y+(BOARD.height-piece["height"]*ch)/2)
        pointer=(safe_origin[0]+anchor[0],safe_origin[1]+anchor[1])
        pointer=(min(1070,max(10,pointer[0])),min(2300,max(10,pointer[1])))
        feedback_sequence=getattr(self.bridge.live,"sequence",None)
        self.touch(0,*source)
        try:
            self.wait(.08)
            self.move_pointer(source,pointer,profile.drag_seconds)
            self.wait(.45)
            from vision.drop_preview import drop_preview,clear_preview,clear_drop_preview
            from drag_servo import DragServo
            servo=DragServo(desired,(cw,ch),diagonal=True)
            lower=(BOARD.x,BOARD.y)
            upper=(BOARD.x+BOARD.width-piece["width"]*cw,
                   BOARD.y+BOARD.height-piece["height"]*ch)
            tracking_target=safe_origin
            def within_board(position):
                # Two pixels accommodate the quantized 540px video contours.
                return all(lo-2<=value<=hi+2 for value,lo,hi in zip(position,lower,upper))
            def probe(position):
                # At the right edge request a fresh frame by moving inward.
                delta=(2 if position[0]<(lower[0]+upper[0])/2 else -2,0)
                bounded=servo.bound_delta(delta,position,lower,upper,overshoot=2.5)
                return (pointer[0]+bounded[0],pointer[1]+bounded[1])
            def tracked(image):
                baseline=clear_effect_baseline(frame,image,fresh["state"],step.rows,step.cols,BOARD)
                return match_dragged_piece(image,template,tracking_target,
                    radius=500 if servo.previous is None else 320,
                    color=piece["color"],cells=piece["cells"],baseline=baseline)
            def aligned(image):
                try:
                    position,_=tracked(image)
                except RuntimeError:return False
                return within_board(position) and abs(position[0]-desired[0])<cw*.22 and abs(position[1]-desired[1])<ch*.22
            def clear_evidence(image):
                return clear_drop_preview(image,BOARD,piece,move.row,move.col,step.rows,step.cols) or (
                    unique_clear and clear_preview(image,BOARD,step.rows,step.cols))
            confirmed=False
            for _ in range(14):
                self.check()
                held=self.feedback_snapshot(feedback_sequence)
                feedback_sequence=getattr(self.bridge.live,"sequence",None)
                try:
                    visual,confidence=tracked(held)
                except RuntimeError as exc:
                    # Do not probe blindly when the sprite is clipped or lost.
                    raise PlacementRetry("Không thấy toàn bộ khối; trả về khay để căn lại") from exc
                tracking_target=visual
                # Learn from the floating sprite, not its snapped grid footprint.
                measured_delta=servo.observe(pointer,visual,confidence)
                self.anchors[shape]=(pointer[0]-visual[0],pointer[1]-visual[1])
                self.record_move("drag_observed",fresh,move,step.state,
                    details={"pointer":list(pointer),"visual":list(visual),
                             "confidence":float(confidence),"inside":within_board(visual),
                             "sequence":feedback_sequence,"servo_samples":servo.samples})
                preview=None
                pose_ready=within_board(visual) and abs(visual[0]-desired[0])<cw*.22 and abs(visual[1]-desired[1])<ch*.22
                # Require both a visible target footprint and aligned sprite.
                # Clear effects can obscure the footprint, never waive alignment.
                if pose_ready and clear_evidence(held):
                    # Static Android surfaces need not emit another encoded
                    # frame. A one-stream-pixel motion requests fresh evidence.
                    pointer=probe(visual)
                    self.touch(2,*pointer)
                    self.wait(.12)
                    confirmation=self.feedback_snapshot(feedback_sequence)
                    if aligned(confirmation) and clear_evidence(confirmation):
                        confirmed=True
                        break
                    continue
                preview=drop_preview(held,BOARD,piece)
                if preview:
                    origin=(BOARD.x+preview["col"]*cw,BOARD.y+preview["row"]*ch)
                    self.sprite_bias[shape]=(origin[0]-visual[0],origin[1]-visual[1])
                    if (preview["row"],preview["col"])==(move.row,move.col) and pose_ready:
                        pointer=probe(visual)
                        self.touch(2,*pointer)
                        self.wait(.12)
                        confirmation=self.feedback_snapshot(feedback_sequence)
                        again=drop_preview(confirmation,BOARD,piece)
                        if aligned(confirmation) and again and (again["row"],again["col"])==(move.row,move.col):
                            confirmed=True
                            break
                        continue
                    elif (preview["row"],preview["col"])!=(move.row,move.col):
                        dx,dy=(move.col-preview["col"])*cw,(move.row-preview["row"])*ch
                    else:
                        # A gray footprint can lag the moving sprite.
                        dx,dy=measured_delta
                else:
                    dx,dy=measured_delta
                    if abs(dx)<cw*.04 and abs(dy)<ch*.04:
                        # Reveal two edges of the snapped footprint when an
                        # aligned solid sprite covers it entirely. Stay within
                        # the alignment tolerance and move inward at boundaries.
                        dx=cw*.14 if visual[0]<(lower[0]+upper[0])/2 else -cw*.14
                        dy=ch*.14 if visual[1]<(lower[1]+upper[1])/2 else -ch*.14
                # Bound every correction, including preview corrections and
                # excitation motions, by the full shape's predicted footprint.
                dx,dy=servo.bound_delta((dx,dy),visual,lower,upper,overshoot=2.5)
                corrected=(pointer[0]+dx,pointer[1]+dy)
                if not (5<corrected[0]<1075 and 5<corrected[1]<2335):
                    raise PlacementRetry("Vùng thả chưa đúng; đang tính lại")
                feedback_sequence=getattr(self.bridge.live,"sequence",None)
                self.move_pointer(pointer,corrected,.15)
                pointer=corrected
                self.wait(.35)
            if not confirmed:raise PlacementRetry("Chưa xác nhận được ô mục tiêu; đang căn lại cùng vị trí")
            self.record_move("release_authorized",fresh,move,step.state,
                             details={"pointer":list(pointer),"grip":[gr,gc],
                                      "preview":preview,"servo_samples":servo.samples,
                                      "unique_clear_target":unique_clear})
            from capture.adb_capture import ADBCapture
            if isinstance(getattr(self.bridge,"adb",None),ADBCapture):
                from pathlib import Path
                try:cv2.imwrite(str(Path(__file__).parent/"artifacts"/"auto-before-release.png"),held)
                except OSError:pass
            self.release()
        except Exception as exc:
            self.record_move("drag_failed",fresh,move,step.state,
                             details={"type":type(exc).__name__,"error":str(exc),"pointer":list(pointer)})
            from capture.adb_capture import ADBCapture
            from pathlib import Path
            root=Path(__file__).parent/"artifacts"
            try:
                if isinstance(getattr(self.bridge,"adb",None),ADBCapture):
                    cv2.imwrite(str(root/"auto-drag-failure.png"),self.bridge.snapshot())
                    cv2.imwrite(str(root/"auto-drag-template.png"),template)
            except Exception:pass
            # The game treats CANCEL as a drop. Return to the original tray before UP.
            try:
                mirror=self.bridge.live
                status=mirror.status()
                mirror.touch(2,round(source[0]*status["width"]/1080),round(source[1]*status["height"]/2340))
                time.sleep(.1)
                self.release()
            except Exception:self.release(cancel=True)
            if isinstance(getattr(self.bridge,"adb",None),ADBCapture):
                self.settle_return(fresh,move)
            raise
        self.update("Đợi bàn sau thả",stage="settling")
        self.wait(.4)
        deadline=time.monotonic()+6
        verified=False
        actual={}
        while time.monotonic()<deadline:
            self.check()
            try:
                actual=self.bridge.parse(self.bridge.capture_stable())
            except Exception:
                self.update("Đợi hiệu ứng xóa hàng và khay mới")
                self.wait(.2)
                continue
            if actual["phase"]=="level_complete":
                verified=True
            elif actual.get("state"):
                verified=actual["state"].board==step.state.board
                if verified and step.state.pieces:
                    expected={p.id:p.cells for p in step.state.pieces}
                    got={p.id:p.cells for p in actual["state"].pieces}
                    verified=expected==got
            if verified:break
            self.update("Đợi và kiểm tra bàn sau thả")
            self.wait(.2)
        if not verified:
            if actual.get("phase")=="game_over":
                self.record_move("unverified_game_over",fresh,move,step.state,actual)
                raise PlacementMismatch("Ván kết thúc trước khi xác minh ô thả; Auto đã dừng")
            if actual.get("state") and actual["state"].board!=fresh["state"].board and (move.piece_id not in {p.id for p in actual["state"].pieces} or (not step.state.pieces and len(actual["state"].pieces)==3)):
                self.bridge.publish(actual) if hasattr(self.bridge,"publish") else None
                self.record_move("mismatch",fresh,move,step.state,actual)
                self.update("Thả lệch ô dự kiến; Auto dừng để tránh làm hỏng bàn",stage="idle",
                            pending_move=None,last_verified=False)
                raise PlacementMismatch(self.message)
            raise PlacementRetry("Khối chưa được đặt; đang đọc lại bàn")
        self.record_move("verified",fresh,move,step.state,actual)
        if len(fresh['state'].pieces)==1 and actual.get('state') and len(actual['state'].pieces)==3:
            try:self.prior.observe_refill(actual['state'].pieces,
                persist=isinstance(getattr(self.bridge,'adb',None),ADBCapture))
            except OSError:pass  # Disk failure must not undo a verified phone move.
        self.bridge.current=actual
        if hasattr(self.bridge,"publish"):self.bridge.publish(actual)
        self.update("Đã kiểm tra nước đi khớp điện thoại",moves=self.moves+1,last_verified=True,
            last_move={"piece_id":move.piece_id,"row":move.row,"col":move.col},stage="waiting",pending_move=None)
        return actual

    def run(self):
        profile=MODES[self.mode]
        uncertain_since=None
        advance_pending=None
        rejected={}
        retry_rounds={}
        locked_plans={}
        try:
            while True:
                self.check()
                with self.bridge.lock:
                    if self.bridge.live.pressed:raise RuntimeError("Có thao tác tay đang diễn ra; Auto đã dừng")
                    try:
                        observed=self.bridge.parse(self.bridge.capture_stable())
                    except Exception as exc:
                        if uncertain_since is None:uncertain_since=time.monotonic()
                        self.update("Đợi bàn rõ hoặc hiệu ứng kết thúc")
                        # Keep Auto armed across transient frames and ADB reconnects.
                        self.wait(.4)
                        observed=None
                    if observed is not None:
                        uncertain_since=None
                        self.bridge.current=observed
                        if hasattr(self.bridge,"publish"):self.bridge.publish(observed)
                        phase=observed["phase"]
                        if phase=="game_over":
                            self.update("Ván đã thua; Auto dừng, không tự tham gia lại")
                            break
                        if phase=="level_complete":
                            if advance_pending is not None:
                                if time.monotonic()-advance_pending>8:
                                    self.touch(0,540,1880)
                                    self.wait(.05)
                                    self.release()
                                    advance_pending=time.monotonic()
                                self.update("Đợi hiệu ứng chuyển cấp")
                            else:
                                self.update("Đã thắng — chuyển cấp tiếp theo")
                                self.wait(.5)
                                self.touch(0,540,1880)
                                self.wait(.05)
                                self.release()
                                advance_pending=time.monotonic()
                                self.update("Đợi cấp mới")
                                self.wait(1)
                        elif phase=="waiting_for_pieces":
                            self.update("Đợi ba khối mới xuất hiện — không đoán trước")
                            if uncertain_since is None:uncertain_since=time.monotonic()
                        else:
                            if advance_pending is not None:
                                self.update("Đã sang cấp mới",levels=self.levels+1)
                                advance_pending=None
                            solver=self.solvers[self.mode]
                            self.update(f"Đang tính {len(observed['pieces'])} khối hiện tại ({profile.label})")
                            result=solver.solve(observed["state"])
                            self.result_state=observed["state"]
                            self.result=result
                            self.check()
                            if not result.plans:
                                if is_game_over(observed['state']):
                                    self.update("Không còn vị trí hợp lệ cho khay hiện tại; Auto dừng")
                                    break
                                self.update("Đợi bàn mới hoặc màn kết thúc",stage="waiting",pending_move=None)
                                self.wait(1)
                                continue
                            blocked=rejected.setdefault(observed["state_id"],set())
                            # The first recommendation remains the target while
                            # this observed board/tray is unchanged.
                            plan=locked_plans.setdefault(observed["state_id"],result.plans[0])
                            self.result=replace(result,plans=(plan,))
                            if plan.moves[0] in blocked:plan=None
                            if plan is None:
                                rounds=retry_rounds.get(observed["state_id"],0)+1
                                retry_rounds[observed["state_id"]]=rounds
                                if rounds>=3:
                                    self.anchors.clear()
                                    self.sprite_bias.clear()
                                    retry_rounds[observed["state_id"]]=0
                                    blocked.clear()
                                    self.update("Đang tự phục hồi: đọc lại bàn và đo lại độ lệch",stage="waiting",
                                                pending_move=None,recoveries=self.recoveries+1)
                                    self.wait(min(10,2+self.recoveries))
                                    continue
                                blocked.clear()
                                self.update("Đợi đồng bộ và thử lại vị trí",stage="waiting",pending_move=None)
                                self.wait(1)
                                continue
                            self.update("Đang căn ô nhận khối trong game",stage="moving",
                                pending_move={"piece_id":plan.moves[0].piece_id,"row":plan.moves[0].row,"col":plan.moves[0].col},
                                last_verified=False,
                                last_search={"ms":round(result.elapsed_ms),"explored":result.explored,
                                    "depth":plan.depth,"tray_size":len(observed["pieces"]),
                                    "future_samples":result.future_samples,
                                    "future_survived":result.future_survived,
                                    "future_horizon":result.future_horizon,
                                    "timed_out":result.timed_out,"cached":result.cached})
                            try:
                                actual=self.perform_move(observed,plan.moves[0],profile)
                                if actual and actual.get('state') and is_game_over(actual['state']):
                                    self.update("Bàn đã xác minh không còn nước hợp lệ; Auto dừng")
                                    break
                            except OSError:
                                self.update("Đợi kết nối điện thoại; Auto sẽ tiếp tục",stage="waiting",pending_move=None)
                                self.wait(.5)
                            except PlacementRetry as exc:
                                blocked.add(plan.moves[0])
                                self.update(str(exc),stage="waiting",pending_move=None)
                                self.result=self.result_state=None
                                self.wait(.4)
                            except RuntimeError:
                                if self.bridge.live.status().get("live"):raise
                                self.update("Đợi video kết nối lại; Auto sẽ tự tiếp tục",stage="waiting",pending_move=None)
                                self.wait(.5)
                self.wait(profile.pause)
        except AutoStopped:pass
        except Exception as exc:self.update(str(exc))
        finally:
            try:self.release(cancel=True)
            except Exception:pass
            self.update(self.message,active=False,stage="idle",pending_move=None)
