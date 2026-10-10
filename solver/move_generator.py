from engine.game_rules import placements
from engine.simulator import Move
def legal_moves(state):
    for piece in state.pieces:
        for row,col,mask in placements(state.size,piece.cells):
            if not state.board&mask: yield Move(piece.id,row,col)
