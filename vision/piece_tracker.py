"""Match arbitrary occupied cell patterns, including disconnected diagonals."""
import cv2
import numpy as np

def track_pattern(area,color,cells,width,height,baseline=None,target=(0,0)):
    rgb=np.array([int(color[i:i+2],16) for i in (1,3,5)],np.uint8)
    hue=int(cv2.cvtColor(rgb[::-1].reshape(1,1,3),cv2.COLOR_BGR2HSV)[0,0,0])
    hsv=cv2.cvtColor(area,cv2.COLOR_BGR2HSV)
    delta=np.abs(hsv[:,:,0].astype(int)-hue)
    present=((np.minimum(delta,180-delta)<=12)&(hsv[:,:,1]>=80)&(hsv[:,:,2]>=100)).astype(np.float32)
    rows=max(r for r,c in cells)+1;cols=max(c for r,c in cells)+1
    kernel=np.zeros((height,width),np.float32)
    holes=np.zeros_like(kernel)
    shape={tuple(cell) for cell in cells}
    regions=[]
    for r in range(rows):
        for c in range(cols):
            y0,y1=round((r+.2)*height/rows),round((r+.8)*height/rows)
            x0,x1=round((c+.2)*width/cols),round((c+.8)*width/cols)
            if (r,c) in shape:
                kernel[round((r+.08)*height/rows):round((r+.92)*height/rows),
                       round((c+.08)*width/cols):round((c+.92)*width/cols)]=1
                # Gem icons cover cell centers; track the colored rim instead.
                kernel[round((r+.28)*height/rows):round((r+.72)*height/rows),
                       round((c+.28)*width/cols):round((c+.72)*width/cols)]=0
            else:
                holes[y0:y1,x0:x1]=1
            regions.append((r,c,y0,y1,x0,x1))
    hole_present=present.copy()
    if baseline is not None:
        hole_present*=np.linalg.norm(area.astype(float)-baseline.astype(float),axis=2)>30
    else:
        # Without a before-image, existing blocks in a shape's holes cannot
        # be distinguished from added cells.
        hole_present[:]=0
    scores=cv2.matchTemplate(present,kernel,cv2.TM_CCORR)/max(1,kernel.sum())
    if holes.sum():
        scores-=cv2.matchTemplate(hole_present,holes,cv2.TM_CCORR)/holes.sum()*.4
    # Preserve exact outer edges when segmentation is complete. The grid
    # correlation below handles partial occlusion and overlapping same colors.
    moving=present.copy()
    if baseline is not None:
        moving*=np.linalg.norm(area.astype(float)-baseline.astype(float),axis=2)>30
    contours,_=cv2.findContours((moving*255).astype(np.uint8),cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    boxes=[cv2.boundingRect(c) for c in contours if cv2.contourArea(c)>width/cols*height/rows*.2]
    if len(boxes)>1:
        left=min(x for x,y,w,h in boxes);top=min(y for x,y,w,h in boxes)
        right=max(x+w for x,y,w,h in boxes);bottom=max(y+h for x,y,w,h in boxes)
        boxes.append((left,top,right-left,bottom-top))
    precise=[]
    for x,y,w,h in boxes:
        if abs(w-width)>width*.12 or abs(h-height)>height*.12:continue
        coverage=[];bad=False
        for r,c,_,_,_,_ in regions:
            patch=present[y+int((r+.2)*h/rows):y+int((r+.8)*h/rows),
                          x+int((c+.2)*w/cols):x+int((c+.8)*w/cols)]
            ratio=float(np.mean(patch))
            if (r,c) in shape:coverage.append(ratio)
            elif float(np.mean(hole_present[y+int((r+.2)*h/rows):y+int((r+.8)*h/rows),
                                            x+int((c+.2)*w/cols):x+int((c+.8)*w/cols)]))>.35:bad=True
        if not bad and min(coverage)>=.90:
            precise.append(((x-target[0])**2+(y-target[1])**2,(x,y),min(coverage)))
    if precise:
        _,point,confidence=min(precise)
        return point,float(confidence)
    candidates=[]
    for _ in range(12):
        _,score,_,point=cv2.minMaxLoc(scores)
        if score<.68:break
        x,y=point
        cover=[];wrong=False
        for r,c,y0,y1,x0,x1 in regions:
            ratio=float(np.mean(present[y+y0:y+y1,x+x0:x+x1]))
            if (r,c) in shape:
                cy0,cy1=round(r*height/rows),round((r+1)*height/rows)
                cx0,cx1=round(c*width/cols),round((c+1)*width/cols)
                rim=kernel[cy0:cy1,cx0:cx1]>0
                cover.append(float(np.mean(present[y+cy0:y+cy1,x+cx0:x+cx1][rim])))
            elif float(np.mean(hole_present[y+y0:y+y1,x+x0:x+x1]))>.35:wrong=True
        changed=1.
        if baseline is not None:
            change=np.linalg.norm(area[y:y+height,x:x+width].astype(float)-
                                  baseline[y:y+height,x:x+width].astype(float),axis=2)>30
            changed=float(np.mean(change[kernel>0]))
        if not wrong and min(cover)>=.70 and changed>=.20:
            distance=(x-target[0])**2+(y-target[1])**2
            candidates.append((-float(np.mean(cover)),distance,(x,y),float(np.mean(cover))))
        # Suppress nearby offsets of this same piece, not all other pieces.
        rx,ry=max(2,width//cols//3),max(2,height//rows//3)
        scores[max(0,y-ry):y+ry+1,max(0,x-rx):x+rx+1]=-1
    if not candidates:raise RuntimeError("Không theo dõi được hình khối đang kéo")
    _,_,point,confidence=min(candidates)
    return point,float(confidence)

