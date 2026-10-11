package com.bric.cheatgame.core;

import java.util.HashMap;
import java.util.Map;

/** Failed physical actions are scoped to the exact observed board and tray. */
public final class ExecutionFailures {
    public static final int STRATEGIES = 3;
    private String state = "";
    private final Map<String,Integer> attempts = new HashMap<>();
    public synchronized void observe(String signature) {
        if (!state.equals(signature)) { state=signature; attempts.clear(); }
    }
    public static String action(int slot,String shape,int row,int col) {
        return slot+":"+shape+":"+row+":"+col;
    }
    public synchronized int strategy(String action) { return attempts.getOrDefault(action,0); }
    public synchronized boolean allowed(String action) { return strategy(action)<STRATEGIES; }
    public synchronized void failed(String action) {
        attempts.put(action,Math.min(STRATEGIES,strategy(action)+1));
    }
}
