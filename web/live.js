const image=document.getElementById('phone'),offline=document.getElementById('live-offline');
const context=image.getContext('2d',{alpha:false});
let control,video,pressed=false,pointer=null,pending=null,timer=null,width=1080,height=2340,lastPosition={x:0,y:0};
let latest=null,drawing=false,frames=0;
window.liveTouchActive=false;
function coordinates(e){
 const rect=image.getBoundingClientRect();
 // Account for letterboxing at every viewport.
 const scale=Math.min(rect.width/width,rect.height/height),w=width*scale,h=height*scale;
 return {x:Math.max(0,Math.min(width-1,Math.round((e.clientX-rect.left-(rect.width-w)/2)/scale))),
 y:Math.max(0,Math.min(height-1,Math.round((e.clientY-rect.top-(rect.height-h)/2)/scale)))};
}
function send(action,position){
 if(control?.readyState!==WebSocket.OPEN)return;
 control.send(JSON.stringify({action,...position}));
}
function flush(){clearTimeout(timer);timer=null;if(pending){send(2,pending);pending=null;}}
image.addEventListener('pointerdown',e=>{
 if(e.button!==0||pressed||!offline.hidden||control?.readyState!==WebSocket.OPEN)return;
 e.preventDefault();pressed=true;pointer=e.pointerId;window.liveTouchActive=true;
 image.setPointerCapture(pointer);lastPosition=coordinates(e);send(0,lastPosition);
});
image.addEventListener('pointermove',e=>{
 if(!pressed||e.pointerId!==pointer)return;
 lastPosition=coordinates(e);pending=lastPosition;if(!timer)timer=setTimeout(flush,16);
});
function release(e,cancel=false){
 if(!pressed)return;flush();if(e)lastPosition=coordinates(e);
 pressed=false;window.liveTouchActive=false;send(cancel?3:1,lastPosition);
 if(pointer!==null&&image.hasPointerCapture(pointer))image.releasePointerCapture(pointer);
 pointer=null;setTimeout(()=>window.refreshHints?.(),500);
}
image.addEventListener('pointerup',e=>release(e));
image.addEventListener('pointercancel',e=>release(e,true));
image.addEventListener('lostpointercapture',()=>release(null,true));
window.addEventListener('blur',()=>release(null,true));
window.addEventListener('keydown',e=>{if(e.key==='Escape')release(null,true);});
async function draw(){
 if(drawing)return;drawing=true;
 try{while(latest){
 const blob=latest;latest=null;const bitmap=await createImageBitmap(blob);
 if(image.width!==bitmap.width||image.height!==bitmap.height){image.width=bitmap.width;image.height=bitmap.height;}
 context.drawImage(bitmap,0,0);bitmap.close();frames++;image.dataset.frames=frames;
 }}finally{drawing=false;}
}
async function connect(){
 if(video)video.close();
 const session=await fetch('/api/session').then(r=>r.json());
 const base='ws://127.0.0.1:8766';
 control=new WebSocket(base+'/control?token='+encodeURIComponent(session.token));
 control.onmessage=e=>{const data=JSON.parse(e.data);if(data.error)document.getElementById('message').textContent=data.error;};
 control.onclose=()=>{release(null,true);setTimeout(connect,1500);};
 video=new WebSocket(base+'/video?token='+encodeURIComponent(session.token));video.binaryType='blob';
 video.onmessage=e=>{latest=e.data;draw();};
 video.onclose=()=>{offline.hidden=false;offline.textContent='Đang kết nối lại video';};
}
async function status(){
 try{
 const data=await fetch('/api/live-status').then(r=>r.json());width=data.width;height=data.height;
 const ready=data.live&&frames>0&&control?.readyState===WebSocket.OPEN;
 offline.hidden=ready;
 const badge=document.getElementById('connection');badge.classList.toggle('error',!ready);
 badge.innerHTML=ready?'<i></i>S23+ · LIVE':'<i></i>Chờ kết nối S23+';
 offline.textContent=data.error||'Đang mở luồng trực tiếp';
 }catch{offline.hidden=false;offline.textContent='Máy chủ local đang ngắt kết nối';}
 setTimeout(status,700);
}
connect().catch(e=>offline.textContent=e.message);status();
