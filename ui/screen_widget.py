from PySide6.QtCore import Qt, Signal, QRect
from PySide6.QtGui import QPainter, QColor, QPen, QImage
from PySide6.QtWidgets import QWidget
import cv2

class ScreenWidget(QWidget):
    roi_selected=Signal(object)
    color_selected=Signal(object)
    def __init__(self):
        super().__init__()
        self.frame=None
        self.image=None
        self.regions=[]
        self.start=None
        self.end=None
        self.setMinimumSize(270,380)
    def set_frame(self,frame):
        self.frame=frame
        rgb=cv2.cvtColor(frame,cv2.COLOR_BGR2RGB)
        h,w=rgb.shape[:2]
        self.image=QImage(rgb.data,w,h,rgb.strides[0],QImage.Format.Format_RGB888).copy()
        self.update()
    def image_rect(self):
        if self.image is None: return QRect()
        scaled=self.image.size().scaled(self.size(),Qt.AspectRatioMode.KeepAspectRatio)
        return QRect((self.width()-scaled.width())//2,(self.height()-scaled.height())//2,scaled.width(),scaled.height())
    def source_point(self,point):
        rect=self.image_rect()
        if not rect.contains(point) or self.frame is None: return None
        h,w=self.frame.shape[:2]
        return int((point.x()-rect.x())*w/rect.width()),int((point.y()-rect.y())*h/rect.height())
    def paintEvent(self,event):
        p=QPainter(self)
        if self.image is None:
            p.setPen(QColor("#98a6bb"))
            p.drawText(self.rect(),Qt.AlignmentFlag.AlignCenter,"Chụp ADB hoặc mở ảnh PNG / JPG")
        else:
            dest=self.image_rect()
            p.drawImage(dest,self.image)
            h,w=self.frame.shape[:2]
            for i,(x,y,rw,rh) in enumerate(self.regions):
                p.setPen(QPen(QColor("#36d6ac" if i==0 else "#ffbf69"),2))
                p.drawRect(QRect(dest.x()+int(x*dest.width()/w),dest.y()+int(y*dest.height()/h),int(rw*dest.width()/w),int(rh*dest.height()/h)))
            if self.start is not None and self.end is not None:
                p.setPen(QPen(QColor("#ffffff"),2,Qt.PenStyle.DashLine))
                p.drawRect(QRect(self.start,self.end).normalized())
        p.end()
    def mousePressEvent(self,event):
        if self.frame is None: return
        point=event.position().toPoint()
        source=self.source_point(point)
        if source is None: return
        if event.button()==Qt.MouseButton.RightButton:
            x,y=source
            self.color_selected.emit(tuple(int(v) for v in self.frame[y,x,::-1]))
        elif event.button()==Qt.MouseButton.LeftButton:
            self.start=self.end=point
            self.update()
    def mouseMoveEvent(self,event):
        if self.start is not None:
            self.end=event.position().toPoint()
            self.update()
    def mouseReleaseEvent(self,event):
        if self.start is None: return
        a,b=self.source_point(self.start),self.source_point(event.position().toPoint())
        self.start=self.end=None
        self.update()
        if a and b:
            x,y=min(a[0],b[0]),min(a[1],b[1])
            w,h=abs(a[0]-b[0]),abs(a[1]-b[1])
            if min(w,h)>=8: self.roi_selected.emit((x,y,w,h))
