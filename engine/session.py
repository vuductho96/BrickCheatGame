"""Local playable session with deterministic undo, tray refill and colored cells."""
from dataclasses import dataclass
import random
from .game_state import GameState,Piece
from .game_rules import Rules
from .simulator import apply_move,is_game_over

PALETTE=("#62d700","#a449db","#ff881d","#06c5e8","#ed005f","#e2d700")
SHAPES=(
    ((0,0),),((0,0),(0,1)),((0,0),(1,0)),
    ((0,0),(0,1),(0,2)),((0,0),(1,0),(2,0)),
    ((0,0),(0,1),(1,0),(1,1)),
    tuple((r,c) for r in range(2) for c in range(3)),
    tuple((r,c) for r in range(3) for c in range(2)),
    tuple((r,c) for r in range(3) for c in range(3)),
    ((0,0),(1,0),(1,1)),((0,0),(0,1),(1,1)),
    ((0,1),(1,0),(1,1)),((0,0),(0,1),(1,0)),
    ((0,0),(0,1),(0,2),(1,1)),((0,0),(1,0),(2,0),(2,1)),
)

@dataclass(frozen=True)
class Snapshot:
    state: GameState
    colors: tuple
    piece_colors: tuple
    rng: object
    counter: int
    lines: int
    moves: int

class PlaySession:
    def __init__(self,size=8,seed=None,rules=Rules()):
        self.size,self.rules=size,rules
        self.rng=random.Random(seed)
        self.history=[]
        self.counter=0
        self.lines=self.moves=0
        self.state=GameState(size)
        self.colors=(None,)*(size*size)
        self.piece_colors={}
        self.new_game()
    def deal(self):
        pieces=[]
        for slot in range(3):
            self.counter+=1
            piece=Piece(f"P{self.counter}",self.rng.choice(SHAPES))
            pieces.append(piece)
            self.piece_colors[piece.id]=self.rng.choice(PALETTE)
        self.state=GameState(self.size,self.state.board,tuple(pieces),self.state.score)
    def new_game(self):
        self.history.clear()
        self.lines=self.moves=0
        self.state=GameState(self.size)
        self.colors=(None,)*(self.size*self.size)
        self.piece_colors={}
        self.deal()
    def snapshot(self):
        return Snapshot(self.state,self.colors,tuple(self.piece_colors.items()),self.rng.getstate(),
                        self.counter,self.lines,self.moves)
    def place(self,move):
        step=apply_move(self.state,move,self.rules)  # Invalid drops must not alter history/RNG.
        before=self.snapshot()
        colors=list(self.colors)
        piece=next(p for p in self.state.pieces if p.id==move.piece_id)
        for r,c in piece.cells:
            colors[(r+move.row)*self.size+c+move.col]=self.piece_colors.get(piece.id,PALETTE[0])
        for i in range(self.size*self.size):
            if not (step.state.board>>i)&1: colors[i]=None
        self.history.append(before)
        self.colors=tuple(colors)
        self.state=step.state
        self.piece_colors.pop(piece.id,None)
        self.lines+=len(step.rows)+len(step.cols)
        self.moves+=1
        if not self.state.pieces: self.deal()
        return step
    def undo(self):
        if not self.history: return False
        previous=self.history.pop()
        self.state,self.colors=previous.state,previous.colors
        self.piece_colors=dict(previous.piece_colors)
        self.rng.setstate(previous.rng)
        self.counter,self.lines,self.moves=previous.counter,previous.lines,previous.moves
        return True
    @property
    def over(self): return is_game_over(self.state)
    def load(self,state,colors=None,piece_colors=None):
        self.size=state.size
        self.state=state
        self.colors=tuple(colors) if colors else tuple(PALETTE[1] if (state.board>>i)&1 else None for i in range(state.size**2))
        self.piece_colors=piece_colors or {p.id:PALETTE[i%len(PALETTE)] for i,p in enumerate(state.pieces)}
        self.history.clear()
        self.lines=self.moves=0
        if not state.pieces: self.deal()
