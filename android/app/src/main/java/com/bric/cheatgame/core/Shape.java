package com.bric.cheatgame.core;

import java.util.*;

/** Arbitrary normalized cell coordinates, never a named-shape whitelist. */
public final class Shape {
    public final int[] rows,cols;
    public final int height,width;
    public final String key;
    private List<Anchor> cachedAnchors;
    public Shape(int[][] cells) {
        if(cells.length==0)throw new IllegalArgumentException("Empty shape");
        int r0=99,c0=99;
        for(int[] p:cells){r0=Math.min(r0,p[0]);c0=Math.min(c0,p[1]);}
        TreeSet<Integer> normalized=new TreeSet<>();
        for(int[] p:cells) {
            int r=p[0]-r0,c=p[1]-c0;
            if(r<0||c<0||r>=8||c>=8||!normalized.add(r*8+c))throw new IllegalArgumentException("Invalid shape");
        }
        rows=new int[cells.length];cols=new int[cells.length];
        int h=0,w=0,i=0;StringBuilder k=new StringBuilder();
        for(int cell:normalized){rows[i]=cell/8;cols[i]=cell%8;h=Math.max(h,rows[i]+1);w=Math.max(w,cols[i]+1);k.append(cell).append(',');i++;}
        height=h;width=w;key=k.toString();
    }
    public long mask(int row,int col){long m=0;for(int i=0;i<rows.length;i++)m|=1L<<((row+rows[i])*8+col+cols[i]);return m;}
    public List<Anchor> anchors(){if(cachedAnchors==null){ArrayList<Anchor> a=new ArrayList<>();for(int r=0;r<=8-height;r++)for(int c=0;c<=8-width;c++)a.add(new Anchor(r,c,mask(r,c)));cachedAnchors=List.copyOf(a);}return cachedAnchors;}
    public record Anchor(int row,int col,long mask) {}
    public int[][] cells(){int[][] p=new int[rows.length][2];for(int i=0;i<rows.length;i++){p[i][0]=rows[i];p[i][1]=cols[i];}return p;}
}
