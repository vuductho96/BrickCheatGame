"""Locate Shopee's snapped drop preview on the 8x8 grid."""
import cv2
import numpy as np

def drop_preview(frame, board, piece, size=8):
    crop=board.crop(frame)
    hsv=cv2.cvtColor(crop,cv2.COLOR_BGR2HSV)
    # The drop footprint is gray/translucent. Colored lifted sprites are excluded.
    mask=cv2.inRange(hsv,np.array([0,0,80]),np.array([179,65,215]))
    contours,_=cv2.findContours(mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    cw,ch=board.width/size,board.height/size
    expected_w,expected_h=piece["width"]*cw,piece["height"]*ch
    candidates=[]
    boxes=[cv2.boundingRect(contour) for contour in contours]
    # T/L/Z footprints may be split by the colored sprite or the board edge.
    # Merge visible gray fragments before applying the same exact grid checks.
    fragments=[cv2.boundingRect(contour) for contour in contours
               if cv2.contourArea(contour)>=cw*ch*.08]
    merged_box=None
    if len(fragments)>1:
        left=min(x for x,y,w,h in fragments)
        top=min(y for x,y,w,h in fragments)
        right=max(x+w for x,y,w,h in fragments)
        bottom=max(y+h for x,y,w,h in fragments)
        merged_box=(left,top,right-left,bottom-top)
        boxes.append(merged_box)
    for x,y,w,h in boxes:
        if abs(w-expected_w)>cw*.16 or abs(h-expected_h)>ch*.16:continue
        col,row=round(x/cw),round(y/ch)
        if abs(x-col*cw)>cw*.16 or abs(y-row*ch)>ch*.16:continue
        if row<0 or col<0 or row+piece["height"]>size or col+piece["width"]>size:continue
        # A substantial connected outline, not a tiny incidental highlight.
        if np.count_nonzero(mask[y:y+h,x:x+w])<cw*ch*.08:continue
        cells=piece.get("cells")
        if cells and (x,y,w,h)==merged_box:
            shape={tuple(cell) for cell in cells}
            support=0
            wrong=False
            for pr in range(piece["height"]):
                for pc in range(piece["width"]):
                    patch=mask[int((row+pr+.15)*ch):int((row+pr+.85)*ch),
                               int((col+pc+.15)*cw):int((col+pc+.85)*cw)]
                    ratio=float(np.mean(patch>0)) if patch.size else 0
                    if (pr,pc) in shape:
                        support+=ratio>.06
                    elif ratio>.08:
                        wrong=True
            if wrong or support<min(2,len(shape)):continue
        confidence=1-(abs(w-expected_w)+abs(h-expected_h))/(expected_w+expected_h)
        candidates.append((confidence,row,col))
    if not candidates:return None
    confidence,row,col=max(candidates)
    return {"row":row,"col":col,"confidence":confidence}

def clear_preview(frame,board,rows,cols,size=8):
    """Expected complete lines must visibly light up before using the sprite fallback."""
    hsv=cv2.cvtColor(board.crop(frame),cv2.COLOR_BGR2HSV)
    h,w=hsv.shape[:2]
    def filled(r,c):
        patch=hsv[int((r+.25)*h/size):int((r+.75)*h/size),
                  int((c+.25)*w/size):int((c+.75)*w/size),2]
        return float(np.mean(patch>=110))>.80
    return bool(rows or cols) and all(all(filled(r,c) for c in range(size)) for r in rows) and all(all(filled(r,c) for r in range(size)) for c in cols)

def clear_drop_preview(frame,board,piece,row,col,rows,cols,size=8):
    """Confirm an occluded footprint using the predicted clear lines and gray fragments.

    This detects footprint evidence only. The caller must separately verify the
    lifted sprite position before authorizing release.
    """
    if not clear_preview(frame,board,rows,cols,size):return False
    hsv=cv2.cvtColor(board.crop(frame),cv2.COLOR_BGR2HSV)
    mask=cv2.inRange(hsv,np.array([0,0,80]),np.array([179,65,215]))
    contours,_=cv2.findContours(mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    cw,ch=board.width/size,board.height/size
    x0,y0=col*cw,row*ch
    x1,y1=(col+piece["width"])*cw,(row+piece["height"])*ch
    for contour in contours:
        if cv2.contourArea(contour)<cw*ch*.08:continue
        x,y,w,h=cv2.boundingRect(contour)
        outside=x<x0-cw*.09 or y<y0-ch*.09 or x+w>x1+cw*.09 or y+h>y1+ch*.09
        # Only thin line borders may be disregarded. A broad footprint fragment
        # outside the target still rejects a wrong row/column.
        density=cv2.contourArea(contour)/max(1,w*h)
        if outside and min(w/cw,h/ch)>.16 and density>.25:return False
    # Completed lines gain pale borders along their full length. They are
    # expected effects, not evidence that the footprint extends outside shape.
    allowed=np.zeros_like(mask)
    for r in rows:allowed[max(0,round((r-.16)*ch)):round((r+1.16)*ch),:]=255
    for c in cols:allowed[:,max(0,round((c-.16)*cw)):round((c+1.16)*cw)]=255
    bx0,by0=max(0,round(x0-cw*.09)),max(0,round(y0-ch*.09))
    bx1,by1=min(mask.shape[1],round(x1+cw*.09)),min(mask.shape[0],round(y1+ch*.09))
    allowed[by0:by1,bx0:bx1]=255
    unexpected=cv2.bitwise_and(mask,cv2.bitwise_not(allowed))
    unexpected_contours,_=cv2.findContours(unexpected,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    if any(cv2.contourArea(c)>=cw*ch*.08 for c in unexpected_contours):return False
    clipped=np.zeros_like(mask)
    clipped[by0:by1,bx0:bx1]=mask[by0:by1,bx0:bx1]
    contours,_=cv2.findContours(clipped,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    pixels=0
    for contour in contours:
        # Ignore sparkles, antialiasing and small reflections on existing blocks.
        if cv2.contourArea(contour)<cw*ch*.02:continue
        x,y,w,h=cv2.boundingRect(contour)
        if x<x0-cw*.09 or y<y0-ch*.09 or x+w>x1+cw*.09 or y+h>y1+ch*.09:
            return False
        pixels+=cv2.contourArea(contour)
    return pixels>=cw*ch*.08
