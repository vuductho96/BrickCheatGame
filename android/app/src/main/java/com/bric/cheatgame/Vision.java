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
    private static final class Pixels {
        final int width,height;final int[] data;
        Pixels(Bitmap image){width=image.getWidth();height=image.getHeight();data=new int[width*height];image.getPixels(data,0,width,0,0,width,height);}
        int getWidth(){return width;}int getHeight(){return height;}int getPixel(int x,int y){return data[y*width+x];}
    }
    public static boolean colorful(int color,int value){int r=(color>>>16)&255,g=(color>>>8)&255,b=color&255,max=Math.max(r,Math.max(g,b)),min=Math.min(r,Math.min(g,b));return max>=value&&max-min>max*.27f;}
    private static float hue(int r,int g,int b,int max,int delta){if(delta==0)return 0;float h=max==r?60f*(g-b)/delta:max==g?120+60f*(b-r)/delta:240+60f*(r-g)/delta;return h<0?h+360:h;}
    private static boolean green(int color){int r=(color>>>16)&255,g=(color>>>8)&255,b=color&255,max=Math.max(r,Math.max(g,b)),min=Math.min(r,Math.min(g,b)),delta=max-min;if(max<=102||delta<=max*.45f)return false;float h=hue(r,g,b,max,delta);return h>120&&h<185;}
    public static Rect findBoard(Bitmap frame){return findBoard(new Pixels(frame));}
    private static Rect findBoard(Pixels frame){
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
    public static State read(Bitmap image,Rect calibrated){
        Pixels frame=new Pixels(image);
        Rect detected=findBoard(frame);Rect board=calibrated==null||Math.abs(calibrated.width()-calibrated.height())>frame.getWidth()*.01?detected:calibrated;
        if(Math.abs(board.left-detected.left)>frame.getWidth()*.04||Math.abs(board.top-detected.top)>frame.getHeight()*.04)
            throw new IllegalArgumentException("Bàn khác hiệu chỉnh; cần căn lại");
        long occupied=readBoard(frame,board);
        ArrayList<Piece> pieces=new ArrayList<>();
        int start=board.bottom+Math.round(board.height()*.0225f),end=trayBottom(frame,board,start);
        for(int slot=0;slot<3;slot++){
            int left=board.left+slot*board.width()/3,right=board.left+(slot+1)*board.width()/3;
            Piece piece=readPiece(frame,new Rect(left,start,right,end),slot,58f*frame.getWidth()/1080f);
            if(piece!=null)pieces.add(piece);
        }
        return new State(occupied,List.copyOf(pieces),board,System.currentTimeMillis());
    }
    private static int trayBottom(Pixels frame,Rect board,int start){
        int fallback=Math.min(frame.getHeight()-1,board.bottom+Math.round(board.height()*.35f));
        // The bottom blue/grey frame spans the tray. Ignore the bright,
        // saturated pieces and stop before the support buttons below it.
        for(int y=board.bottom+Math.round(board.height()*.15f);y<=fallback;y++){
            int hit=0,total=0;
            for(int x=board.left;x<board.right;x+=4){int color=frame.getPixel(x,y),r=(color>>>16)&255,g=(color>>>8)&255,b=color&255,max=Math.max(r,Math.max(g,b)),min=Math.min(r,Math.min(g,b)),delta=max-min;total++;
                float h=hue(r,g,b,max,delta);if(h>190&&h<240&&delta>max*.15f&&delta<max*.8f&&max>255*.25f&&max<255*.85f)hit++;}
            if(hit>total*.85)return Math.max(start+1,y-2);
        }
        return fallback;
    }
    public static long readBoard(Bitmap frame,Rect board){return readBoard(new Pixels(frame),board);}
    private static long readBoard(Pixels frame,Rect board){
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
    private static Piece readPiece(Pixels frame,Rect roi,int slot,float defaultPitch){
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
