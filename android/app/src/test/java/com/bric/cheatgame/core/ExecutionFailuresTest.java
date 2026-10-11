package com.bric.cheatgame.core;

import org.junit.Test;
import static org.junit.Assert.*;

public final class ExecutionFailuresTest {
    @Test public void sameActionChangesStrategyThenIsExcluded() {
        ExecutionFailures f=new ExecutionFailures();f.observe("board/tray");
        String a=ExecutionFailures.action(2,"shape",6,1);
        for(int i=0;i<3;i++){assertEquals(i,f.strategy(a));assertTrue(f.allowed(a));f.failed(a);}
        assertFalse(f.allowed(a));f.failed(a);assertEquals(3,f.strategy(a));
    }
    @Test public void pollingAndAutoRestartDoNotForgetSameBoard() {
        ExecutionFailures f=new ExecutionFailures();f.observe("a");f.failed("drop");
        for(int i=0;i<20;i++)f.observe("a");assertEquals(1,f.strategy("drop"));
    }
    @Test public void ChangedBoardOrTrayInvalidatesFailures() {
        ExecutionFailures f=new ExecutionFailures();f.observe("board/tray");f.failed("drop");
        f.observe("board/new-tray");assertEquals(0,f.strategy("drop"));
        f.failed("drop");f.observe("changed-board/new-tray");assertEquals(0,f.strategy("drop"));
    }
    @Test public void FailureDoesNotBlockDifferentPieceOrTarget() {
        ExecutionFailures f=new ExecutionFailures();f.observe("a");
        String a=ExecutionFailures.action(0,"shape",0,0);for(int i=0;i<3;i++)f.failed(a);
        assertTrue(f.allowed(ExecutionFailures.action(1,"shape",0,0)));
        assertTrue(f.allowed(ExecutionFailures.action(0,"shape",0,1)));
    }
}
