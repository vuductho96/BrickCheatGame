package com.bric.cheatgame.benchmark;

import com.bric.cheatgame.core.*;
import java.util.*;

/** Paired streams are generated before play. They never enter the planner's history early. */
public final class Compare {
    private record Result(int moves,int lines,int trays,long nanos,boolean capped,int clearingMoves,int breaks,int maxRun) {}
    private static boolean streakMode;
    private static Shape rect(int h,int w){int[][] c=new int[h*w][2];int i=0;for(int r=0;r<h;r++)for(int col=0;col<w;col++)c[i++]=new int[]{r,col};return new Shape(c);}
    private static Shape[] pool={rect(1,1),rect(1,2),rect(2,1),rect(1,3),rect(3,1),rect(1,4),rect(4,1),rect(1,5),rect(5,1),rect(2,2),rect(3,3),rect(2,3),rect(3,2),new Shape(new int[][]{{0,0},{1,0},{1,1}}),new Shape(new int[][]{{0,0},{0,1},{0,2},{1,1}}),new Shape(new int[][]{{0,0},{1,1},{2,2}})};
    static Shape[][] stream(int seed,int count,String profile){Random rng=new Random(seed);Shape[][] out=new Shape[count][3];for(int t=0;t<count;t++)for(int i=0;i<3;i++){
        int hard=profile.equals("classic")?0:profile.equals("curriculum")&&t<10?0:1;
        if(hard==0||rng.nextInt(100)<55)out[t][i]=pool[rng.nextInt(pool.length)];
        else if(rng.nextBoolean())out[t][i]=rng.nextBoolean()?rect(3,3):rect(1+rng.nextInt(2),4+rng.nextInt(3));
        else out[t][i]=Planner.unfamiliar(rng);
    }return out;}
    private static Result play(Shape[][] stream,int budget,boolean legacy){long board=0,time=0;int moves=0,lines=0,trays=0,clearingMoves=0,breaks=0,maxRun=0;Streak streak=Streak.EMPTY;List<Shape[]> history=new ArrayList<>();List<LegacyShape[]> oldHistory=new ArrayList<>();Planner solver=new Planner();LegacyPlanner oldSolver=new LegacyPlanner();
        for(Shape[] pieces:stream){history.add(pieces);LegacyShape[] old=Arrays.stream(pieces).map(s->new LegacyShape(s.cells())).toArray(LegacyShape[]::new);oldHistory.add(old);long start=System.nanoTime();List<int[]> path=new ArrayList<>();
            if(legacy){for(LegacyPlanner.Move m:oldSolver.solve(board,old,80,budget,oldHistory).moves())path.add(new int[]{m.slot(),m.row(),m.col()});}
            else {Planner.Plan plan=streakMode?solver.solve(board,pieces,80,budget,history,streak):solver.solve(board,pieces,80,budget,history);for(Planner.Move m:plan.moves())path.add(new int[]{m.slot(),m.row(),m.col()});}
            time+=System.nanoTime()-start;int used=0;
            for(int[] m:path){long mask=pieces[m[0]].mask(m[1],m[2]);if((used&(1<<m[0]))!=0||(mask&board)!=0)throw new AssertionError("Illegal plan");used|=1<<m[0];Board.Cleared cleared=Board.clear(board|mask);board=cleared.board();lines+=cleared.lines();moves++;if(cleared.lines()>0)clearingMoves++;if(streak.lines()>0&&streak.misses()==2&&cleared.lines()==0)breaks++;streak=streak.after(cleared.lines());maxRun=Math.max(maxRun,streak.lines());}
            if(used!=7)return new Result(moves,lines,trays,time,false,clearingMoves,breaks,maxRun);trays++;
            if(history.size()>48){history.remove(0);oldHistory.remove(0);}
        }return new Result(moves,lines,trays,time,true,clearingMoves,breaks,maxRun);
    }
    public static void main(String[] args){int seeds=args.length>0?Integer.parseInt(args[0]):8,start=args.length>1?Integer.parseInt(args[1]):100,trays=args.length>2?Integer.parseInt(args[2]):60,budget=args.length>3?Integer.parseInt(args[3]):40;
        streakMode=args.length>4&&args[4].equals("streak");
        for(int warm=0;warm<3;warm++){Shape[][] s=stream(999+warm,3,"classic");play(s,15,true);play(s,15,false);}
        System.out.println("profile,seed,variant,moves,lines,trays,mean_search_ms,capped,clearing_moves,streak_breaks,max_streak_lines");System.out.flush();
        for(String profile:new String[]{"classic","curriculum","unfamiliar"})for(int seed=start;seed<start+seeds;seed++){
            Shape[][] s=stream(seed,trays,profile);
            for(int turn=0;turn<2;turn++){boolean legacy=((seed+turn)&1)==0;Result r=play(s,budget,legacy);System.out.printf(Locale.ROOT,"%s,%d,%s,%d,%d,%d,%.3f,%s,%d,%d,%d%n",profile,seed,legacy?"baseline":"upgrade",r.moves,r.lines,r.trays,r.nanos/1e6/Math.max(1,r.trays+(r.capped?0:1)),r.capped,r.clearingMoves,r.breaks,r.maxRun);System.out.flush();}
        }
    }
}
