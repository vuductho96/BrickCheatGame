"""Immutable game representation. Coordinates are (row, column)."""
from dataclasses import dataclass
import json

@dataclass(frozen=True)
class Piece:
    id: str
    cells: tuple[tuple[int, int], ...]
    def __post_init__(self):
        cells = tuple(tuple(c) for c in self.cells)
        if not isinstance(self.id, str) or not self.id or not cells or any(len(c) != 2 or any(type(v) is not int for v in c) for c in cells):
            raise ValueError("Piece needs an ID and integer (row, column) cells")
        if len(set(cells)) != len(cells):
            raise ValueError("Duplicate piece cell")
        r0, c0 = min(r for r, c in cells), min(c for r, c in cells)
        object.__setattr__(self, "cells", tuple(sorted((r-r0, c-c0) for r, c in cells)))
    @property
    def height(self):
        return max(r for r, c in self.cells)+1
    @property
    def width(self):
        return max(c for r, c in self.cells)+1

@dataclass(frozen=True)
class GameState:
    size: int
    board: int = 0
    pieces: tuple[Piece, ...] = ()
    score: int = 0
    def __post_init__(self):
        if type(self.size) is not int or not 2 <= self.size <= 16:
            raise ValueError("Board size must be 2..16")
        if type(self.board) is not int or not 0 <= self.board < (1 << self.size**2):
            raise ValueError("Board bits outside grid")
        object.__setattr__(self, "pieces", tuple(self.pieces))
        if len({p.id for p in self.pieces}) != len(self.pieces):
            raise ValueError("Piece IDs must be unique")
        if type(self.score) is not int or self.score < 0:
            raise ValueError("Score must be a nonnegative integer")
    def occupied(self, row, col):
        return bool(self.board & (1 << (row*self.size+col)))
    def matrix(self):
        return [[int(self.occupied(r,c)) for c in range(self.size)] for r in range(self.size)]
    def to_dict(self):
        return {"size":self.size, "board":self.matrix(), "pieces":[{"id":p.id,"cells":[list(c) for c in p.cells]} for p in self.pieces], "score":self.score}
    def to_json(self):
        return json.dumps(self.to_dict(),ensure_ascii=False,indent=2)
    @classmethod
    def from_dict(cls,data):
        size, grid = data["size"], data["board"]
        if type(size) is not int or not 2 <= size <= 16:
            raise ValueError("Invalid size")
        if len(grid)!=size or any(len(row)!=size for row in grid):
            raise ValueError("Matrix dimensions do not match size")
        if any(type(v) is not int or v not in (0,1) for row in grid for v in row):
            raise ValueError("Matrix values must be 0 or 1")
        board=sum(v << (r*size+c) for r,row in enumerate(grid) for c,v in enumerate(row))
        return cls(size,board,tuple(Piece(p["id"],tuple(tuple(c) for c in p["cells"])) for p in data.get("pieces",[])),data.get("score",0))
    @classmethod
    def from_json(cls,text):
        return cls.from_dict(json.loads(text))
