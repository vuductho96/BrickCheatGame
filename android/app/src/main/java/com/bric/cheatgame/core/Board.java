package com.bric.cheatgame.core;

public final class Board {
    private Board() {}
    private static final long[][] VALID=new long[9][9];
    static {for(int h=1;h<=8;h++)for(int w=1;w<=8;w++)for(int r=0;r<=8-h;r++)VALID[h][w]|=((1L<<(9-w))-1)<<(r*8);}
    public static int rectangles(long board,int h,int w){
        long free=~board,horizontal=free;for(int c=1;c<w;c++)horizontal&=free>>>c;
        long fit=horizontal;for(int r=1;r<h;r++)fit&=horizontal>>>(r*8);
        return Long.bitCount(fit&VALID[h][w]);
    }
    public record Cleared(long board,int lines) {}
    public static Cleared clear(long b){
        long remove=0;int lines=0;
        for(int i=0;i<8;i++){
            long row=255L<<(i*8),col=0x0101010101010101L<<i;
            if((b&row)==row){remove|=row;lines++;}
            if((b&col)==col){remove|=col;lines++;}
        }
        return new Cleared(b&~remove,lines);
    }
    public static int count(long b,Shape s){int n=0;for(Shape.Anchor a:s.anchors())if((a.mask()&b)==0)n++;return n;}
    /** Whole empty rectangles support every shape whose bounding box fits. */
    public static double flexibility(long b){
        double total=0;int maxArea=0;
        for(int h=1;h<=8;h++)for(int w=1;w<=8;w++){
            int count=rectangles(b,h,w);
            if(count>0)maxArea=Math.max(maxArea,h*w);
            total+=Math.log1p(count)*Math.sqrt(h*w);
        }
        return total*.15+maxArea*.5;
    }
    public static double cheap(long b,int lines){
        long horizontal=0x7f7f7f7f7f7f7f7fL,vertical=0x00ffffffffffffffL;
        int boundary=Long.bitCount((b^(b>>>1))&horizontal)+Long.bitCount((b^(b>>>8))&vertical);
        int holes=0;long free=~b;
        for(int i=0;i<64;i++)if((free&(1L<<i))!=0){int r=i/8,c=i%8;long neighbors=0;
            if(r>0)neighbors|=1L<<(i-8);if(r<7)neighbors|=1L<<(i+8);if(c>0)neighbors|=1L<<(i-1);if(c<7)neighbors|=1L<<(i+1);
            if((free&neighbors)==0)holes++;
        }
        return lines*10+(64-Long.bitCount(b))*1.5-boundary*.35-holes*6;
    }
}
