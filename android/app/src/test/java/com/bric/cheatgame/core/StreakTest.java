package com.bric.cheatgame.core;

import org.junit.Test;
import java.util.List;
import java.util.Random;
import java.util.HashSet;
import static org.junit.Assert.*;

public final class StreakTest {
    @Test public void firstClearStartsRunAndThirdMissEndsIt(){
        Streak s=Streak.EMPTY.after(1);assertEquals(1,s.lines());
        s=s.after(0);assertEquals(1,s.misses());
        s=s.after(0);assertEquals(2,s.misses());assertEquals(1,s.lines());
        assertEquals(Streak.EMPTY,s.after(0));
    }
    @Test public void clearOnThirdMoveSavesRun(){
        Streak s=new Streak(8,2).after(2);
        assertEquals(10,s.lines());assertEquals(0,s.misses());
    }
    @Test public void simultaneousRowsAndColumnsIncreaseRun(){
        assertEquals(new Streak(6,0),new Streak(2,1).after(4));
    }
    @Test public void imminentBreakIsPenalizedButSetupMoveIsAllowed(){
        assertEquals(0,new Streak(8,0).priority(0),0);
        assertTrue(new Streak(8,2).priority(0)<0);
    }
    @Test public void solverClearsBeforeBreakingActiveRunWhenFullTrayFits(){
        Shape dot=new Shape(new int[][]{{0,0}});
        Planner.Plan plan=new Planner().solve(127L,new Shape[]{dot,dot,dot},80,1000,List.of(),new Streak(6,2));
        assertEquals(3,plan.placed());
        assertEquals(0,plan.moves().get(0).row());assertEquals(7,plan.moves().get(0).col());
    }
    @Test public void reorderedPlansKeepBoardAndPlacementFeasibility(){
        Random rng=new Random(25);
        for(int run=0;run<20;run++){
            long board=0;for(int i=0;i<12;i++)board|=1L<<rng.nextInt(64);
            Shape[] pieces={Planner.unfamiliar(rng),Planner.unfamiliar(rng),Planner.unfamiliar(rng)};
            Planner.Plan original=new Planner().solve(board,pieces,30,80,List.of());
            Planner.Plan reordered=Planner.reorderForStreak(board,pieces,original,new Streak(8,2));
            assertEquals(original.placed(),reordered.placed());assertTrue(reordered.lines()>=original.lines());
            HashSet<Integer> used=new HashSet<>();long actual=board;
            for(Planner.Move move:reordered.moves()){
                assertTrue(used.add(move.slot()));long mask=pieces[move.slot()].mask(move.row(),move.col());
                assertEquals(0,actual&mask);actual=Board.clear(actual|mask).board();assertEquals(actual,move.expected());
            }
            assertEquals(original.finalBoard(),actual);
        }
    }
}
