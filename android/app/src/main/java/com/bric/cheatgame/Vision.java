package com.bric.cheatgame;

import android.graphics.*;
import com.bric.cheatgame.core.Shape;
import java.util.*;

/** Screen-relative board calibration and arbitrary colored tray cells. */
public final class Vision {
    public record Piece(int slot,Shape shape,Rect bounds,int color,float pitch) {}
    public record State(long board,List<Piece> pieces,Rect boardRect,long timestamp) {
        public String signature(){StringBuilder s=new StringBuilder(Long.toUnsignedString(board));for(Piece p:pieces)s.append('/').append(p.slot).append(':').append(p.shape.key);return s.toString();}
    }
    private static final ThreadLocal<float[]> HSV=ThreadLocal.withInitial(()->new float[3]);
    public static boolean colorful(int color,int value){float[] h=HSV.get();Color.colorToHSV(color,h);return h[1]>.27f&&h[2]*255>=value;}
    private static boolean green(int color){float[] h=HSV.get();Color.colorToHSV(color,h);return h[0]>120&&h[0]<185&&h[1]>.45&&h[2]>.4;}
    public static Rect findBoard(Bitmap frame){
        int w=frame.getWidth(),h=frame.getHeight();ArrayList<Integer> lines=new ArrayList<>();
        for(int y=h/6;y<h*4/5;y+=2){int count=0;for(int x=w/30;x<w*29/30;x+=3)if(green(frame.getPixel(x,y)))count++;
            if(count>w*.20)lines.add(y);}
        Rect best=null;
        for(int y:lines)for(int bottom:lines){int side=bottom-y;if(side<w*.65||side>w*1.03)continue;
            int left=w,right=0;for(int x=0;x<w;x++)if(green(frame.getPixel(x,y))){left=Math.min(left,x);right=Math.max(right,x);}
            if(Math.abs((right-left)-side)>w*.045)continue;
            int edge=0;for(int yy=y;yy<bottom;yy+=4)if(green(frame.getPixel(left,yy))&&green(frame.getPixel(right,yy)))edge++;
            if(edge<side/4*.8)continue;
            int inset=Math.max(3,Math.round(w*.0148f));Rect candidate=new Rect(left+inset,y+inset,right-inset,bottom-inset);
            if(best==null||candidate.width()*candidate.height()>best.width()*best.height())best=candidate;
        }
        if(best==null)throw new IllegalArgumentException("Không thấy viền bàn rõ; chờ game hoặc hiệu chỉnh");
        return best;
    }
    public static State read(Bitmap frame,Rect calibrated){
        Rect detected=findBoard(frame);Rect board=calibrated==null?detected:calibrated;
        if(Math.abs(board.left-detected.left)>frame.getWidth()*.04||Math.abs(board.top-detected.top)>frame.getHeight()*.04)
            throw new IllegalArgumentException("Bàn khác hiệu chỉnh; cần căn lại");
        long occupied=readBoard(frame,board);
        ArrayList<Piece> pieces=new ArrayList<>();
        int start=board.bottom+Math.round(board.height()*.0225f),end=Math.min(frame.getHeight()-1,board.bottom+Math.round(board.height()*.35f));
        for(int slot=0;slot<3;slot++){
            int left=board.left+slot*board.width()/3,right=board.left+(slot+1)*board.width()/3;
            Piece piece=readPiece(frame,new Rect(left,start,right,end),slot,58f*frame.getWidth()/1080f);
            if(piece!=null)pieces.add(piece);
        }
        return new State(occupied,List.copyOf(pieces),board,System.currentTimeMillis());
    }
    public static long readBoard(Bitmap frame,Rect board){
        long occupied=0;
        for(int r=0;r<8;r++)for(int c=0;c<8;c++){
            int hit=0;for(float dy:new float[]{.3f,.5f,.7f})for(float dx:new float[]{.3f,.5f,.7f}){
                int x=board.left+Math.round((c+dx)*board.width()/8f),y=board.top+Math.round((r+dy)*board.height()/8f);
                if(colorful(frame.getPixel(x,y),105))hit++;
            }
            if(hit>=6)occupied|=1L<<(r*8+c);
            else if(hit>=3)throw new IllegalArgumentException("Ô bàn chưa rõ hoặc đang animation");
        }
        return occupied;
    }
    private static Piece readPiece(Bitmap frame,Rect roi,int slot,float defaultPitch){
        int w=roi.width(),h=roi.height();boolean[] mask=new boolean[w*h];int x0=w,y0=h,x1=0,y1=0,n=0;long red=0,blue=0,green=0;
        for(int y=0;y<h;y++)for(int x=0;x<w;x++){
            int color=frame.getPixel(roi.left+x,roi.top+y);if(!colorful(color,150))continue;
            mask[y*w+x]=true;n++;x0=Math.min(x0,x);x1=Math.max(x1,x+1);y0=Math.min(y0,y);y1=Math.max(y1,y+1);
            red+=Color.red(color);green+=Color.green(color);blue+=Color.blue(color);
        }
        if(n<defaultPitch*defaultPitch*.12)return null;
        if(x0==0||y0==0||x1==w||y1==h)throw new IllegalArgumentException("Khối "+(slot+1)+" bị cắt; ROI="+roi+" bounds="+x0+","+y0+","+x1+","+y1);
        float pitch=estimatePitch(mask,w,h,defaultPitch);
        int cols=Math.round((x1-x0)/pitch),rows=Math.round((y1-y0)/pitch);
        if(rows<1||cols<1||rows>8||cols>8||Math.abs(x1-x0-cols*pitch)>pitch*.35||Math.abs(y1-y0-rows*pitch)>pitch*.35)
            throw new IllegalArgumentException("Lưới hình mới chưa rõ; cần ảnh ổn định");
        ArrayList<int[]> cells=new ArrayList<>();
        for(int r=0;r<rows;r++)for(int c=0;c<cols;c++){
            int a=x0+Math.round((c+.2f)*(x1-x0)/cols),b=x0+Math.round((c+.8f)*(x1-x0)/cols);
            int t=y0+Math.round((r+.2f)*(y1-y0)/rows),d=y0+Math.round((r+.8f)*(y1-y0)/rows),count=0;
            for(int y=t;y<d;y++)for(int x=a;x<b;x++)if(mask[y*w+x])count++;
            float ratio=count/(float)Math.max(1,(b-a)*(d-t));
            if(ratio>.15&&ratio<.65)throw new IllegalArgumentException("Hình mới có ô chưa chắc chắn");
            if(ratio>=.65)cells.add(new int[]{r,c});
        }
        return new Piece(slot,new Shape(cells.toArray(new int[0][])),new Rect(roi.left+x0,roi.top+y0,roi.left+x1,roi.top+y1),Color.rgb((int)(red/n),(int)(green/n),(int)(blue/n)),pitch);
    }
    private static float estimatePitch(boolean[] mask,int w,int h,float fallback){
        boolean[] seen=new boolean[mask.length];int[] queue=new int[mask.length];ArrayList<Integer> sizes=new ArrayList<>();
        for(int start=0;start<mask.length;start++)if(mask[start]&&!seen[start]){
            int head=0,tail=1;queue[0]=start;seen[start]=true;int x0=w,y0=h,x1=0,y1=0;
            while(head<tail){int p=queue[head++],x=p%w,y=p/w;x0=Math.min(x0,x);y0=Math.min(y0,y);x1=Math.max(x1,x);y1=Math.max(y1,y);
                for(int direction=0;direction<4;direction++){int xx=x+(direction==0?-1:direction==1?1:0),yy=y+(direction==2?-1:direction==3?1:0);
                    if(xx<0||yy<0||xx>=w||yy>=h)continue;int next=yy*w+xx;if(mask[next]&&!seen[next]){seen[next]=true;queue[tail++]=next;}}
            }
            int small=Math.min(x1-x0+1,y1-y0+1);if(small>=18*w/329f&&small<fallback*.85&&tail>=(x1-x0+1)*(y1-y0+1)*.7)sizes.add(small+1);
        }
        if(sizes.isEmpty())return fallback;Collections.sort(sizes);float pitch=sizes.get(sizes.size()/2);
        for(int size:sizes)if(Math.abs(size-pitch)>pitch*.12)throw new IllegalArgumentException("Kích thước ô không nhất quán");return pitch;
    }
}
