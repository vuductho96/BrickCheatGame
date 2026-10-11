package com.bric.cheatgame;

import android.app.*;
import android.content.*;
import android.content.pm.ServiceInfo;
import android.graphics.*;
import android.hardware.display.*;
import android.media.Image;
import android.media.ImageReader;
import android.media.projection.*;
import android.os.*;
import android.util.DisplayMetrics;
import android.view.WindowManager;
import java.nio.ByteBuffer;
import java.util.concurrent.atomic.AtomicLong;

/** Screen capture stays on device. No INTERNET permission or PC runtime. */
public final class CaptureService extends Service {
    public static volatile CaptureService instance;
    public static volatile String status="Chưa chia sẻ màn hình";
    public static volatile boolean running=false;
    private final Object frames=new Object();
    private Bitmap latest,lastGame;private final AtomicLong sequence=new AtomicLong();
    private MediaProjection projection;private VirtualDisplay display;private ImageReader reader;
    private HandlerThread captureThread;private Thread autoThread;
    private long lastImageAt,lastBoardCheck;
    private String closeReason="Đã tắt chia sẻ màn hình";
    @Override public IBinder onBind(Intent intent){return null;}
    @Override public int onStartCommand(Intent intent,int flags,int id){
        if(intent==null)return START_NOT_STICKY;
        if("START".equals(intent.getAction())){if(instance==this)startAuto();else status="Chia sẻ màn hình trước";return START_NOT_STICKY;}
        if("STOP".equals(intent.getAction())){stopAuto();return START_NOT_STICKY;}
        if("CLOSE".equals(intent.getAction())){stopSelf();return START_NOT_STICKY;}
        if(instance!=null)return START_NOT_STICKY;
        try{
            createNotification();
            Intent permission=Build.VERSION.SDK_INT>=33?intent.getParcelableExtra("permission",Intent.class):intent.getParcelableExtra("permission");
            if(permission==null)throw new IllegalArgumentException("Cần cấp quyền chia sẻ màn hình");
            projection=getSystemService(MediaProjectionManager.class).getMediaProjection(intent.getIntExtra("result",0),permission);
            captureThread=new HandlerThread("bric-capture");captureThread.start();Handler handler=new Handler(captureThread.getLooper());
            projection.registerCallback(new MediaProjection.Callback(){@Override public void onStop(){closeReason="Phiên chia sẻ đã dừng. Bấm Chia sẻ toàn bộ màn hình để cấp lại.";stopSelf();}},handler);
            DisplayMetrics metrics=new DisplayMetrics();((WindowManager)getSystemService(WINDOW_SERVICE)).getDefaultDisplay().getRealMetrics(metrics);
            reader=ImageReader.newInstance(metrics.widthPixels,metrics.heightPixels,PixelFormat.RGBA_8888,3);
            reader.setOnImageAvailableListener(source->{
                try(Image image=source.acquireLatestImage()){
                    if(image==null||SystemClock.elapsedRealtime()-lastImageAt<85)return;lastImageAt=SystemClock.elapsedRealtime();
                    Image.Plane plane=image.getPlanes()[0];ByteBuffer buffer=plane.getBuffer();int padding=plane.getRowStride()/plane.getPixelStride()-image.getWidth();
                    Bitmap padded=Bitmap.createBitmap(image.getWidth()+padding,image.getHeight(),Bitmap.Config.ARGB_8888);padded.copyPixelsFromBuffer(buffer);
                    Bitmap frame=Bitmap.createBitmap(padded,0,0,image.getWidth(),image.getHeight());if(frame!=padded)padded.recycle();
                    boolean game=false;
                    if(lastImageAt-lastBoardCheck>=1000){lastBoardCheck=lastImageAt;try{Vision.findBoard(frame);game=true;}catch(IllegalArgumentException ignored){}}
                    synchronized(frames){if(latest!=null)latest.recycle();latest=frame;if(game){if(lastGame!=null)lastGame.recycle();lastGame=frame.copy(Bitmap.Config.ARGB_8888,false);}sequence.incrementAndGet();frames.notifyAll();}
                }catch(Exception failure){status="Lỗi khung hình: "+failure.getMessage();}
            },handler);
            display=projection.createVirtualDisplay("BricScreen",metrics.widthPixels,metrics.heightPixels,metrics.densityDpi,DisplayManager.VIRTUAL_DISPLAY_FLAG_AUTO_MIRROR,reader.getSurface(),null,handler);
            instance=this;status="Đã nhận màn hình. Mở game rồi bật Auto.";
        }catch(Exception error){closeReason="Không khởi động được chia sẻ: "+error.getMessage();status=closeReason;stopSelf();}
        return START_NOT_STICKY;
    }
    private void createNotification(){
        NotificationManager manager=getSystemService(NotificationManager.class);manager.createNotificationChannel(new NotificationChannel("bric","Bric Auto",NotificationManager.IMPORTANCE_LOW));
        PendingIntent open=PendingIntent.getActivity(this,0,new Intent(this,MainActivity.class),PendingIntent.FLAG_IMMUTABLE);
        PendingIntent stop=PendingIntent.getService(this,1,new Intent(this,CaptureService.class).setAction("STOP"),PendingIntent.FLAG_IMMUTABLE);
        PendingIntent close=PendingIntent.getService(this,2,new Intent(this,CaptureService.class).setAction("CLOSE"),PendingIntent.FLAG_IMMUTABLE);
        PendingIntent start=PendingIntent.getService(this,3,new Intent(this,CaptureService.class).setAction("START"),PendingIntent.FLAG_IMMUTABLE);
        Notification notification=new Notification.Builder(this,"bric").setSmallIcon(android.R.drawable.ic_media_play).setContentTitle("Bric · Xếp Gạch").setContentText("Đọc màn hình trên máy · chạm để xem trạng thái").setContentIntent(open).setOngoing(true)
            .addAction(new Notification.Action.Builder(null,"Chạy Auto",start).build()).addAction(new Notification.Action.Builder(null,"Dừng Auto",stop).build()).addAction(new Notification.Action.Builder(null,"Tắt chụp",close).build()).build();
        startForeground(7,notification,ServiceInfo.FOREGROUND_SERVICE_TYPE_MEDIA_PROJECTION);
    }
    public Bitmap frame(){synchronized(frames){return latest==null?null:latest.copy(Bitmap.Config.ARGB_8888,false);}}
    public Bitmap gameFrame(){synchronized(frames){return lastGame==null?null:lastGame.copy(Bitmap.Config.ARGB_8888,false);}}
    public Bitmap nextFrame(long previous,long timeout)throws InterruptedException{
        long end=SystemClock.elapsedRealtime()+timeout;
        synchronized(frames){while(sequence.get()<=previous&&SystemClock.elapsedRealtime()<end)frames.wait(Math.max(1,end-SystemClock.elapsedRealtime()));
            if(sequence.get()<=previous||latest==null)return null;return latest.copy(Bitmap.Config.ARGB_8888,false);}
    }
    public long sequence(){return sequence.get();}
    public synchronized void startAuto(){
        if(running||autoThread!=null&&autoThread.isAlive()){status="Chờ lượt cũ kết thúc trước khi chạy lại";return;}
        if(InputService.instance==null){status="Bật Trợ năng Bric trước";return;}
        running=true;autoThread=new Thread(()->{try{new AutoController(this).run();}finally{running=false;}},"bric-auto");autoThread.start();
    }
    public static void stopAuto(){running=false;status="Đang dừng Auto";}
    @Override public void onDestroy(){
        stopAuto();instance=null;if(autoThread!=null)try{autoThread.join(1800);}catch(InterruptedException ignored){Thread.currentThread().interrupt();}
        if(display!=null)display.release();if(reader!=null)reader.close();if(projection!=null)projection.stop();if(captureThread!=null)captureThread.quitSafely();
        synchronized(frames){if(latest!=null){latest.recycle();latest=null;}if(lastGame!=null){lastGame.recycle();lastGame=null;}}
        status=closeReason;super.onDestroy();
    }
}
