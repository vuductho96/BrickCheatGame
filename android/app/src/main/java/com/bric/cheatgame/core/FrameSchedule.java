package com.bric.cheatgame.core;

/** Coalesces notifications without consuming and discarding the final image. */
public final class FrameSchedule {
    private boolean pending;
    private long last=-85;
    public long schedule(long now){if(pending)return -1;pending=true;return Math.max(0,85-(now-last));}
    public void begin(long now){pending=false;last=now;}
}
