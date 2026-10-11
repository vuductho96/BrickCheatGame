package com.bric.cheatgame.core;
import java.util.Random;
import org.junit.Test;
import static org.junit.Assert.*;
public final class BoardGeometryTest {
    @Test public void rectangleCountsMatchEveryLegalAnchorIncludingHighBit(){
        Random rng=new Random(190);for(int sample=0;sample<30;sample++){
            long board=sample==0?0:sample==1?~0L:rng.nextLong();
            for(int h=1;h<=8;h++)for(int w=1;w<=8;w++){
                int count=0;for(int r=0;r<=8-h;r++)for(int c=0;c<=8-w;c++){
                    long mask=0;for(int y=0;y<h;y++)for(int x=0;x<w;x++)mask|=1L<<((r+y)*8+c+x);
                    if((board&mask)==0)count++;
                }
                assertEquals("shape="+h+"x"+w,count,Board.rectangles(board,h,w));
            }
        }
    }
}
