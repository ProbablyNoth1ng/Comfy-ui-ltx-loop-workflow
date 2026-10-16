// Adapt only input preparation/output persistence. Keep the official sampler,
// model loading, IC-LoRA guide injection and tiled decoding intact.
import fs from 'node:fs';
import crypto from 'node:crypto';

const official='workflows/ltx-2.5-motion-track.official.json';
const graph=JSON.parse(fs.readFileSync(official,'utf8'));
const obsolete=new Set([9004,9006,9007,9008,5508,5544]);
graph.nodes=graph.nodes.filter(n=>!obsolete.has(n.id));
graph.links=graph.links.filter(l=>!obsolete.has(l[1])&&!obsolete.has(l[3]));

function node(id,type,pos,inputs,outputs,values,size=[360,240]) {
    return {id,type,pos,size,flags:{},order:0,mode:0,inputs,outputs,
            properties:{'Node name for S&R':type},widgets_values:values};
}
const editor=node(10000,'ComfyLTXLoopMotionEditor',[450,0],
    [{name:'image',type:'IMAGE',link:null}],
    ['IMAGE','STRING','MOTION_PLAN','FLOAT','FLOAT','INT','STRING'].map((type,i)=>({
        name:['canvas','tracks','motion_plan','fps','duration','seed','prompt'][i],type,links:[]})),
    ['Gentle hair sway. Stationary camera.','auto',6,24,.01,720,
     42,'models/Qwen3.5-9B','local Qwen3.5','{}','render',false,'','model','character',true,true],[540,1050]);
const saver=node(4852,'ComfyLTXLoopSaveCandidate',[2200,0],
    [{name:'video',type:'VIDEO',link:null},{name:'motion_plan',type:'MOTION_PLAN',link:null},
     {name:'seed',type:'INT',widget:{name:'seed'},link:null}],
    [{name:'candidate',type:'RENDER_HANDLE',links:[]}],[42],[540,550]);
graph.nodes=graph.nodes.filter(n=>n.id!==4852);
const selector=node(10001,'ComfyLTXLoopSavedCandidate',[2200,600],[],
    [{name:'RENDER_HANDLE',type:'RENDER_HANDLE',links:[]}],['Select a saved candidate']);
const upscale=node(10002,'ComfyLTXLoopFinish',[2650,600],
    [{name:'candidate',type:'RENDER_HANDLE',link:null}],
    [{name:'RENDER_HANDLE',type:'RENDER_HANDLE',links:[]}],['1080p','Fast',4],[540,550]);
graph.nodes.push(editor,saver,selector,upscale);

let next=14000;
function connect(source,output,target,input,type) {
    graph.links=graph.links.filter(l=>!(l[3]===target&&l[4]===input));
    const id=next++;
    graph.links.push([id,source,output,target,input,type]);
}
connect(2004,0,10000,0,'IMAGE');
connect(10000,0,5014,2,'IMAGE');
connect(10000,0,9002,4,'IMAGE');
connect(10000,6,5014,4,'STRING');
connect(10000,3,5014,7,'FLOAT');
connect(10000,4,5014,8,'FLOAT');
connect(10000,1,9002,9,'STRING');
connect(10000,5,5516,4,'INT');
connect(5518,0,4852,0,'VIDEO');
connect(10000,2,4852,1,'MOTION_PLAN');
connect(10000,5,4852,2,'INT');
connect(10001,0,10002,0,'RENDER_HANDLE');

const parameters=graph.nodes.find(n=>n.id===5014);
parameters.widgets_values[0]=true;
parameters.widgets_values[2]=false; // local prompt, no enhancer rewrite
const inputGraph=graph.definitions.subgraphs.find(s=>s.name==='Input Parameters');
const resizeIds=new Set([4990,5562,5563]);
inputGraph.nodes=inputGraph.nodes.filter(n=>!resizeIds.has(n.id));
inputGraph.links=inputGraph.links.filter(l=>!resizeIds.has(l.origin_id)&&!resizeIds.has(l.target_id));
inputGraph.outputs[1].linkIds=[];
inputGraph.inputs[2].linkIds=[];
inputGraph.inputs[12].linkIds=[];

// Rebuild sockets so stale official links never survive the adaptation.
for(const n of graph.nodes) {
    n.inputs?.forEach(i=>i.link=null);
    n.outputs?.forEach(o=>o.links=[]);
}
for(const [id,source,slot,target,input] of graph.links) {
    const a=graph.nodes.find(n=>n.id===source),b=graph.nodes.find(n=>n.id===target);
    if(!a?.outputs?.[slot]||!b?.inputs?.[input])throw new Error(`Invalid link ${id}`);
    a.outputs[slot].links.push(id);b.inputs[input].link=id;
}
const positions={2004:[0,0],5509:[0,440],5004:[1100,0],5014:[1100,450],
                 9002:[1500,450],5516:[1500,0],5518:[1900,0]};
let noteIndex=0;
for(const n of graph.nodes) {
    if(positions[n.id])n.pos=positions[n.id];
    if(n.type==='MarkdownNote') {n.pos=[(noteIndex++%4)*600,1200+Math.floor(noteIndex/4)*400];}
}
graph.nodes.find(n=>n.id===5527).widgets_values=[
    '## Comfy LTX Loop\nLoad one image and set character motion text. Render directly when no points are active; Prepare and accept point review only when using points.\n\nBackground motion text guides scenery even without points. Blank text excludes background tracks while keeping saved points. Use the Use character points and Use background points switches to include or exclude each saved group. Choose Model or Manual to prepare points. Visible points filters the editor; New point group controls newly placed points. Circles mark character points and squares mark background points.\n\nRun offers Prepare character points, Prepare background points, Prepare both, Render and Upscale. Each choice queues one stage. Switching a point group requires renewed review before rendering with its points.\n\nRender uses the official LTX-2.5 pipeline with a stationary camera. Small generation drift may remain. Inspect continuous and seam previews. Finish the same saved candidate again with Fast, Balanced AI, or Original AI to compare results.'];
graph.groups=[];
graph.last_node_id=10002;graph.last_link_id=next-1;
graph.extra={comfy_ltx_loop:{schema:1,official_sha256:crypto.createHash('sha256').update(fs.readFileSync(official)).digest('hex'),
                          qualification:'pending actual cloud GPU run'}};
fs.writeFileSync('workflows/comfy-ltx-loop-motion.json',JSON.stringify(graph,null,2)+'\n');
console.log('Wrote workflows/comfy-ltx-loop-motion.json');
