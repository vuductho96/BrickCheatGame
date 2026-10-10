from dataclasses import dataclass
from .game_state import GameState
from .game_rules import Rules, placements, clear_lines

@dataclass(frozen=True)
class Move:
    piece_id: str
    row: int
    col: int

@dataclass(frozen=True)
class Step:
    move: Move
    state: GameState
    rows: tuple[int,...]
    cols: tuple[int,...]
    points: int

def apply_move(state,move,rules=Rules()):
    piece=next((p for p in state.pieces if p.id==move.piece_id),None)
    if piece is None: raise ValueError("Piece is unavailable")
    if type(move.row) is not int or type(move.col) is not int:
        raise ValueError("Coordinates must be integers")
    mask=next((m for r,c,m in placements(state.size,piece.cells) if r==move.row and c==move.col),None)
    if mask is None or mask&state.board:
        raise ValueError("Placement is outside board or overlaps occupied cells")
    board,rows,cols=clear_lines(state.board|mask,state.size)
    points=len(piece.cells)*rules.points_per_cell+(len(rows)+len(cols))*rules.points_per_line
    result=GameState(state.size,board,tuple(p for p in state.pieces if p.id!=piece.id),state.score+points)
    return Step(move,result,rows,cols,points)

def is_game_over(state):
    # Empty tray requires a new capture, not a game-over conclusion.
    return bool(state.pieces) and not any(not state.board&mask for p in state.pieces for r,c,mask in placements(state.size,p.cells))
