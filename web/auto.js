const button=document.getElementById('auto-toggle'),mode=document.getElementById('auto-mode'),status=document.getElementById('auto-status');
let current={active:false},token=null,changing=false,lastMoves=-1;
window.autoActive=false;
async function request(body,retry=true){
 if(!token)token=(await fetch('/api/session').then(r=>r.json())).token;
 const response=await fetch('/api/auto',{method:'POST',headers:{'Content-Type':'application/json','X-Session-Token':token},body:JSON.stringify(body)});
 const data=await response.json();if(response.status===403&&retry){token=null;return request(body,false);}if(!response.ok)throw Error(data.error);return data;
}
function render(data){
 const wasActive=current.active;current=data;window.autoActive=data.active;
 button.textContent=data.active?'■ Dừng Auto':'▶ Auto';button.classList.toggle('running',data.active);
 button.setAttribute('aria-pressed',String(data.active));mode.disabled=data.active||changing;
 status.classList.toggle('running',data.active);
 const search=data.search?.cached?(" · dùng kế hoạch đã tính cho bàn này"):data.search?(' · '+data.search.ms+' ms · xét '+data.search.explored.toLocaleString('vi')+' trạng thái · '+data.search.depth+'/'+data.search.tray_size+' khối'):'';
 const future=data.search?.future_samples?` · qua ${data.search.future_survived}/${data.search.future_samples} kịch bản ${data.search.future_horizon} khay giả định`:'';
 status.textContent=data.message+' · '+data.moves+' nước đã kiểm tra · '+data.levels+' lần chuyển cấp'+search+future;
 if(data.moves!==lastMoves)setTimeout(()=>window.refreshHints?.(),100);
 if(wasActive&&!data.active)setTimeout(()=>window.refreshHints?.(),200);
 lastMoves=data.moves;
}
button.onclick=async()=>{
 if(changing)return;changing=true;button.disabled=true;
 try{render(await request({action:current.active?'stop':'start',mode:mode.value}));}
 catch(error){status.textContent=error.message;}
 finally{changing=false;button.disabled=false;mode.disabled=current.active;}
};
mode.onchange=()=>request({action:"mode",mode:mode.value}).then(data=>{render(data);window.refreshHints?.();}).catch(error=>status.textContent=error.message);
window.addEventListener('keydown',e=>{if(e.key==='Escape'&&current.active)request({action:'stop'}).then(render).catch(()=>{});});
async function poll(){
 try{const response=await fetch('/api/auto');if(response.ok)render(await response.json());}
 catch{}
 setTimeout(poll,600);
}
poll();
