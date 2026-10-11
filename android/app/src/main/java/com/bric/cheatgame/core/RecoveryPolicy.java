package com.bric.cheatgame.core;

/** Back off repeated failures on the same observed board; never reuse a failed plan. */
public final class RecoveryPolicy {
    private String state="";
    private int failures;
    public long failed(String observed) {
        observe(observed);
        failures=Math.min(4,failures+1);
        return switch(failures){case 1->1000;case 2->2500;case 3->5000;default->30000;};
    }
    public void observe(String observed) {
        if(observed!=null&&!observed.equals(state)){state=observed;failures=0;}
    }
    public void verified(){failures=0;}
    public int failures(){return failures;}
}
