package com.bric.cheatgame;

import android.accessibilityservice.*;
import android.graphics.Path;
import android.os.*;
import android.view.accessibility.AccessibilityEvent;
import java.util.concurrent.*;
import com.bric.cheatgame.core.MotionTiming;

/** Continued strokes permit feedback while the finger remains down. */
public final class InputService extends AccessibilityService {
    public static volatile InputService instance;
    private final Handler main=new Handler(Looper.getMainLooper());
    private volatile GestureDescription.StrokeDescription held;
    private volatile String foregroundPackage="";
    private float x,y;
    private MotionTiming timing=MotionTiming.NORMAL;
    public void setTiming(MotionTiming timing){this.timing=timing;}
    @Override public void onCreate(){super.onCreate();instance=this;}
    @Override public void onServiceConnected(){instance=this;}
    @Override public void onAccessibilityEvent(AccessibilityEvent event){
        instance=this;
        if(event.getEventType()==AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED&&event.getPackageName()!=null)foregroundPackage=event.getPackageName().toString();
    }
    public boolean gameInFront(){return "com.shopee.vn".equals(foregroundPackage);}
    @Override public void onInterrupt(){CaptureService.status="Trợ năng gián đoạn; Auto sẽ đọc lại bàn";}
    @Override public void onDestroy(){if(instance==this){instance=null;held=null;CaptureService.status="Chờ Trợ năng kết nối lại";}super.onDestroy();}
    public boolean pressed(){return held!=null;}
    public void down(float sx,float sy)throws Exception{if(held!=null)throw new IllegalStateException("Finger already down");send(sx,sy,timing.duration(100),true,true);}
    public void move(float sx,float sy,long duration)throws Exception{if(held==null)throw new IllegalStateException("No finger");send(sx,sy,timing.duration(duration),true,false);Thread.sleep(timing.duration(220));}
    public void up()throws Exception{if(held!=null)send(x,y,timing.duration(60),false,false);}
    private void send(float sx,float sy,long duration,boolean continuing,boolean first)throws Exception{
        CountDownLatch complete=new CountDownLatch(1);boolean[] success={false};
        main.post(()->{
            try{
            Path path=new Path();path.moveTo(first?sx:x,first?sy:y);path.lineTo(sx,sy);
            GestureDescription.StrokeDescription stroke=first?new GestureDescription.StrokeDescription(path,0,duration,continuing):held.continueStroke(path,0,duration,continuing);
            boolean accepted=dispatchGesture(new GestureDescription.Builder().addStroke(stroke).build(),new GestureResultCallback(){
                @Override public void onCompleted(GestureDescription gesture){held=continuing?stroke:null;x=sx;y=sy;success[0]=true;complete.countDown();}
                @Override public void onCancelled(GestureDescription gesture){held=null;complete.countDown();}
            },main);
            if(!accepted){held=null;complete.countDown();}
            }catch(RuntimeException error){held=null;complete.countDown();}
        });
        if(!complete.await(duration+1800,TimeUnit.MILLISECONDS)||!success[0])throw new IllegalStateException("Android hủy hoặc không hoàn tất cử chỉ");
    }
}
