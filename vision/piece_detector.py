"""Read arbitrary colorful cell patterns on a calibrated tray grid."""
import cv2
import numpy as np
from engine.game_state import Piece

def detect_piece(frame,rect,piece_id,pitch,min_saturation=70,min_value=60,max_size=8):
    crop=rect.crop(frame)
    if pitch<4: raise ValueError("Kích thước ô khối phải >=4 pixel.")
    hsv=cv2.cvtColor(crop,cv2.COLOR_BGR2HSV)
    mask=cv2.inRange(hsv,np.array([0,min_saturation,min_value]),np.array([179,255,255]))
    ys,xs=np.where(mask>0)
    if len(xs)<pitch*pitch*0.12:
        raise ValueError(f"Không thấy khối {piece_id}; sửa thủ công hoặc hiệu chỉnh lại.")
    x0,y0,x1,y1=int(xs.min()),int(ys.min()),int(xs.max())+1,int(ys.max())+1
    # A cropped shape can still look like a smaller valid rectangle. Never
    # silently turn it into a different piece and send that plan to the phone.
    if x0==0 or y0==0 or x1==crop.shape[1] or y1==crop.shape[0]:
        raise ValueError(f"Khối {piece_id}: vùng đọc cắt mất khối; không được lập kế hoạch.")
    cols,rows=round((x1-x0)/pitch),round((y1-y0)/pitch)
    if not 1<=rows<=max_size or not 1<=cols<=max_size:
        raise ValueError(f"Khối {piece_id}: pitch không phù hợp hoặc vùng bị che.")
    if abs((x1-x0)-cols*pitch)>pitch*0.35 or abs((y1-y0)-rows*pitch)>pitch*0.35:
        raise ValueError(f"Khối {piece_id}: hình không khớp lưới.")
    cells=[]
    for r in range(rows):
        for c in range(cols):
            # Use observed bounds to tolerate small gaps/rounded corners.
            yy0,yy1=int(y0+(r+0.2)*(y1-y0)/rows),int(y0+(r+0.8)*(y1-y0)/rows)
            xx0,xx1=int(x0+(c+0.2)*(x1-x0)/cols),int(x0+(c+0.8)*(x1-x0)/cols)
            ratio=float(np.mean(mask[yy0:yy1,xx0:xx1]>0))
            if 0.15<ratio<0.65: raise ValueError(f"Khối {piece_id}: nhận diện không chắc chắn.")
            if ratio>=0.65: cells.append((r,c))
    if not cells: raise ValueError(f"Không nhận diện được khối {piece_id}.")
    # Later levels include diagonal and detached cells. Grid fit and per-cell
    # coverage establish the piece; edge connectivity is not a game rule.
    return Piece(piece_id,tuple(cells))


def detect_tray_piece(frame,rect,piece_id,pitch=58,max_size=8,min_value=150):
    """Infer smaller cell scale from visible tile components, not a shape list.

    The calibrated pitch remains the fallback. Thin fragments and tray rims
    cannot supply scale evidence; clipped or uncertain cells still fail closed.
    """
    crop=rect.crop(frame)
    hsv=cv2.cvtColor(crop,cv2.COLOR_BGR2HSV)
    mask=cv2.inRange(hsv,np.array([0,70,min_value]),np.array([179,255,255]))
    _,_,stats,_=cv2.connectedComponentsWithStats(mask)
    evidence=[]
    for x,y,w,h,area in stats[1:]:
        small=min(w,h)
        if 18<=small<pitch*.85 and area>=w*h*.7:
            evidence.append(small+1)
    inferred=float(np.median(evidence)) if evidence else float(pitch)
    if evidence and any(abs(v-inferred)>inferred*.12 for v in evidence):
        raise ValueError(f"Khối {piece_id}: kích thước ô chưa nhất quán.")
    piece=detect_piece(frame,rect,piece_id,inferred,min_value=min_value,max_size=max_size)
    return piece,inferred
