from engine.game_state import Piece
def parse_pieces(text):
    pieces=[]
    for line in text.splitlines():
        line=line.strip()
        if not line: continue
        identity,pattern=line.split(":",1)
        rows=pattern.strip().split("/")
        if not rows or any(not row or any(c not in "01" for c in row) for row in rows) or len({len(row) for row in rows})!=1:
            raise ValueError("Mẫu khối: A:11/11; mỗi dòng một khối, chỉ dùng 0 và 1.")
        pieces.append(Piece(identity.strip(),tuple((r,c) for r,row in enumerate(rows) for c,v in enumerate(row) if v=="1")))
    if len(pieces)>6: raise ValueError("MVP hỗ trợ tối đa 6 khối.")
    if len({p.id for p in pieces})!=len(pieces): raise ValueError("Tên khối phải khác nhau.")
    if any(max(p.height,p.width)>5 for p in pieces): raise ValueError("Mỗi khối tối đa 5×5.")
    return tuple(pieces)
def format_pieces(pieces):
    return "\n".join(p.id+":"+"/".join("".join("1" if (r,c) in p.cells else "0" for c in range(p.width)) for r in range(p.height)) for p in pieces)
def describe_move(move):
    return f"Chọn khối {move.piece_id} · góc trên trái: hàng {move.row+1}, cột {move.col+1}"
