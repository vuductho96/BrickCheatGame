package com.bric.cheatgame.core;

/** Observed clear history. A run ends after three consecutive placements without a clear. */
public record Streak(int lines,int misses) {
    public static final Streak EMPTY=new Streak(0,0);
    public Streak {
        if(lines<0||misses<0||misses>2)throw new IllegalArgumentException("Invalid streak");
    }
    public Streak after(int cleared){
        if(cleared<0)throw new IllegalArgumentException("Negative clears");
        if(cleared>0)return new Streak((int)Math.min(Integer.MAX_VALUE,(long)lines+cleared),0);
        return lines==0||misses==2?EMPTY:new Streak(lines,misses+1);
    }
    /** Relative search priority, not Shopee's unknown point formula. */
    public double priority(int cleared){
        if(cleared>0)return cleared*10d+cleared*cleared*2d+cleared*Math.min(lines,15)*.8d;
        return lines>0&&misses==2?-60-Math.min(lines,15)*2d:0;
    }
}
