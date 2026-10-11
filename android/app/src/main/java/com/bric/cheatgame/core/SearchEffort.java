package com.bric.cheatgame.core;

/** Spend more computation when empty space or actual piece choices are scarce. */
public record SearchEffort(int level,int width,long budgetMs,int candidates,int scenarios,int rolloutWidth,int dfsNodes) {
    public static final SearchEffort NORMAL=new SearchEffort(0,160,1500,16,16,6,50000);
    public static final SearchEffort CAREFUL=new SearchEffort(1,320,3000,24,24,10,100000);
    public static final SearchEffort CRITICAL=new SearchEffort(2,640,5000,32,32,16,200000);
    public static SearchEffort choose(long board,Shape[] pieces) {
        int empty=64-Long.bitCount(board),fewest=64;
        for(Shape piece:pieces)fewest=Math.min(fewest,Board.count(board,piece));
        if(empty<=20 || (pieces.length>0 && fewest<=2))return CRITICAL;
        if(empty<=32 || (pieces.length>0 && fewest<=6)
            || (empty<=40 && Board.rectangles(board,3,3)==0))return CAREFUL;
        return NORMAL;
    }
}
