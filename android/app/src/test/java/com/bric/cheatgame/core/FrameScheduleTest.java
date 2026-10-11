package com.bric.cheatgame.core;
import org.junit.Test;
import static org.junit.Assert.*;
public final class FrameScheduleTest {
    @Test public void lastFrameInBurstRemainsScheduled(){FrameSchedule s=new FrameSchedule();assertEquals(0,s.schedule(0));s.begin(0);assertEquals(75,s.schedule(10));assertEquals(-1,s.schedule(20));s.begin(85);assertEquals(85,s.schedule(85));}
    @Test public void quietScreenDoesNotNeedAnotherNotification(){FrameSchedule s=new FrameSchedule();s.schedule(100);s.begin(100);assertEquals(84,s.schedule(101));/* the queued read runs at 185 even if no more frames arrive */s.begin(185);assertEquals(0,s.schedule(500));}
    @Test public void firstFrameDoesNotWait(){assertEquals(0,new FrameSchedule().schedule(10000));}
}
