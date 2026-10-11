package com.bric.cheatgame;

import org.junit.After;
import org.junit.Test;
import static org.junit.Assert.*;

/** Regression checks for the events that used to silently stop Auto. */
public final class AutoLifecycleTest {
    @After public void clearState(){CaptureService.running=false;CaptureService.waiting=false;InputService.instance=null;CaptureService.status="";}
    @Test public void accessibilityInterruptDoesNotMeanUserStop(){
        CaptureService.running=true;
        new InputService().onInterrupt();
        assertTrue(CaptureService.running);
    }
    @Test public void accessibilityDisconnectKeepsRecoveryRequested(){
        InputService input=new InputService();InputService.instance=input;
        CaptureService.running=true;
        input.onDestroy();
        assertNull(InputService.instance);
        assertTrue(CaptureService.running);
    }
    @Test public void duplicateStartDoesNotReplaceActiveStatus(){
        CaptureService.running=true;CaptureService.status="aligning";
        new CaptureService().startAuto();
        assertEquals("aligning",CaptureService.status);
        assertTrue(CaptureService.running);
    }
    @Test public void explicitStopEndsRunningAndWaiting(){
        CaptureService.running=true;CaptureService.waiting=true;
        CaptureService.stopAuto();
        assertFalse(CaptureService.running);assertFalse(CaptureService.waiting);
    }
}
