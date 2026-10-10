package com.bric.cheatgame.core;

import org.junit.Test;
import java.util.*;
import static org.junit.Assert.*;

public final class PlannerTest {
    private Shape shape(int[][] cells){return new Shape(cells);}
    @Test public void simultaneousClearsIncludeHighBit(){long b=255L|(0x0101010101010101L<<7);Board.Cleared c=Board.clear(b);assertEquals(2,c.lines());assertEquals(0,c.board());}
    @Test public void unfamiliarShapesAreNotWhitelisted(){Shape s=shape(new int[][]{{3,2},{4,4},{5,3},{5,5},{6,2},{6,5}});assertEquals(4,s.height);assertEquals(4,s.width);assertEquals(6,Long.bitCount(s.mask(0,0)));}
    @Test public void normalizedShapeCannotWrapRows(){try{shape(new int[][]{{0,0},{0,8}});fail();}catch(IllegalArgumentException expected){} }
    @Test public void solverReplaysAllActualIdsLegally(){
        Shape[] pieces={shape(new int[][]{{0,0},{1,1},{2,2},{3,3}}),shape(new int[][]{{0,0},{0,1},{0,2},{1,0},{2,0},{2,2}}),shape(new int[][]{{0,0},{1,0},{2,0},{3,0},{4,0},{5,0},{6,0},{7,0}})};
        Planner.Plan plan=new Planner().solve(0,pieces,80,1500,List.of());assertEquals(3,plan.placed());long current=0;HashSet<Integer> used=new HashSet<>();
        for(Planner.Move move:plan.moves()){assertTrue(used.add(move.slot()));long mask=pieces[move.slot()].mask(move.row(),move.col());assertEquals(0,current&mask);current=Board.clear(current|mask).board();assertEquals(current,move.expected());}
        assertEquals(current,plan.finalBoard());
    }
    @Test public void budgetIsNotDeathProof(){Planner.Plan plan=new Planner().solve(0,new Shape[]{shape(new int[][]{{0,0}})},10,0,List.of());assertTrue(plan.limited());}
    @Test public void noMoveHasNoInventedPath(){long full=~0L;Planner.Plan p=new Planner().solve(full,new Shape[]{shape(new int[][]{{0,0}})},10,200,List.of());assertTrue(p.moves().isEmpty());}
    @Test public void rectangleFlexibilityPrefersContinuousSpace(){long a=0,b=0;for(int r=0;r<8;r++)for(int c=0;c<8;c++){if(r<4)a|=1L<<(r*8+c);if((r+c)%2==0)b|=1L<<(r*8+c);}assertEquals(Long.bitCount(a),Long.bitCount(b));assertTrue(Board.flexibility(a)>Board.flexibility(b));}
    @Test public void proceduralProbesIncludeShapesOutsideCatalog(){Random rng=new Random(73);Set<String> seen=new HashSet<>();boolean longBar=false,irregular=false;for(int i=0;i<1000;i++){Shape s=Planner.unfamiliar(rng);seen.add(s.key);assertTrue(s.width<=8&&s.height<=8);longBar|=s.width>=7||s.height>=7;irregular|=s.rows.length>=10&&s.width*s.height>s.rows.length;}assertTrue(seen.size()>100);assertTrue(longBar&&irregular);}
    @Test public void randomLegalPlansNeverOccupyWrongCells(){Random rng=new Random(9);for(int run=0;run<25;run++){long current=0;for(int i=0;i<15;i++)current|=1L<<rng.nextInt(64);Shape[] pieces={Planner.unfamiliar(rng),Planner.unfamiliar(rng),Planner.unfamiliar(rng)};Planner.Plan plan=new Planner().solve(current,pieces,30,100,List.of());for(Planner.Move m:plan.moves()){long mask=pieces[m.slot()].mask(m.row(),m.col());assertEquals(0,current&mask);current=Board.clear(current|mask).board();assertEquals(current,m.expected());}}}
}
