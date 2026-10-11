package com.bric.cheatgame.core;

import org.junit.Test;
import static org.junit.Assert.*;

public final class RecoveryPolicyTest {
    @Test public void unchangedBoardCannotCauseRapidEndlessDrags(){
        RecoveryPolicy policy=new RecoveryPolicy();
        assertEquals(1000,policy.failed("board-a"));
        assertEquals(2500,policy.failed("board-a"));
        assertEquals(5000,policy.failed("board-a"));
        for(int i=0;i<100;i++)assertEquals(30000,policy.failed("board-a"));
    }
    @Test public void NewBoardOrVerifiedDropClearsBackoff(){
        RecoveryPolicy policy=new RecoveryPolicy();
        policy.failed("board-a");policy.failed("board-a");
        assertEquals(1000,policy.failed("board-b"));
        policy.verified();assertEquals(1000,policy.failed("board-b"));
    }
    @Test public void unreadableFrameDoesNotPretendBoardHasChanged(){
        RecoveryPolicy policy=new RecoveryPolicy();policy.failed("board-a");
        assertEquals(2500,policy.failed(null));
        policy.observe("board-a");assertEquals(2,policy.failures());
    }
}
