package com.bric.cheatgame.core;

/** Gesture speed never changes search budgets, frame freshness, or release checks. */
public enum MotionTiming {
    NORMAL(1), FAST(2);
    private final int multiplier;
    MotionTiming(int multiplier){this.multiplier=multiplier;}
    public int multiplier(){return multiplier;}
    public long duration(long normalMs){return Math.max(1,normalMs/multiplier);}
}
