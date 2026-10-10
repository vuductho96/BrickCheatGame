from dataclasses import dataclass
import numpy as np

@dataclass(frozen=True)
class BoardRecognition:
    board: int
    ambiguous: tuple[tuple[int,int],...]
    distances: tuple[tuple[float,...],...]

def classify_cells(frame,rect,size,empty_rgb,tolerance=40,margin=10):
    crop=rect.crop(frame)
    h,w=crop.shape[:2]
    if min(h,w)<size*4: raise ValueError("Vùng bàn cờ quá nhỏ cho kích thước lưới.")
    board,ambiguous,distances=0,[],[]
    empty_bgr=np.array(empty_rgb[::-1],dtype=float)
    for r in range(size):
        row=[]
        for c in range(size):
            y0,y1=int((r+0.3)*h/size),int((r+0.7)*h/size)
            x0,x1=int((c+0.3)*w/size),int((c+0.7)*w/size)
            patch=crop[y0:y1,x0:x1].reshape(-1,3)
            color=np.median(patch,axis=0)
            distance=float(np.linalg.norm(color-empty_bgr))
            variation=float(np.median(np.linalg.norm(patch-color,axis=1)))
            # A gem/icon may vary strongly in color while every pixel is clearly occupied.
            occupied_fraction=float(np.mean(np.linalg.norm(patch-empty_bgr,axis=1)>tolerance+margin))
            if abs(distance-tolerance)<=margin or (variation>25 and occupied_fraction<.95): ambiguous.append((r,c))
            if distance>tolerance: board|=1 << (r*size+c)
            row.append(distance)
        distances.append(tuple(row))
    return BoardRecognition(board,tuple(ambiguous),tuple(distances))
