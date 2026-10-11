package com.bric.cheatgame;

import android.Manifest;
import android.app.*;
import android.content.*;
import android.graphics.*;
import android.media.projection.MediaProjectionManager;
import android.os.*;
import android.provider.Settings;
import android.view.*;
import android.widget.*;
import java.io.*;
import java.util.zip.*;

public final class MainActivity extends Activity {
    private final Handler handler=new Handler();private TextView status;private Button auto;
    private final Runnable refresh=new Runnable(){public void run(){status.setText((InputService.instance!=null?"Trợ năng: đã bật":"Trợ năng: chưa bật")+"\n"+CaptureService.status);auto.setText(CaptureService.running?(CaptureService.waiting?"Dừng Auto (đang chờ)":"Dừng Auto"):"Chạy Auto trên điện thoại");handler.postDelayed(this,500);}};
    @Override public void onCreate(Bundle state){
        super.onCreate(state);getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        LinearLayout layout=new LinearLayout(this);layout.setOrientation(LinearLayout.VERTICAL);layout.setPadding(dp(24),dp(32),dp(24),dp(20));layout.setBackgroundColor(Color.rgb(243,248,249));
        ScrollView scroll=new ScrollView(this);scroll.addView(layout);setContentView(scroll);
        TextView title=text("Bric · Xếp Gạch",28);title.setTypeface(null,Typeface.BOLD);layout.addView(title);
        layout.addView(text("Chạy trên máy · nhận hình mới · không cần PC",15));
        status=text("",16);status.setPadding(0,dp(20),0,dp(20));layout.addView(status);
        button(layout,"1. Bật Trợ năng Bric",()->startActivity(new Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS)));
        button(layout,"2. Chia sẻ ứng dụng / màn hình",this::requestCapture);
        auto=button(layout,"Chạy Auto trên điện thoại",()->{
            if(CaptureService.running){CaptureService.stopAuto();return;}
            if(CaptureService.instance==null){Toast.makeText(this,"Chia sẻ màn hình trước",Toast.LENGTH_LONG).show();return;}
            if(InputService.instance==null){Toast.makeText(this,"Bật Trợ năng Bric trước",Toast.LENGTH_LONG).show();return;}
            CaptureService.instance.startAuto();moveTaskToBack(true);
        });
        button(layout,"Hiệu chỉnh / xem bàn",this::calibrate);
        button(layout,"Lưu log để sửa lỗi",()->startActivityForResult(new Intent(Intent.ACTION_CREATE_DOCUMENT).setType("application/zip").putExtra(Intent.EXTRA_TITLE,"bric-debug.zip"),11));
        button(layout,"Tắt chụp màn hình",()->{if(CaptureService.instance!=null)startService(new Intent(this,CaptureService.class).setAction("CLOSE"));});
        layout.addView(text("Mở ván game trước, quay lại Bric rồi chạy Auto. Khi cấp quyền có thể chọn một ứng dụng (Shopee) hoặc toàn bộ màn hình. Có thể dừng Auto từ thông báo bất cứ lúc nào.\n\nHình mới được đọc theo các ô, không cần tên hình. Kịch bản tương lai là giả định; không bảo đảm điểm hoặc thắng. App không bấm hồi sinh, mua vật phẩm hay tự mở ván mới.",14));
        if(getIntent().getBooleanExtra("open_capture",false))handler.post(this::requestCapture);
    }
    private void requestCapture(){
            if(CaptureService.instance!=null){Toast.makeText(this,"Đã nhận màn hình",Toast.LENGTH_SHORT).show();return;}
            if(Build.VERSION.SDK_INT>=33)requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS},9);
            MediaProjectionManager manager=getSystemService(MediaProjectionManager.class);
            Intent request=manager.createScreenCaptureIntent();
            startActivityForResult(request,10);
    }
    private TextView text(String value,int size){TextView t=new TextView(this);t.setText(value);t.setTextSize(size);t.setTextColor(Color.rgb(12,48,57));t.setPadding(0,dp(8),0,dp(8));return t;}
    private Button button(LinearLayout parent,String label,Runnable action){Button b=new Button(this);b.setText(label);b.setAllCaps(false);parent.addView(b,new LinearLayout.LayoutParams(-1,dp(60)));b.setOnClickListener(v->action.run());return b;}
    private int dp(int pixels){return Math.round(pixels*getResources().getDisplayMetrics().density);}
    @Override protected void onResume(){super.onResume();handler.post(refresh);}
    @Override protected void onPause(){handler.removeCallbacks(refresh);super.onPause();}
    @Override protected void onActivityResult(int request,int result,Intent data){
        super.onActivityResult(request,result,data);
        if(result!=RESULT_OK||data==null)return;
        if(request==10){startForegroundService(new Intent(this,CaptureService.class).putExtra("result",result).putExtra("permission",data));}
        if(request==11){try(ZipOutputStream zip=new ZipOutputStream(getContentResolver().openOutputStream(data.getData()))){
            for(String name:new String[]{"moves.jsonl","mismatch.png","error.png","drag-unreadable.png"}){File file=new File(getFilesDir(),name);if(!file.exists())continue;zip.putNextEntry(new ZipEntry(name));try(FileInputStream in=new FileInputStream(file)){in.transferTo(zip);}zip.closeEntry();}
            Toast.makeText(this,"Đã lưu log",Toast.LENGTH_SHORT).show();
        }catch(Exception error){Toast.makeText(this,"Không lưu được: "+error.getMessage(),Toast.LENGTH_LONG).show();}}
    }
    private void calibrate(){
        CaptureService service=CaptureService.instance;Bitmap frame=service==null?null:service.gameFrame();
        if(frame==null){Toast.makeText(this,"Chia sẻ màn hình rồi mở bàn game vài giây trước",Toast.LENGTH_LONG).show();return;}
        if(CaptureService.running){Toast.makeText(this,"Dừng Auto trước khi hiệu chỉnh",Toast.LENGTH_LONG).show();frame.recycle();return;}
        CalibrationView view=new CalibrationView(frame);
        AlertDialog dialog=new AlertDialog.Builder(this).setTitle("Chạm góc trên trái, rồi góc dưới phải bên trong bàn").setView(view)
            .setPositiveButton("Lưu",(d,w)->{
                RectF rect=view.selection;if(rect==null||rect.width()<frame.getWidth()*.5||Math.abs(rect.width()-rect.height())>frame.getWidth()*.08){Toast.makeText(this,"Chọn bàn vuông đủ lớn",Toast.LENGTH_LONG).show();return;}
                getSharedPreferences("bric",0).edit().putString("calibration",rect.left/frame.getWidth()+","+rect.top/frame.getHeight()+","+rect.right/frame.getWidth()+","+rect.bottom/frame.getHeight()).apply();
            }).setNeutralButton("Tự tìm viền",(d,w)->getSharedPreferences("bric",0).edit().remove("calibration").apply()).setNegativeButton("Đóng",null).create();
        dialog.setOnDismissListener(d->frame.recycle());dialog.show();
    }
    private final class CalibrationView extends View {
        final Bitmap bitmap;final Paint paint=new Paint(3);final Matrix matrix=new Matrix(),inverse=new Matrix();RectF selection;PointF first;
        CalibrationView(Bitmap bitmap){super(MainActivity.this);this.bitmap=bitmap;setMinimumHeight(dp(450));}
        @Override protected void onDraw(Canvas canvas){super.onDraw(canvas);matrix.setRectToRect(new RectF(0,0,bitmap.getWidth(),bitmap.getHeight()),new RectF(0,0,getWidth(),getHeight()),Matrix.ScaleToFit.CENTER);canvas.drawBitmap(bitmap,matrix,paint);
            if(selection!=null){RectF out=new RectF(selection);matrix.mapRect(out);paint.setStyle(Paint.Style.STROKE);paint.setStrokeWidth(4);paint.setColor(Color.YELLOW);canvas.drawRect(out,paint);paint.setStyle(Paint.Style.FILL);}}
        @Override public boolean onTouchEvent(MotionEvent event){if(event.getAction()!=MotionEvent.ACTION_UP)return true;matrix.invert(inverse);float[] point={event.getX(),event.getY()};inverse.mapPoints(point);
            if(first==null){first=new PointF(point[0],point[1]);selection=null;}else{selection=new RectF(Math.min(first.x,point[0]),Math.min(first.y,point[1]),Math.max(first.x,point[0]),Math.max(first.y,point[1]));first=null;}invalidate();performClick();return true;}
        @Override public boolean performClick(){super.performClick();return true;}
    }
}
