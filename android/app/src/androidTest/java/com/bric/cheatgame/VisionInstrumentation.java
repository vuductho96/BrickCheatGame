package com.bric.cheatgame;

import android.app.Instrumentation;
import android.graphics.*;
import android.os.Bundle;
import org.json.*;
import java.io.*;

/** Runs actual Android Bitmap/HSV code on the phone without touching the game. */
public final class VisionInstrumentation extends Instrumentation {
    private boolean synthetic;
    private String diagnostic;
    private String preview;
    @Override public void onCreate(Bundle args){super.onCreate(args);synthetic=args!=null&&"true".equals(args.getString("synthetic"));diagnostic=args==null?null:args.getString("frame");preview=args==null?null:args.getString("preview");start();}
    @Override public void onStart(){Bundle result=new Bundle();int passed=0;
        try{
            if(preview!=null){Bitmap baseline=BitmapFactory.decodeStream(getContext().getAssets().open("diagnostic-local.png")),drag=BitmapFactory.decodeStream(getContext().getAssets().open(preview));try{
                Vision.State read=Vision.read(baseline,null);PointF point=AutoController.locatePreview(drag,baseline,read.boardRect(),read.pieces().get(0));
                if(point==null)throw new AssertionError("Grey preview not found");
                float x=read.boardRect().left+6*read.boardRect().width()/8f,y=read.boardRect().top+2*read.boardRect().height()/8f;
                if(Math.abs(point.x-x)>1||Math.abs(point.y-y)>1)throw new AssertionError("Wrong grey anchor: "+point);
                Bitmap covered=baseline.copy(Bitmap.Config.ARGB_8888,true);try{
                    Vision.Piece square=read.pieces().get(2);Rect b=read.boardRect();float cw=b.width()/8f,ch=b.height()/8f;Canvas canvas=new Canvas(covered);Paint paint=new Paint();paint.setColor(square.color());
                    for(int r=0;r<3;r++)for(int c=0;c<3;c++)canvas.drawRect(b.left+c*cw+1,b.top+(r+4)*ch+1,b.left+(c+1)*cw-1,b.top+(r+5)*ch-1,paint);
                    PointF full=AutoController.locatePreview(covered,baseline,b,square);
                    if(full==null||Math.abs(full.x-b.left)>1||Math.abs(full.y-(b.top+4*ch))>1)throw new AssertionError("Covered 3x3 footprint");
                    paint.setColor(baseline.getPixel(Math.round(b.left+.5f*cw),Math.round(b.top+4.5f*ch)));canvas.drawRect(b.left,b.top+4*ch,b.left+cw,b.top+5*ch,paint);
                    if(AutoController.locatePreview(covered,baseline,b,square)!=null)throw new AssertionError("Incomplete square accepted");
                }finally{covered.recycle();}
                result.putString("stream","Placement: grey anchor correct; fully covered 3x3 accepted; incomplete shape rejected\n");finish(-1,result);return;
            }finally{baseline.recycle();drag.recycle();}}
            if(diagnostic!=null){Bitmap image=BitmapFactory.decodeStream(getContext().getAssets().open(diagnostic));try{long started=android.os.SystemClock.elapsedRealtime();Vision.State read=Vision.read(image,null);result.putString("stream","Diagnostic: "+read.signature()+" board="+read.boardRect()+" read_ms="+(android.os.SystemClock.elapsedRealtime()-started)+"\n");finish(-1,result);return;}finally{image.recycle();}}
            JSONArray fixtures=new JSONArray(new String(getContext().getAssets().open("fixtures/cases.json").readAllBytes(),java.nio.charset.StandardCharsets.UTF_8));
            for(int i=0;i<fixtures.length();i++){
                JSONObject item=fixtures.getJSONObject(i);Bitmap frame;
                try{frame=synthetic?render(item):BitmapFactory.decodeStream(getContext().getAssets().open("fixtures/"+item.getString("file")));}
                catch(FileNotFoundException missing){frame=render(item);}
                try{
                    Bundle debug=new Bundle();debug.putString("stream",item.getString("file")+" board="+Vision.findBoard(frame)+"\n");sendStatus(0,debug);
                    Vision.State state=Vision.read(frame,null);
                    if(!Long.toUnsignedString(state.board(),16).equals(item.getString("board")))throw new AssertionError("Board mismatch: "+item.getString("file")+" "+Long.toUnsignedString(state.board(),16));
                    JSONArray shapes=item.getJSONArray("shapes");if(shapes.length()!=state.pieces().size())throw new AssertionError("Tray length");
                    for(int j=0;j<shapes.length();j++)if(!shapes.getString(j).equals(state.pieces().get(j).shape().key))throw new AssertionError("Shape mismatch "+item.getString("file"));
                    passed++;
                }finally{frame.recycle();}
            }
            result.putString("stream","Native vision: "+passed+" fixtures passed\n");finish(-1,result);
        }catch(Throwable error){result.putString("stream","FAILED after "+passed+": "+error+"\n");finish(0,result);}
    }
    private Bitmap render(JSONObject item)throws Exception {
        Bitmap frame=Bitmap.createBitmap(1080,2340,Bitmap.Config.ARGB_8888);Canvas canvas=new Canvas(frame);Paint p=new Paint();
        p.setColor(Color.rgb(0,220,160));canvas.drawRect(30,624,1050,1648,p);p.setColor(Color.rgb(8,61,56));canvas.drawRect(46,640,1034,1632,p);
        long board=Long.parseUnsignedLong(item.getString("board"),16);
        for(int r=0;r<8;r++)for(int c=0;c<8;c++)if((board&(1L<<(r*8+c)))!=0){p.setColor(Color.rgb(250,140,20));canvas.drawRect(47+c*123.5f,641+r*124,45+(c+1)*123.5f,639+(r+1)*124,p);}
        JSONArray shapes=item.getJSONArray("shapes");int[] colors={Color.rgb(230,0,80),Color.rgb(0,210,240),Color.rgb(110,240,0)};
        for(int i=0;i<shapes.length();i++){
            String[] points=shapes.getString(i).split(",");int height=0,width=0;
            for(String point:points){int cell=Integer.parseInt(point);height=Math.max(height,cell/8+1);width=Math.max(width,cell%8+1);}
            float pitch=58,x=46+(i+.5f)*988/3-width*pitch/2,y=1800-height*pitch/2;p.setColor(colors[i]);
            for(String point:points){int cell=Integer.parseInt(point);canvas.drawRect(x+(cell%8)*pitch,y+(cell/8)*pitch,x+(cell%8+1)*pitch-1,y+(cell/8+1)*pitch-1,p);}
        }
        return frame;
    }
}
