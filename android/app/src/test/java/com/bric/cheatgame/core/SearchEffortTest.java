package com.bric.cheatgame.core;

import java.util.*;
import org.junit.Test;
import static org.junit.Assert.*;

public final class SearchEffortTest {
    private final Shape single=new Shape(new int[][]{{0,0}});
    @Test public void openBoardKeepsNormalBudget(){assertEquals(SearchEffort.NORMAL,SearchEffort.choose(0,new Shape[]{single}));}
    @Test public void fewerEmptyCellsIncreaseEffort(){
        assertEquals(SearchEffort.CAREFUL,SearchEffort.choose(0xffffffffL,new Shape[]{single}));
        assertEquals(SearchEffort.CRITICAL,SearchEffort.choose((1L<<44)-1,new Shape[]{single}));
    }
    @Test public void fragmentedSpaceMattersBeforeHalfFull(){
        long b=0;for(int r=0;r<8;r++)for(int c=0;c<8;c++)if(r==2||r==5||c==2||c==5)b|=1L<<(r*8+c);
        assertEquals(36,64-Long.bitCount(b));assertEquals(0,Board.rectangles(b,3,3));
        assertEquals(SearchEffort.CAREFUL,SearchEffort.choose(b,new Shape[]{single}));
    }
    @Test public void fewActualPlacementsTriggerCriticalEvenWithManyEmptyCells(){
        Shape whole=new Shape(new int[][]{{0,0},{7,7}});
        assertEquals(1,Board.count(0,whole));assertEquals(SearchEffort.CRITICAL,SearchEffort.choose(0,new Shape[]{whole}));
        assertEquals(SearchEffort.CRITICAL,SearchEffort.choose(1,new Shape[]{whole,single}));
    }
    @Test public void largerSearchHonorsFailedActionsAndReplay(){
        Shape[] tray={single,new Shape(new int[][]{{0,0},{0,1}}),new Shape(new int[][]{{0,0},{1,0}})};
        long b=0;Random random=new Random(816);
        for(int i=0;i<43;i++)b|=1L<<random.nextInt(64);b=Board.clear(b).board();
        Planner.Plan p=new Planner().solve(b,tray,SearchEffort.CRITICAL,List.of(),new Streak(5,2),(slot,row,col)->slot!=0);
        assertEquals(3,p.placed());assertNotEquals(0,p.moves().get(0).slot());
        int used=0,lines=0;for(Planner.Move m:p.moves()){
            assertEquals(0,used&(1<<m.slot()));used|=1<<m.slot();long mask=tray[m.slot()].mask(m.row(),m.col());
            assertEquals(0,b&mask);Board.Cleared next=Board.clear(b|mask);b=next.board();lines+=next.lines();assertEquals(b,m.expected());
        }
        assertEquals(lines,p.lines());assertEquals(b,p.finalBoard());assertTrue(p.scenarios()<=32);
    }
    @Test public void simultaneousRowAndColumnClearFreesUnionOfCells(){
        long row=255L,col=0x0101010101010101L,missing=1L;
        Board.Cleared next=Board.clear((row|col)&~missing|missing);
        assertEquals(2,next.lines());assertEquals(0,next.board());assertEquals(15,Long.bitCount(row|col));
    }
}
