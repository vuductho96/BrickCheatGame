import math
from PySide6.QtCore import Qt,QRectF,QPointF,Signal
from PySide6.QtGui import QPainter,QColor,QPen,QLinearGradient,QPolygonF,QFont
from PySide6.QtWidgets import QWidget
from engine.game_rules import placements
from engine.simulator import Move

class GameCanvas(QWidget):
    dropped=Signal(object)
    invalid_drop=Signal()
    restart=Signal()
    def __init__(self,session):
        super().__init__()
        self.session=session
        self.hint=None
        self.show_hint=True
        self.drag=None
        self.drag_pos=None
        self.hotspot=(0,0)
        self.setMinimumSize(430,540)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    def board_rect(self):
        side=min(self.width()-76,self.height()-180)
        return QRectF((self.width()-side)/2,34,side,side)
    def tray_rect(self):
        board=self.board_rect()
        return QRectF(board.x(),board.bottom()+32,board.width(),110)
    def piece_rects(self):
        tray=self.tray_rect()
        slot_width=tray.width()/3
        cell=min(33,slot_width/5)
        result={}
        for index,piece in enumerate(self.session.state.pieces):
            x=tray.x()+index*slot_width+(slot_width-piece.width*cell)/2
            y=tray.y()+24+(65-piece.height*cell)/2
            result[piece.id]=(QRectF(x,y,piece.width*cell,piece.height*cell),cell,index)
        return result
    def target_move(self):
        if self.drag is None or self.drag_pos is None: return None
        board=self.board_rect()
        cell=board.width()/self.session.state.size
        # Preserve the grabbed block as the cursor's anchor while scaling from tray to board.
        col=math.floor((self.drag_pos.x()-board.x())/cell-self.hotspot[1])
        row=math.floor((self.drag_pos.y()-board.y())/cell-self.hotspot[0])
        return Move(self.drag.id,row,col)
    def valid(self,move):
        if move is None: return False
        piece=next((p for p in self.session.state.pieces if p.id==move.piece_id),None)
        return piece is not None and any(r==move.row and c==move.col and not mask&self.session.state.board
            for r,c,mask in placements(self.session.size,piece.cells))
    def draw_block(self,p,rect,color,opacity=1.0):
        p.save()
        p.setOpacity(opacity)
        base=QColor(color)
        gradient=QLinearGradient(rect.topLeft(),rect.bottomRight())
        gradient.setColorAt(0,base.lighter(130))
        gradient.setColorAt(1,base.darker(110))
        p.setBrush(gradient)
        p.setPen(QPen(base.darker(160),1))
        p.drawRect(rect)
        bevel=min(9,rect.width()*0.17)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(base.lighter(165))
        p.drawPolygon(QPolygonF([rect.topLeft(),rect.topRight(),
            QPointF(rect.right()-bevel,rect.top()+bevel),QPointF(rect.left()+bevel,rect.top()+bevel)]))
        p.setBrush(base.darker(150))
        p.drawPolygon(QPolygonF([rect.bottomLeft(),rect.bottomRight(),
            QPointF(rect.right()-bevel,rect.bottom()-bevel),QPointF(rect.left()+bevel,rect.bottom()-bevel)]))
        p.restore()
    def draw_shape(self,p,piece,rect,cell,color,opacity=1.0):
        for r,c in piece.cells:
            self.draw_block(p,QRectF(rect.x()+c*cell+1,rect.y()+r*cell+1,cell-2,cell-2),color,opacity)
    def paintEvent(self,event):
        p=QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        background=QLinearGradient(0,0,0,self.height())
        background.setColorAt(0,QColor("#083768"))
        background.setColorAt(1,QColor("#042747"))
        p.fillRect(self.rect(),background)
        board=self.board_rect()
        n=self.session.size
        cell=board.width()/n
        p.fillRect(board,QColor("#073e35"))
        p.setPen(QPen(QColor("#17c48d"),4))
        p.drawRect(board.adjusted(-5,-5,5,5))
        for i in range(n):
            p.setPen(QColor("#80afa9"))
            p.drawText(QRectF(board.x()+i*cell,board.y()-27,cell,24),Qt.AlignmentFlag.AlignCenter,str(i+1))
            p.drawText(QRectF(board.x()-29,board.y()+i*cell,24,cell),Qt.AlignmentFlag.AlignCenter,str(i+1))
        for r in range(n):
            for c in range(n):
                index=r*n+c
                rect=QRectF(board.x()+c*cell+1,board.y()+r*cell+1,cell-2,cell-2)
                p.setPen(QPen(QColor("#06352f"),2))
                p.setBrush(QColor("#083f37"))
                p.drawRect(rect)
                color=self.session.colors[index]
                if color: self.draw_block(p,rect,color)
        if self.show_hint and self.hint and not self.drag:
            piece=next((q for q in self.session.state.pieces if q.id==self.hint.piece_id),None)
            if piece:
                for r,c in piece.cells:
                    rect=QRectF(board.x()+(self.hint.col+c)*cell+3,board.y()+(self.hint.row+r)*cell+3,cell-6,cell-6)
                    p.fillRect(rect,QColor(255,239,118,45))
                    p.setPen(QPen(QColor("#ffed81"),2,Qt.PenStyle.DashLine))
                    p.drawRect(rect)
        tray=self.tray_rect()
        p.fillRect(tray,QColor("#071b43"))
        p.setPen(QPen(QColor("#44759b"),2))
        p.drawRect(tray)
        for identity,(rect,small,index) in self.piece_rects().items():
            piece=next(q for q in self.session.state.pieces if q.id==identity)
            if self.hint and self.show_hint and identity==self.hint.piece_id:
                p.setPen(QPen(QColor("#ffed81"),2))
                p.drawRoundedRect(rect.adjusted(-9,-9,9,9),8,8)
            p.setPen(QColor("#9bbad3"))
            p.drawText(QRectF(tray.x()+index*tray.width()/3,tray.y()+2,tray.width()/3,19),
                       Qt.AlignmentFlag.AlignCenter,["TRÁI","GIỮA","PHẢI"][index])
            self.draw_shape(p,piece,rect,small,self.session.piece_colors[identity],0.25 if self.drag and identity==self.drag.id else 1)
        if self.drag and self.drag_pos:
            move=self.target_move()
            valid=self.valid(move)
            rect=QRectF(self.drag_pos.x()-self.hotspot[1]*cell,self.drag_pos.y()-self.hotspot[0]*cell,
                        self.drag.width*cell,self.drag.height*cell)
            if valid:
                rect.moveTopLeft(QPointF(board.x()+move.col*cell,board.y()+move.row*cell))
            self.draw_shape(p,self.drag,rect,cell,self.session.piece_colors[self.drag.id] if valid else "#e55565",0.78)
        if self.session.over:
            p.fillRect(self.rect(),QColor(0,0,0,185))
            p.setPen(QColor("#ffffff"))
            font=QFont("Segoe UI",25,QFont.Weight.Bold)
            p.setFont(font)
            p.drawText(board,Qt.AlignmentFlag.AlignCenter,"HẾT NƯỚC ĐI")
            p.setFont(QFont("Segoe UI",12))
            p.drawText(board.adjusted(0,80,0,80),Qt.AlignmentFlag.AlignCenter,"Bấm Ván mới để chơi tiếp · hoặc Undo")
        p.end()
    def mousePressEvent(self,event):
        if event.button()!=Qt.MouseButton.LeftButton or self.session.over: return
        pos=event.position()
        for identity,(rect,cell,index) in self.piece_rects().items():
            if rect.contains(pos):
                piece=next(q for q in self.session.state.pieces if q.id==identity)
                r=int((pos.y()-rect.y())/cell)
                c=int((pos.x()-rect.x())/cell)
                if (r,c) not in piece.cells: continue
                self.drag=piece
                self.hotspot=((pos.y()-rect.y())/cell,(pos.x()-rect.x())/cell)
                self.drag_pos=pos
                self.setCursor(Qt.CursorShape.ClosedHandCursor)
                self.update()
                return
    def mouseMoveEvent(self,event):
        if self.drag:
            self.drag_pos=event.position()
            self.update()
    def mouseReleaseEvent(self,event):
        if not self.drag: return
        self.drag_pos=event.position()
        move=self.target_move()
        valid=self.valid(move)
        self.cancel_drag()
        if valid: self.dropped.emit(move)
        else: self.invalid_drop.emit()
    def cancel_drag(self):
        self.drag=None
        self.drag_pos=None
        self.unsetCursor()
        self.update()
    def keyPressEvent(self,event):
        if event.key()==Qt.Key.Key_Escape: self.cancel_drag()
        else: super().keyPressEvent(event)
