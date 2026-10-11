package com.bric.cheatgame.benchmark;

import java.util.*;

/** Bounded real-tray search + geometry and sampled unfamiliar-shape risk. */
public final class LegacyPlanner {
    public record Move(int slot,int row,int col,long expected) {}
    public record Plan(List<Move> moves,int placed,int lines,long finalBoard,boolean limited,int scenarios) {}
    private record Key(long board,int left) {}
    private record Node(long board,int left,int lines,List<Move> path,double value) {}
    private long deadline;private boolean limited;private int nodes;
    private List<LegacyShape.Anchor>[] anchors;
    private Node witness;
    private final HashSet<Key> failed=new HashSet<>();

    public Plan solve(long board,LegacyShape[] shapes,int width,long budgetMs,List<LegacyShape[]> history){
        deadline=System.nanoTime()+budgetMs*1_000_000L;limited=false;nodes=0;failed.clear();witness=null;
        anchors=new List[shapes.length];for(int i=0;i<shapes.length;i++)anchors[i]=shapes[i].anchors();
        Node root=new Node(board,(1<<shapes.length)-1,0,List.of(),LegacyBoard.cheap(board,0));
        List<Node> beam=List.of(root);Node best=root;
        for(int depth=0;depth<shapes.length;depth++){
            HashMap<Key,Node> next=new HashMap<>();
            outer:for(Node n:beam)for(int i=0;i<shapes.length;i++)if((n.left&(1<<i))!=0)for(LegacyShape.Anchor a:anchors[i]){
                if((a.mask()&n.board)!=0)continue;
                if(expired()){limited=true;break outer;}
                LegacyBoard.Cleared clear=LegacyBoard.clear(n.board|a.mask());int lines=n.lines+clear.lines();
                ArrayList<Move> path=new ArrayList<>(n.path);path.add(new Move(i,a.row(),a.col(),clear.board()));
                Node child=new Node(clear.board(),n.left^(1<<i),lines,path,LegacyBoard.cheap(clear.board(),lines));
                Key key=new Key(child.board,child.left);Node old=next.get(key);
                if(old==null||child.value>old.value)next.put(key,child);
            }
            if(next.isEmpty())break;
            beam=new ArrayList<>(next.values());beam.sort(Comparator.comparingDouble(Node::value).reversed());
            if(beam.size()>width)beam=new ArrayList<>(beam.subList(0,width));
            best=beam.get(0);
            if(expired()){limited=true;break;}
        }
        // Narrow-beam failure is not a proof of death. Try other piece orders.
        if(best.left!=0&&!expired()){
            dfs(root);
            if(witness!=null){beam=List.of(witness);best=witness;}
        }
        ArrayList<Node> complete=new ArrayList<>();for(Node n:beam)if(n.left==0)complete.add(n);
        if(complete.isEmpty())return new Plan(best.path,best.path.size(),best.lines,best.board,limited,0);
        if(complete.size()>16)complete=new ArrayList<>(complete.subList(0,16));
        double[] rank=new double[complete.size()],depthSum=new double[complete.size()];int[] worst=new int[complete.size()];Arrays.fill(worst,6);
        for(int i=0;i<rank.length;i++)rank[i]=complete.get(i).value+LegacyBoard.flexibility(complete.get(i).board);
        Random random=new Random(board^Arrays.stream(shapes).map(s->s.key).reduce("",String::concat).hashCode());
        int sampled=0;
        for(int sample=0;sample<16&&!expired();sample++){
            LegacyShape[][] future={draw(random,history),draw(random,history)};
            int[] depths=new int[complete.size()];boolean finished=true;
            for(int i=0;i<complete.size();i++){
                long current=complete.get(i).board;
                for(LegacyShape[] tray:future){Node result=rollout(current,tray);depths[i]+=result.path.size();current=result.board;if(result.left!=0)break;}
                if(expired()){finished=false;limited=true;break;}
            }
            if(!finished)break;
            for(int i=0;i<depths.length;i++){depthSum[i]+=depths[i];worst[i]=Math.min(worst[i],depths[i]);}
            sampled++;
        }
        int winner=0;double value=-Double.MAX_VALUE;
        for(int i=0;i<rank.length;i++){
            double score=rank[i]+(sampled==0?0:35*depthSum[i]/sampled+15*worst[i]);
            if(score>value){value=score;winner=i;}
        }
        best=complete.get(winner);
        return new Plan(List.copyOf(best.path),best.path.size(),best.lines,best.board,limited,sampled);
    }
    private boolean expired(){return Thread.currentThread().isInterrupted()||System.nanoTime()>=deadline;}
    private boolean dfs(Node n){
        if(n.left==0){witness=n;return true;}
        if(expired()||nodes++>=50000){limited=true;return false;}
        Key key=new Key(n.board,n.left);if(failed.contains(key))return false;
        for(int i=0;i<anchors.length;i++)if((n.left&(1<<i))!=0)for(LegacyShape.Anchor a:anchors[i]){
            if((n.board&a.mask())!=0)continue;
            LegacyBoard.Cleared c=LegacyBoard.clear(n.board|a.mask());ArrayList<Move> path=new ArrayList<>(n.path);path.add(new Move(i,a.row(),a.col(),c.board()));
            if(dfs(new Node(c.board(),n.left^(1<<i),n.lines+c.lines(),path,0)))return true;
            if(limited)return false;
        }
        failed.add(key);return false;
    }
    private Node rollout(long board,LegacyShape[] shapes){
        List<Node> beam=List.of(new Node(board,7,0,List.of(),0));Node best=beam.get(0);
        for(int depth=0;depth<3;depth++){
            HashMap<Key,Node> next=new HashMap<>();
            for(Node n:beam)for(int i=0;i<3;i++)if((n.left&(1<<i))!=0)for(LegacyShape.Anchor a:shapes[i].anchors())if((n.board&a.mask())==0){
                LegacyBoard.Cleared c=LegacyBoard.clear(n.board|a.mask());ArrayList<Move> path=new ArrayList<>(n.path);path.add(new Move(i,a.row(),a.col(),c.board()));
                Node child=new Node(c.board(),n.left^(1<<i),n.lines+c.lines(),path,(n.lines+c.lines())*20+64-Long.bitCount(c.board()));
                Key k=new Key(child.board,child.left);Node old=next.get(k);if(old==null||child.value>old.value)next.put(k,child);
            }
            if(next.isEmpty()||expired())break;
            beam=new ArrayList<>(next.values());beam.sort(Comparator.comparingDouble(Node::value).reversed());
            if(beam.size()>6)beam=beam.subList(0,6);best=beam.get(0);
        }
        return best;
    }
    private LegacyShape[] draw(Random random,List<LegacyShape[]> history){
        if(!history.isEmpty()&&random.nextBoolean())return history.get(random.nextInt(history.size()));
        LegacyShape[] result=new LegacyShape[3];for(int i=0;i<3;i++)result[i]=unfamiliar(random);return result;
    }
    public static LegacyShape unfamiliar(Random random){
        int type=random.nextInt(4);ArrayList<int[]> cells=new ArrayList<>();
        if(type==0){int length=1+random.nextInt(8);boolean vertical=random.nextBoolean();for(int i=0;i<length;i++)cells.add(new int[]{vertical?i:0,vertical?0:i});}
        else if(type==1){int h=1+random.nextInt(4),w=1+random.nextInt(4);for(int r=0;r<h;r++)for(int c=0;c<w;c++)cells.add(new int[]{r,c});}
        else if(type==2){int length=2+random.nextInt(4);for(int i=0;i<length;i++)cells.add(new int[]{i,i});}
        else {HashSet<Integer> set=new HashSet<>();set.add(3*8+3);int target=3+random.nextInt(8);
            while(set.size()<target){Integer[] existing=set.toArray(new Integer[0]);int p=existing[random.nextInt(existing.length)],r=p/8,c=p%8;
                int[] dr={-1,1,0,0},dc={0,0,-1,1};int d=random.nextInt(4);r+=dr[d];c+=dc[d];if(r>=0&&r<8&&c>=0&&c<8)set.add(r*8+c);}
            for(int p:set)cells.add(new int[]{p/8,p%8});}
        return new LegacyShape(cells.toArray(new int[0][]));
    }
}