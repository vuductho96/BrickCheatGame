const $=id=>document.getElementById(id);
let state=null,token=null,busy=false,drag=null,activePlan=0,poll=null;
const slots=['trái','giữa','phải'];
for(let r=0;r<8;r++)for(let c=0;c<8;c++){
 const cell=document.createElement('div');cell.className='cell';cell.dataset.row=r;cell.dataset.col=c;
 cell.setAttribute('role','gridcell');cell.setAttribute('aria-label',`Hàng ${r+1}, cột ${c+1}`);$('board').append(cell);
}
function pieceNode(piece,tile){
 const node=document.createElement('div');node.className='piece';node.dataset.id=piece.id;
 node.style.setProperty('--cols',piece.width);node.style.setProperty('--rows',piece.height);
 if(tile)node.style.setProperty('--tile',tile+'px');
 for(let r=0;r<piece.height;r++)for(let c=0;c<piece.width;c++){
  const block=document.createElement('div');const exists=piece.cells.some(([rr,cc])=>rr===r&&cc===c);
  block.className=exists?'block':'hole';block.style.setProperty('--color',piece.color);
  block.dataset.row=r;block.dataset.col=c;node.append(block);
 }
 return node;
}
function setBusy(value){
 busy=value;$('busy').hidden=!value;$('refresh').disabled=value;
 $('tray').classList.toggle('locked',value);$('restart').disabled=value;
}
async function api(path,body){
 const response=await fetch(path,{method:body?'POST':'GET',headers:body?{'Content-Type':'application/json','X-Session-Token':token}:{},body:body?JSON.stringify(body):undefined});
 const result=await response.json();if(!response.ok)throw new Error(result.error||'Không kết nối được');return result;
}
function hint(index=0){
 activePlan=index;
 document.querySelectorAll('.suggested').forEach(n=>n.classList.remove('suggested'));
 document.querySelectorAll('.recommended').forEach(n=>n.classList.remove('recommended'));
 document.querySelectorAll('.plan-row').forEach((n,i)=>n.classList.toggle('active',i===index));
 const plan=state?.plans?.[index];if(!plan)return;
 const move=plan.moves[0],piece=state.pieces.find(p=>p.id===move.piece_id);if(!piece)return;
 $('next-hint').textContent=`Khối ${slots[piece.slot]} → Hàng ${move.row+1}, cột ${move.col+1}`;
 document.querySelector(`.tray-slot[data-slot="${piece.slot}"]`)?.classList.add('recommended');
 for(const[r,c]of piece.cells)document.querySelector(`.cell[data-row="${r+move.row}"][data-col="${c+move.col}"]`)?.classList.add('suggested');
}
function showExecution(data){
 const execution=data.execution,pending=data.pending_move;
 if(!execution||execution.state_id!==data.state_id||!pending||
    !['piece_id','row','col'].every(key=>execution.target[key]===pending[key]))return;
 const piece=execution.pieces.find(p=>p.id===pending.piece_id);if(!piece)return;
 for(const[r,c]of piece.cells)document.querySelector(`#board .cell[data-row="${r+pending.row}"][data-col="${c+pending.col}"]`)?.classList.add('suggested');
 document.querySelector(`.tray-slot[data-slot="${piece.slot}"]`)?.classList.add('recommended');
 for(const[index,move]of execution.moves.entries()){
  const shape=execution.pieces.find(p=>p.id===move.piece_id);if(!shape)continue;
  const row=document.createElement('div');row.className='plan-row'+(index===0?' active':'');
  const num=document.createElement('span');num.className='plan-number';num.textContent=index+1;
  const copy=document.createElement('span');copy.className='plan-copy';
  const title=document.createElement('strong'),detail=document.createElement('small');
  title.textContent=`Khối ${slots[shape.slot]} → Hàng ${move.row+1}, cột ${move.col+1}`;
  detail.textContent=index===0?'Đang thực hiện · phải khớp ô vàng':'Bước kế tiếp dự tính · kiểm tra lại sau thả';
  copy.append(title,detail);row.append(num,pieceNode(shape),copy);$('plans').append(row);
 }
}
function showCheck(check){
 $('drop-check').hidden=!check;if(!check)return;
 const matched=check.outcome==='verified',actual=check.actual,expected=check.expected;
 $('check-title').textContent=matched?'Lần thả gần nhất: đã xác minh':'Lần thả gần nhất: chưa khớp';
 $('drop-check').classList.toggle('check-failed',!matched);
 let differences=0;
 for(const id of ['expected-board','actual-board']){
  $(id).replaceChildren();
  const grid=id==='expected-board'?expected:actual;
  for(let r=0;r<8;r++)for(let c=0;c<8;c++){
   const cell=document.createElement('span');cell.className='check-cell';
   if(grid?.[r]?.[c])cell.classList.add('occupied');
   if(actual&&expected[r][c]!==actual[r][c]){cell.classList.add('difference');if(id==='actual-board')differences++;}
   cell.setAttribute('aria-label',`Hàng ${r+1}, cột ${c+1}: ${grid?(grid[r][c]?'có khối':'trống'):'chưa đọc được'}`);$(id).append(cell);
  }
 }
 const location=`Hàng ${check.move.row+1}, cột ${check.move.col+1}`;
 $('check-detail').textContent=check.phase==='level_complete'?`${location} · Game đã báo thắng; chưa đối chiếu được bàn sau hiệu ứng.`:
  !actual?`${location} · Chưa đọc được bàn sau thả.`:
  `${location} · ${differences===0?'Bàn sau thả khớp dự tính.':differences+' ô khác dự tính, đánh dấu đỏ. Auto đã dừng.'}`;
}
function render(data){
 state=data;activePlan=0;


 const cells=[...$('board').children];
 for(let r=0;r<8;r++)for(let c=0;c<8;c++){
  const node=cells[r*8+c];node.className='cell';
  const color=data.colors?.[r]?.[c];if(color){node.classList.add('block');node.style.setProperty('--color',color);}
  else node.style.removeProperty('--color');
 }
 $('tray').replaceChildren();
 for(let i=0;i<3;i++){
  const slot=document.createElement('div');slot.className='tray-slot';slot.dataset.slot=i;
  const piece=data.pieces.find(p=>p.slot===i);
  if(piece){slot.append(pieceNode(piece));slot.setAttribute('aria-label',`Kéo khối ${slots[i]}`);}
  else{slot.classList.add('empty');slot.setAttribute('aria-label','Ô khay trống');}
  $('tray').append(slot);
 }
 $('plans').replaceChildren();
 for(const[index,plan]of(data.plans||[]).entries()){
  const move=plan.moves[0],piece=data.pieces.find(p=>p.id===move.piece_id);if(!piece)continue;
  const button=document.createElement('button');button.className='plan-row';button.dataset.plan=index;
  const num=document.createElement('span');num.className='plan-number';num.textContent=index+1;button.append(num,pieceNode(piece));
  const copy=document.createElement('span');copy.className='plan-copy';const strong=document.createElement('strong'),small=document.createElement('small');
  strong.textContent=`Hàng ${move.row+1}, cột ${move.col+1}`;small.textContent=`Đặt khối ${slots[piece.slot]}`;copy.append(strong,small);button.append(copy);button.onclick=()=>hint(index);$('plans').append(button);
 }
 $('overlay').hidden=data.phase==='playing';
 $('restart').hidden=!['game_over','level_complete'].includes(data.phase);
 $('restart').textContent=data.phase==='level_complete'?'Cấp độ tiếp theo':'Tham gia lại';
 if(data.phase==='level_complete'){$('overlay-title').textContent='Tốt lắm — đã thắng!';$('overlay-detail').textContent='Auto sẽ bấm Cấp độ tiếp theo khi được bật.';$('next-hint').textContent='Đã hoàn thành cấp độ';}
 else if(data.phase==='game_over'){$('overlay-title').textContent='Cố lên nhé';$('overlay-detail').textContent='Ván đã kết thúc trên điện thoại. Bấm Tham gia lại để bắt đầu.';$('next-hint').textContent='Ván đã kết thúc';}
 else if(data.phase!=='playing'){$('overlay-title').textContent='Đợi khối mới';$('overlay-detail').textContent='Khay điện thoại chưa sẵn sàng. Cập nhật gợi ý sau khi hiệu ứng kết thúc.';}
 else if(!data.plans.length)$('next-hint').textContent=window.autoActive?'Auto đang tính khay hiện tại…':'Không còn vị trí đặt hợp lệ';
 if(data.sync==='moving'){
  $('plans').replaceChildren();
  document.querySelectorAll('.suggested,.recommended').forEach(n=>n.classList.remove('suggested','recommended'));
  const pending=data.pending_move;
  $('next-hint').textContent=pending?('Auto đang căn: Hàng '+(pending.row+1)+', cột '+(pending.col+1)):'Đang thao tác trên điện thoại…';
  showExecution(data);
 }
 $('model-help').textContent=data.sync==='moving'?'Bàn đã xác nhận trước lần kéo. Ô vàng là mục tiêu Auto phải đặt; so với luồng LIVE bên trái.':'Ô viền vàng là vị trí nên đặt. Các lựa chọn bên trên là phương án thay thế.';
 showCheck(data.last_check);
 if(data.search?.cached)$('metrics').textContent='Kế hoạch đã tính cho bàn và khay hiện tại';
 else if(data.search)$('metrics').textContent=`${data.search.ms} ms · ${data.search.explored.toLocaleString('vi')} trạng thái · gợi ý cho khay hiện tại`;
 if(data.search?.future_samples)$('metrics').textContent+=` · qua ${data.search.future_survived}/${data.search.future_samples} kịch bản ${data.search.future_horizon} khay giả định (ước tính, không biết khay sắp ra)`;
 if(data.receipt)$('message').textContent=data.receipt.message;
 if(data.sync!=='moving')hint(0);
}
function updateScreenOnly(){}
async function refresh(){
 if(busy||drag||window.liveTouchActive ){schedulePoll();return;}
 setBusy(true);
 try{render(await api('/api/state'));if(!state.receipt)$('message').textContent='Kéo trực tiếp trên màn hình LIVE; gợi ý tự cập nhật';}
 catch(err){$('message').textContent=err.message;updateScreenOnly();$('overlay').hidden=false;$('overlay-title').textContent='Chưa đọc được bàn';$('overlay-detail').textContent=err.message;state=null;}
 finally{setBusy(false);schedulePoll();}
}
function schedulePoll(){clearTimeout(poll);poll=setTimeout(refresh,350);}
function boardGeometry(){const board=$('board'),rect=board.getBoundingClientRect(),styles=getComputedStyle(board),inset=parseFloat(styles.borderLeftWidth)+parseFloat(styles.paddingLeft);return{x:rect.left+inset,y:rect.top+inset,cell:(rect.width-2*inset)/8};}
function startDrag(event,piece){
 if(busy||!state||state.phase!=='playing'||!event.target.classList.contains('block'))return;
 event.preventDefault();clearTimeout(poll);
 const shape=event.currentTarget.querySelector('.piece'),rect=shape.getBoundingClientRect(),styles=getComputedStyle(shape);
 const tile=parseFloat(styles.getPropertyValue('--tile'))+1,gr=(event.clientY-rect.top)/tile,gc=(event.clientX-rect.left)/tile;
 const row=Math.floor(gr),col=Math.floor(gc);if(!piece.cells.some(([r,c])=>r===row&&c===col))return;
 const ghost=pieceNode(piece,boardGeometry().cell);ghost.classList.add('drag-ghost');document.body.append(ghost);
 drag={piece,grab:[gr,gc],ghost,state_id:state.state_id,slot:event.currentTarget,row:0,col:0,valid:false};drag.slot.classList.add('dragging');
 document.querySelectorAll('.suggested').forEach(n=>n.classList.remove('suggested'));
 moveDrag(event);
}
function moveDrag(event){
 if(!drag)return;
 const geometry=boardGeometry(),[gr,gc]=drag.grab;
 drag.row=Math.floor((event.clientY-geometry.y)/geometry.cell-gr+.015);
 drag.col=Math.floor((event.clientX-geometry.x)/geometry.cell-gc+.015);
 drag.valid=drag.piece.cells.every(([r,c])=>{r+=drag.row;c+=drag.col;return r>=0&&r<8&&c>=0&&c<8&&state.board[r][c]===0;});
 drag.ghost.style.left=(event.clientX-gc*geometry.cell)+'px';drag.ghost.style.top=(event.clientY-gr*geometry.cell)+'px';drag.ghost.classList.toggle('bad',!drag.valid);
 document.querySelectorAll('.drop-preview,.invalid').forEach(n=>n.classList.remove('drop-preview','invalid'));
 for(const[r,c]of drag.piece.cells){const cell=document.querySelector(`.cell[data-row="${r+drag.row}"][data-col="${c+drag.col}"]`);cell?.classList.add('drop-preview');if(!drag.valid)cell?.classList.add('invalid');}
}
function cancelDrag(){if(!drag)return;drag.ghost.remove();drag.slot.classList.remove('dragging');drag=null;document.querySelectorAll('.drop-preview,.invalid').forEach(n=>n.classList.remove('drop-preview','invalid'));hint(activePlan);schedulePoll();}
async function endDrag(event){
 if(!drag)return;moveDrag(event);
 const request={piece_id:drag.piece.id,row:drag.row,col:drag.col,grab:drag.grab,state_id:drag.state_id},valid=drag.valid;cancelDrag();
 if(!valid){$('message').textContent='Thả trong vùng trống của bàn. Điện thoại chưa bị thao tác.';return;}
 setBusy(true);$('message').textContent='Đang đặt khối trên S23+ và đọc luồng video để kiểm tra…';
 try{render(await api('/api/move',request));}
 catch(err){$('message').textContent=err.message;updateScreenOnly();state=null;$('overlay').hidden=false;$('overlay-title').textContent='Cần đọc luồng video';$('overlay-detail').textContent=err.message;}
 finally{setBusy(false);schedulePoll();}
}
async function tap(x,y){
 if(busy||drag||window.liveTouchActive)return;setBusy(true);
 try{render(await api('/api/tap',{x,y}));$('message').textContent='Đã gửi thao tác chạm và đọc lại điện thoại.';}
 catch(err){$('message').textContent=err.message;updateScreenOnly();}
 finally{setBusy(false);schedulePoll();}
}
window.addEventListener('pointermove',moveDrag);
window.addEventListener('pointerup',endDrag);
window.addEventListener('pointercancel',cancelDrag);
window.addEventListener('keydown',e=>{if(e.key==='Escape')cancelDrag();});
$('refresh').onclick=refresh;
$('restart').onclick=()=>tap(540,1880);
window.refreshHints=refresh;
api('/api/session').then(session=>{token=session.token;refresh();}).catch(err=>{$('message').textContent=err.message;});
