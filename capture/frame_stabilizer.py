import cv2
import numpy as np

class FrameStabilizer:
    """Require consecutive stable frames; compare only calibrated game regions."""
    def __init__(self,required=3,pixel_threshold=12,changed_fraction=0.005):
        self.required,self.pixel_threshold,self.changed_fraction=required,pixel_threshold,changed_fraction
        self.previous=None
        self.count=0
    def reset(self):
        self.previous=None
        self.count=0
    def update(self,frame,regions=()):
        samples=[]
        for x,y,w,h in regions:
            crop=frame[y:y+h,x:x+w]
            if crop.shape[:2]!=(h,w):
                self.reset()
                return False
            samples.append(cv2.resize(crop,(128,128)))
        sample=np.concatenate(samples,axis=0) if samples else cv2.resize(frame,(128,256))
        if self.previous is not None and sample.shape==self.previous.shape:
            diff=np.max(np.abs(sample.astype(np.int16)-self.previous.astype(np.int16)),axis=2)
            stable=np.mean(diff>self.pixel_threshold)<=self.changed_fraction
            self.count=self.count+1 if stable else 1
        else: self.count=1
        self.previous=sample.copy()
        return self.count>=self.required
