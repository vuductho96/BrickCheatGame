package com.bric.cheatgame;

import android.app.Instrumentation;
import android.graphics.*;
import android.os.Bundle;
import org.json.*;
import java.io.*;

/** Runs actual Android Bitmap/HSV code on the phone without touching the game. */
public final class VisionInstrumentation extends Instrumentation {
    private boolean synthetic;
    @Override public void onCreate(Bundle args){super.onCreate(args);synthetic=args!=null&&"true".equals(args.getString("synthetic"));start();}
    @Override public void onStart(){Bundle result=new Bundle();int passed=0;
        try{
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
