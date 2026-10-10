from dataclasses import dataclass
import cv2

@dataclass(frozen=True)
class Rect:
    x: int
    y: int
    width: int
    height: int
    def tuple(self): return (self.x,self.y,self.width,self.height)
    def crop(self,frame):
        h,w=frame.shape[:2]
        if min(self.x,self.y)<0 or min(self.width,self.height)<8 or self.x+self.width>w or self.y+self.height>h:
            raise ValueError("Vùng hiệu chỉnh nằm ngoài ảnh hoặc quá nhỏ.")
        return frame[self.y:self.y+self.height,self.x:self.x+self.width]

def suggest_board(frame):
    """Tentative square contour proposal only. User must confirm the actual cell grid."""
    gray=cv2.cvtColor(frame,cv2.COLOR_BGR2GRAY)
    contours,_=cv2.findContours(cv2.Canny(gray,40,120),cv2.RETR_LIST,cv2.CHAIN_APPROX_SIMPLE)
    candidates=[]
    height,width=gray.shape
    for contour in contours:
        x,y,w,h=cv2.boundingRect(contour)
        if w>width*0.4 and h>height*0.15 and 0.9<w/h<1.1:
            candidates.append(Rect(x,y,w,h))
    return max(candidates,key=lambda r:r.width*r.height) if candidates else None
