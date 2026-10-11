package com.bric.cheatgame.benchmark;

import com.bric.cheatgame.core.*;
import java.util.*;

/** One baseline search per tray. Both policies must leave exactly the same board. */
public final class OrderCompare {
    private static final class Stats {
        Streak streak=Streak.EMPTY;int moves,lines,breaks,maxRun;
        long replay(long board,Shape[] shapes,Planner.Plan plan){
            int used=0;
            for(Planner.Move move:plan.moves()){
                long mask=shapes[move.slot()].mask(move.row(),move.col());
                if((mask&board)!=0||(used&(1<<move.slot()))!=0)throw new AssertionError("Illegal placement");
                used|=1<<move.slot();Board.Cleared next=Board.clear(board|mask);
                if(next.board()!=move.expected())throw new AssertionError("Wrong expected board");
                if(streak.lines()>0&&streak.misses()==2&&next.lines()==0)breaks++;
                streak=streak.after(next.lines());maxRun=Math.max(maxRun,streak.lines());
                moves++;lines+=next.lines();board=next.board();
            }
            return board;
        }
    }
    public static void main(String[] args){
        int seeds=args.length>0?Integer.parseInt(args[0]):8,start=args.length>1?Integer.parseInt(args[1]):3000,trays=args.length>2?Integer.parseInt(args[2]):90,budget=args.length>3?Integer.parseInt(args[3]):150;
        System.out.println("profile,seed,moves,baseline_lines,streak_lines,baseline_breaks,streak_breaks,baseline_max_run,streak_max_run,capped");
        for(String profile:new String[]{"classic","curriculum","unfamiliar"})for(int seed=start;seed<start+seeds;seed++){
            long board=0;Stats baseline=new Stats(),ordered=new Stats();Planner planner=new Planner();List<Shape[]> history=new ArrayList<>();boolean capped=true;
            for(Shape[] pieces:Compare.stream(seed,trays,profile)){
                history.add(pieces);if(history.size()>48)history.remove(0);
                Planner.Plan plan=planner.solve(board,pieces,80,budget,history);
                Planner.Plan improved=Planner.reorderForStreak(board,pieces,plan,ordered.streak);
                long left=baseline.replay(board,pieces,plan),right=ordered.replay(board,pieces,improved);
                if(left!=right||improved.placed()!=plan.placed()||improved.lines()<plan.lines())throw new AssertionError("Safety invariant failed");
                board=left;if(plan.placed()!=3){capped=false;break;}
            }
            System.out.printf(Locale.ROOT,"%s,%d,%d,%d,%d,%d,%d,%d,%d,%s%n",profile,seed,baseline.moves,baseline.lines,ordered.lines,baseline.breaks,ordered.breaks,baseline.maxRun,ordered.maxRun,capped);System.out.flush();
        }
    }
}
