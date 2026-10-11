package com.bric.cheatgame;

import android.graphics.*;
import android.os.SystemClock;
import com.bric.cheatgame.core.*;
import org.json.*;
import java.io.*;
import java.util.*;

/** Re-read, plan, align twice, release, verify. No automatic purchases/restarts. */
public final class AutoController {
    private final CaptureService service;private final Planner planner=new Planner();
    private final ArrayList<Shape[]> history=new ArrayList<>();
    private int moves;private Rect calibrated;private String lastRefill="",readError="Chưa có ảnh";
    private long releaseSequence=-1;
    public AutoController(CaptureService service){this.service=service;loadHistory();}
    public void run(){
        try{
            long deadline=SystemClock.elapsedRealtime()+10000;
            while(CaptureService.running&&SystemClock.elapsedRealtime()<deadline){
                String top=service.getSharedPreferences("bric",0).getString("calibration","");
                if(!top.isEmpty()){String[] v=top.split(",");Bitmap f=service.frame();if(f!=null){calibrated=new Rect(Math.round(Float.parseFloat(v[0])*f.getWidth()),Math.round(Float.parseFloat(v[1])*f.getHeight()),Math.round(Float.parseFloat(v[2])*f.getWidth()),Math.round(Float.parseFloat(v[3])*f.getHeight()));f.recycle();}}
                try(BitmapHandle handle=new BitmapHandle(service.frame())){if(handle.bitmap!=null){Vision.read(handle.bitmap,calibrated);break;}}
                catch(Exception ignored){CaptureService.status="Mở bàn game trong 10 giây…";}
                Thread.sleep(300);
            }
            while(CaptureService.running){
                Vision.State state=stable(6000);if(state==null){CaptureService.status="Không đọc được bàn: "+readError;log("unreadable",null,null,null);saveFrame("error.png");break;}
                observeRefill(state);
                Shape[] shapes=state.pieces().stream().map(Vision.Piece::shape).toArray(Shape[]::new);
                if(shapes.length==0){CaptureService.status="Không có khối trong khay; Auto dừng";break;}
                CaptureService.status="Đang tính "+shapes.length+" khối · "+moves+" nước đúng";
                Planner.Plan plan=planner.solve(state.board(),shapes,160,1500,history);
                if(plan.moves().isEmpty()){CaptureService.status="Không tìm được nước hợp lệ";log("no_move",state,null,null);break;}
                // The full current-tray path is kept while each observed state agrees.
                for(Planner.Move move:plan.moves()){
                    if(!CaptureService.running)break;
                    int wantedSlot=originalSlots[move.slot()];
                    Vision.Piece piece=state.pieces().stream().filter(p->p.slot()==wantedSlot).findFirst().orElse(null);
                    if(piece==null)throw new IllegalStateException("Khay đã đổi; cần tính lại");
                    long mask=piece.shape().mask(move.row(),move.col());if((mask&state.board())!=0)throw new IllegalStateException("Ô đích đã bị chiếm");
                    log("planned",state,move,null);
                    CaptureService.status="Khối "+(piece.slot()+1)+" → hàng "+(move.row()+1)+", cột "+(move.col()+1)+" · "+moves+" nước đúng";
                    place(state,piece,move);
                    Vision.State actual=stable(6000);
                    if(actual==null||actual.board()!=move.expected()||!remainingMatches(state,actual,piece.slot())){
                        log("mismatch",state,move,actual);saveFrame("mismatch.png");throw new IllegalStateException("Sau thả khác dự tính; dừng để bảo vệ bàn");
                    }
                    log("verified",state,move,actual);moves++;state=actual;
                }
            }
        }catch(Exception error){CaptureService.status="Auto dừng: "+error.getMessage();log("error",null,null,null);saveFrame("error.png");}
        finally{CaptureService.running=false;}
    }
    private int[] originalSlots=new int[0];
    private Vision.State stable(long timeout)throws Exception{
        long end=SystemClock.elapsedRealtime()+timeout;String previous="";Vision.State latest=null;int same=0;
        while(SystemClock.elapsedRealtime()<end){
            // MediaProjection may emit no new buffer for an unchanged screen.
            // After a release require at least one image newer than the pre-UP image.
            long sequence=service.sequence();
            Bitmap frame=sequence>releaseSequence?service.frame():service.nextFrame(releaseSequence,600);
            try(BitmapHandle h=new BitmapHandle(frame)){
                if(h.bitmap==null)continue;
                try{long started=SystemClock.elapsedRealtime();Vision.State read=Vision.read(h.bitmap,calibrated);String signature=read.signature();same=signature.equals(previous)?same+1:1;previous=signature;latest=read;readError="Bàn chưa ổn định: "+same+"/3 · đọc "+(SystemClock.elapsedRealtime()-started)+" ms";if(same>=3)return latest;}
                catch(IllegalArgumentException error){readError=error.getMessage();same=0;previous="";}
            }
            Thread.sleep(180);
        }
        return null;
    }
    private boolean remainingMatches(Vision.State before,Vision.State after,int used){
        if(before.pieces().size()==1)return after.pieces().size()==3||after.pieces().isEmpty();
        Map<Integer,String> wanted=new HashMap<>(),got=new HashMap<>();for(Vision.Piece p:before.pieces())if(p.slot()!=used)wanted.put(p.slot(),p.shape().key);for(Vision.Piece p:after.pieces())got.put(p.slot(),p.shape().key);return wanted.equals(got);
    }
    private void place(Vision.State before,Vision.Piece piece,Planner.Move move)throws Exception{
        InputService input=InputService.instance;if(input==null)throw new IllegalStateException("Trợ năng mất kết nối");
        Rect b=before.boardRect();float cw=b.width()/8f,ch=b.height()/8f;
        int grip=0;double distance=Double.MAX_VALUE;
        for(int i=0;i<piece.shape().rows.length;i++){double d=Math.pow(piece.shape().rows[i]+.5-piece.shape().height/2d,2)+Math.pow(piece.shape().cols[i]+.5-piece.shape().width/2d,2);if(d<distance){distance=d;grip=i;}}
        float sx=piece.bounds().left+(piece.shape().cols[grip]+.5f)*piece.bounds().width()/piece.shape().width;
        float sy=piece.bounds().top+(piece.shape().rows[grip]+.5f)*piece.bounds().height()/piece.shape().height;
        float px=b.centerX(),py=b.centerY()+ch*.5f;boolean released=false;
        try(BitmapHandle baseline=new BitmapHandle(service.frame())){
            input.down(sx,sy);long requestedSequence=service.sequence();input.move(px,py,250);
            float targetX=b.left+move.col()*cw,targetY=b.top+move.row()*ch;
            int matches=0;
            for(int attempt=0;attempt<18;attempt++){
                if(!CaptureService.running)throw new IllegalStateException("Bạn đã dừng");
                try(BitmapHandle fresh=new BitmapHandle(service.nextFrame(requestedSequence,1800))){
                    if(fresh.bitmap==null)throw new IllegalStateException("Không có khung mới khi kéo");
                    requestedSequence=service.sequence();
                    PointF preview=locatePreview(fresh.bitmap,baseline.bitmap,b,piece);
                    PointF location=preview!=null?preview:locate(fresh.bitmap,baseline.bitmap,b,piece,targetX,targetY);
                    logAlignment(attempt,px,py,location,preview,targetX,targetY);
                    if(attempt==0)saveFrame("drag-first.png");
                    if(location==null){saveFrame("drag-unreadable.png");throw new IllegalStateException("Không thấy toàn bộ hình đang kéo");}
                    float dx=targetX-location.x,dy=targetY-location.y;
                    if(preview!=null&&Math.abs(dx)<cw*.07&&Math.abs(dy)<ch*.07){
                        if(++matches>=2){releaseSequence=service.sequence();input.up();released=true;return;}
                        // Request a changed screen for the second confirmation;
                        // one pixel remains well inside the alignment tolerance.
                        float nudge=px<fresh.bitmap.getWidth()-3?1:-1;
                        input.move(px+nudge,py,100);px+=nudge;continue;
                    }
                    matches=0;float nextX=px+Math.max(-cw,Math.min(cw,dx))*.7f,nextY=py+Math.max(-ch,Math.min(ch,dy))*.7f;
                    nextX=Math.max(2,Math.min(fresh.bitmap.getWidth()-2,nextX));nextY=Math.max(2,Math.min(fresh.bitmap.getHeight()-2,nextY));
                    input.move(nextX,nextY,120);px=nextX;py=nextY;
                }
            }
            throw new IllegalStateException("Căn không thành công; trả khối về khay");
        }finally{
            if(!released&&input.pressed()){try{input.move(sx,sy,250);input.up();}catch(Exception ignored){CaptureService.status="Android đã hủy kéo";}}
        }
    }
    /** The grey snapped footprint is the game's placement, not the lifted sprite. */
    static PointF locatePreview(Bitmap frame,Bitmap baseline,Rect board,Vision.Piece piece){
        float cw=board.width()/8f,ch=board.height()/8f;long grey=0,colored=0;float[] wanted=new float[3],sample=new float[3];Color.colorToHSV(piece.color(),wanted);
        for(int r=0;r<8;r++)for(int c=0;c<8;c++){
            int hits=0,colorHits=0;
            for(float oy:new float[]{.15f,.5f,.85f})for(float ox:new float[]{.15f,.5f,.85f}){
                int x=Math.round(board.left+(c+ox)*cw),y=Math.round(board.top+(r+oy)*ch);
                int now=frame.getPixel(x,y),old=baseline.getPixel(x,y);
                int rr=Color.red(now),gg=Color.green(now),bb=Color.blue(now),max=Math.max(rr,Math.max(gg,bb)),min=Math.min(rr,Math.min(gg,bb));
                if(max>=80&&max<=190&&max-min<max*.32f&&rr>Color.red(old)+25&&gg>Color.green(old)+25&&bb>Color.blue(old)+25)hits++;
                Color.colorToHSV(now,sample);float hue=Math.abs(sample[0]-wanted[0]);
                if(Math.min(hue,360-hue)<17&&sample[1]>.4&&sample[2]>.4&&Math.abs(rr-Color.red(old))+Math.abs(gg-Color.green(old))+Math.abs(bb-Color.blue(old))>100)colorHits++;
            }
            if(hits>=2)grey|=1L<<(r*8+c);
            if(colorHits>=6)colored|=1L<<(r*8+c);
        }
        // A lifted piece may completely cover its grey shadow. In that case
        // require every piece cell to be visible at grid centers, not a partial match.
        if(Long.bitCount(grey)<Math.max(2,(piece.shape().rows.length+1)/2)){
            if(Long.bitCount(colored)!=piece.shape().rows.length)return null;
            grey=colored;
        }
        PointF found=null;
        for(int r=0;r<=8-piece.shape().height;r++)for(int c=0;c<=8-piece.shape().width;c++){
            long mask=piece.shape().mask(r,c);
            if((grey&~mask)!=0)continue;
            if(found!=null)return null;
            found=new PointF(board.left+c*cw,board.top+r*ch);
        }
        return found;
    }
    private void logAlignment(int attempt,float px,float py,PointF location,PointF preview,float tx,float ty){
        try{JSONObject record=new JSONObject().put("time",System.currentTimeMillis()).put("event","alignment").put("attempt",attempt).put("pointerX",px).put("pointerY",py).put("targetX",tx).put("targetY",ty).put("preview",preview!=null);
            if(location!=null)record.put("observedX",location.x).put("observedY",location.y);
            try(FileWriter writer=new FileWriter(new File(service.getFilesDir(),"moves.jsonl"),true)){writer.write(record+"\n");}
        }catch(Exception ignored){}
    }
    private PointF locate(Bitmap frame,Bitmap baseline,Rect board,Vision.Piece piece,float targetX,float targetY){
        float cw=board.width()/8f,ch=board.height()/8f;int step=Math.max(4,Math.round(cw/8));PointF best=null;double score=0;
        int maxX=board.right-Math.round(piece.shape().width*cw),maxY=board.bottom-Math.round(piece.shape().height*ch);
        for(int y=board.top;y<=maxY;y+=step)for(int x=board.left;x<=maxX;x+=step){double v=match(frame,baseline,piece,x,y,cw,ch);if(v>score){score=v;best=new PointF(x,y);}}
        if(best==null||score<.7)return null;
        PointF coarse=best;score=0;best=null;
        for(int y=Math.max(board.top,(int)coarse.y-step);y<=Math.min(maxY,coarse.y+step);y+=2)for(int x=Math.max(board.left,(int)coarse.x-step);x<=Math.min(maxX,coarse.x+step);x+=2){
            double value=match(frame,baseline,piece,x,y,cw,ch)-Math.hypot(x-targetX,y-targetY)*.00001;if(value>score){score=value;best=new PointF(x,y);}}
        return best;
    }
    private double match(Bitmap frame,Bitmap baseline,Vision.Piece piece,float x,float y,float cw,float ch){
        float[] color=new float[3],sample=new float[3],old=new float[3];Color.colorToHSV(piece.color(),color);int all=0,newPixels=0;
        for(int i=0;i<piece.shape().rows.length;i++){
            int matches=0;
            for(float dy:new float[]{.12f,.88f})for(float dx:new float[]{.12f,.88f}){
                int xx=Math.round(x+(piece.shape().cols[i]+dx)*cw),yy=Math.round(y+(piece.shape().rows[i]+dy)*ch);
                if(xx<0||yy<0||xx>=frame.getWidth()||yy>=frame.getHeight())return 0;
                Color.colorToHSV(frame.getPixel(xx,yy),sample);float delta=Math.abs(sample[0]-color[0]);delta=Math.min(delta,360-delta);
                if(delta<17&&sample[1]>.4&&sample[2]>.4){matches++;Color.colorToHSV(baseline.getPixel(xx,yy),old);float difference=Math.abs(sample[0]-old[0]);if(Math.min(difference,360-difference)>20||old[2]<.4)newPixels++;}
            }
            if(matches<3)return 0;all+=matches;
        }
        if(newPixels<piece.shape().rows.length*1.5)return 0;
        return all/(piece.shape().rows.length*4d);
    }
    private void observeRefill(Vision.State state){
        originalSlots=state.pieces().stream().mapToInt(Vision.Piece::slot).toArray();
        if(state.pieces().size()!=3||state.signature().equals(lastRefill))return;
        lastRefill=state.signature();history.add(state.pieces().stream().map(Vision.Piece::shape).toArray(Shape[]::new));if(history.size()>48)history.remove(0);saveHistory();
    }
    private void loadHistory(){
        try{JSONArray data=new JSONArray(service.getSharedPreferences("bric",0).getString("trays","[]"));
            for(int i=0;i<data.length();i++){JSONArray tray=data.getJSONArray(i);Shape[] shapes=new Shape[3];for(int j=0;j<3;j++){JSONArray cells=tray.getJSONArray(j);int[][] points=new int[cells.length()][2];for(int k=0;k<cells.length();k++){points[k][0]=cells.getJSONArray(k).getInt(0);points[k][1]=cells.getJSONArray(k).getInt(1);}shapes[j]=new Shape(points);}history.add(shapes);}
        }catch(Exception ignored){history.clear();}
    }
    private void saveHistory(){JSONArray all=new JSONArray();for(Shape[] tray:history){JSONArray shapes=new JSONArray();for(Shape s:tray){JSONArray cells=new JSONArray();for(int[] p:s.cells())cells.put(new JSONArray().put(p[0]).put(p[1]));shapes.put(cells);}all.put(shapes);}service.getSharedPreferences("bric",0).edit().putString("trays",all.toString()).apply();}
    private void log(String event,Vision.State before,Planner.Move move,Vision.State actual){
        try{JSONObject record=new JSONObject().put("time",System.currentTimeMillis()).put("event",event).put("status",CaptureService.status);
            if(before!=null)record.put("before",before.signature());if(actual!=null)record.put("actual",actual.signature());if(move!=null)record.put("row",move.row()).put("col",move.col()).put("expected",Long.toUnsignedString(move.expected()));
            try(FileWriter writer=new FileWriter(new File(service.getFilesDir(),"moves.jsonl"),true)){writer.write(record+"\n");}
        }catch(Exception ignored){}
    }
    private void saveFrame(String name){try(BitmapHandle h=new BitmapHandle(service.frame())){if(h.bitmap!=null)try(FileOutputStream stream=service.openFileOutput(name,0)){h.bitmap.compress(Bitmap.CompressFormat.PNG,100,stream);}}catch(Exception ignored){}}
    private static final class BitmapHandle implements AutoCloseable {final Bitmap bitmap;BitmapHandle(Bitmap bitmap){this.bitmap=bitmap;}public void close(){if(bitmap!=null)bitmap.recycle();}}
}
