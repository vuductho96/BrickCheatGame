from PySide6.QtCore import Qt, Signal, QRectF
from PySide6.QtGui import QPainter, QColor
from PySide6.QtWidgets import QWidget

class BoardWidget(QWidget):
    cell_clicked=Signal(int,int)
    def __init__(self,editable=True):
        super().__init__()
        self.state=None
        self.move=None
        self.editable=editable
        self.setMinimumSize(260,260)
    def set_state(self,state,move=None):
        self.state,self.move=state,move
        self.update()
    def geometry_grid(self):
        side=min(self.width()-44,self.height()-44)
        return (self.width()-side)/2+10,(self.height()-side)/2+10,side
    def paintEvent(self,event):
        if self.state is None: return
        p=QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        x,y,side=self.geometry_grid()
        cell=side/self.state.size
        highlights=set()
        if self.move:
            piece=next((a for a in self.state.pieces if a.id==self.move.piece_id),None)
            if piece: highlights={(self.move.row+r,self.move.col+c) for r,c in piece.cells}
        for i in range(self.state.size):
            p.setPen(QColor("#98a6bb"))
            p.drawText(QRectF(x+i*cell,y-24,cell,22),Qt.AlignmentFlag.AlignCenter,str(i+1))
            p.drawText(QRectF(x-26,y+i*cell,22,cell),Qt.AlignmentFlag.AlignCenter,str(i+1))
        for r in range(self.state.size):
            for c in range(self.state.size):
                color="#6878e3" if self.state.occupied(r,c) else "#253347"
                if (r,c) in highlights: color="#36d6ac"
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(color))
                p.drawRoundedRect(QRectF(x+c*cell+2,y+r*cell+2,cell-4,cell-4),5,5)
        p.end()
    def mousePressEvent(self,event):
        if not self.editable or self.state is None or event.button()!=Qt.MouseButton.LeftButton: return
        x,y,side=self.geometry_grid()
        pos=event.position()
        col=int((pos.x()-x)/(side/self.state.size))
        row=int((pos.y()-y)/(side/self.state.size))
        if x<=pos.x()<x+side and y<=pos.y()<y+side: self.cell_clicked.emit(row,col)
