"""Local image-feedback controller, independent of piece shape and game level."""
import numpy as np

class DragServo:
    def __init__(self,target,cell,diagonal=False):
        self.target=np.asarray(target,dtype=float)
        self.cell=np.asarray(cell,dtype=float)
        self.jacobian=np.eye(2)
        self.previous=None
        self.samples=0
        self.stable=0
        self.diagonal=diagonal
        self.axis_samples=[[],[]]

    def observe(self,pointer,visual,confidence):
        p,v=np.array(pointer,dtype=float,copy=True),np.array(visual,dtype=float,copy=True)
        if self.previous is not None:
            old_p,old_v=self.previous
            dp,dv=p-old_p,v-old_v
            if self.diagonal:
                updated=False
                for axis in range(2):
                    if abs(dp[axis])<8:continue
                    gain=dv[axis]/dp[axis]
                    if .3<=gain<=2.5:
                        samples=self.axis_samples[axis]
                        samples.append(float(gain));del samples[:-5]
                        self.jacobian[axis,axis]=np.median(samples)
                        updated=True
                if updated:self.samples+=1
            elif np.linalg.norm(dp)>4 and np.linalg.norm(dv)>2:
                candidate=self.jacobian+np.outer(dv-self.jacobian@dp,dp)/(dp@dp)
                singular=np.linalg.svd(candidate,compute_uv=False)
                if singular.min()>.3 and singular.max()<2.5:
                    self.jacobian=candidate
                    self.samples+=1
        self.previous=(p,v)
        error=self.target-v
        aligned=np.max(np.abs(error)/self.cell)<.12 and confidence>=.90
        self.stable=self.stable+1 if aligned else 0
        delta=np.linalg.solve(self.jacobian,error)
        # Limit each correction; recompute from the next observed frame.
        scale=max(1.,float(np.max(np.abs(delta)/(self.cell*1.5))))
        return tuple(delta/scale)

    @property
    def ready_without_ghost(self):
        # Two independently fresh images and a measured response to input.
        return self.stable>=2 and self.samples>=1

    def bound_delta(self,delta,visual,lower,upper,overshoot=1.0):
        """Project the predicted whole-piece origin into the playable rectangle.

        Bounds describe the sprite origin, not the finger (the game lifts the
        sprite above the finger). Feedback must still verify the actual pose.
        """
        visual=np.asarray(visual,dtype=float)
        lower,upper=np.asarray(lower,dtype=float),np.asarray(upper,dtype=float)
        if np.any(upper<lower):raise ValueError("Piece exceeds board bounds")
        destination=np.clip(visual+self.jacobian@np.asarray(delta,dtype=float),lower,upper)
        motion=destination-visual
        if overshoot<1:raise ValueError("Overshoot margin must be >=1")
        if overshoot>1 and np.all(visual>=lower) and np.all(visual<=upper):
            # Do not use the entire remaining edge clearance in one command.
            # A real response faster than the model still has room to stop.
            motion=np.clip(motion,(lower-visual)/overshoot,(upper-visual)/overshoot)
        command=np.linalg.solve(self.jacobian,motion)
        if self.diagonal and overshoot>1 and np.all(visual>=lower) and np.all(visual<=upper):
            # Also cap raw pointer motion: an underestimated learned gain must
            # not enlarge the command beyond the absolute phone gain envelope.
            command=np.clip(command,(lower-visual)/overshoot,(upper-visual)/overshoot)
        return tuple(command)

