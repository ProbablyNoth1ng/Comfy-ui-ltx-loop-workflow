import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';

class Element {
  constructor(tag) {this.tag=tag;this.style={};this.children=[];this.value='';this.checked=false;}
  append(child) {this.children.push(child);if(this.tag==='select'&&this.children.length===1)this.value=String(child.value??'');}
  replaceChildren() {this.children=[];this.value='';}
  setAttribute(name,value) {this[name]=value;}
  setPointerCapture() {}
  getBoundingClientRect() {return{left:0,top:0,width:480,height:300};}
  getContext() {return new Proxy({}, {get:(_,name)=>name==='drawImage'?(image=>{this.drawnImage=image;}):()=>{},set:()=>true});}
}
const descendants=root=>[root,...root.children.flatMap(descendants)];
let instance=0;
async function fixture() {
  globalThis.document={createElement:tag=>new Element(tag),body:new Element('body')};
  globalThis.Image=class {naturalWidth=600;naturalHeight=900;set src(value){this.source=value;this.onload?.();}};
  const values={motion_prompt:'Hair sway. Face still.',requested_parts:'auto',duration:6,fps:24,strength:.01,
    short_side:720,seed:42,vision_model:'models/Qwen3-VL-8B-Instruct',preparation:'local Qwen3.5',plan_json:'{}',stage:'render',
    animate_background:false,background_prompt:'',background_preparation:'model',prepare_target:'character',
    use_character_points:true,use_background_points:true};
  const node={id:2,type:'ComfyLTXLoopMotionEditor',size:[520,300],properties:{},
    widgets:Object.entries(values).map(([name,value])=>({name,value})),
    addDOMWidget(name,type,root){this.root=root;return{};},setSize(size){this.size=size;}};
  const load={id:1,type:'LoadImage',widgets:[{name:'image',value:'source.png'}]};
  const app={graph:{_nodes:[load,node],extra:{},setDirtyCanvas(){}},registerExtension(extension){this.extension=extension;}};
  const requests=[];
  const api={apiURL:path=>path,fetchApi:async(path,options)=>{requests.push(path);return{ok:true,json:async()=>({...JSON.parse(options.body),review:{state:'reviewed'}})};}};
  globalThis.comfy_ltx_loopEditorFixture={app,api};
  const source=await readFile(new URL('../comfy_nodes/comfy_ltx_loop/web/comfy_ltx_loop.js',import.meta.url),'utf8');
  const modified=source.replace(/import \{ app \}[^\n]+\nimport \{ api \}[^\n]+/,'const {app,api}=globalThis.comfy_ltx_loopEditorFixture;')
    .replace(/from '(\.\/[^']+)'/g,(_,path)=>`from '${new URL('../comfy_nodes/comfy_ltx_loop/web/'+path,import.meta.url).href}'`);
  await import('data:text/javascript;base64,'+Buffer.from(modified+`\n// editor fixture ${instance++}`).toString('base64'));
  app.extension.nodeCreated(node);
  const widget=name=>node.widgets.find(w=>w.name===name);
  const plan=()=>JSON.parse(widget('plan_json').value);
  const points=Array.from({length:24},(_,i)=>({label:`hair ${i}`,x:.2+i*.005,y:.4,
    body_part:'hair',motion_role:'move',reason:'Requested hair sway',enabled:true,strength:1,
    path:[{t:0,x:.2+i*.005,y:.4},{t:.5,x:.21+i*.005,y:.4},{t:1,x:.2+i*.005,y:.4}]}));
  points[23]={...points[23],label:'eye',motion_role:'anchor',body_part:'face',reason:'Face still'};
  points[23].path=points[23].path.map(k=>({...k,x:points[23].x}));
  node.onExecuted({motion_plan:[{schema:'comfy-ltx-loop-motion-plan/1',source_size:[600,900],transform:{canvas:[768,1088]},
    frames:145,prompt:values.motion_prompt,requested:['auto'],duration:6,fps:24,strength:.01,short_side:720,
    analysis:{preparation:'local Qwen3.5',model_path:'models/Qwen3.5-9B'},landmarks:points,review:{state:'pending'}}],bg_image:['fixture']});
  return{node,app,widget,plan,requests,elements:()=>descendants(node.root),
    button:text=>descendants(node.root).find(el=>el.tag==='button'&&el.textContent===text),
    control:title=>descendants(node.root).find(el=>el.title===title)};
}

test('Qwen preparation populates bundled paths while preserving custom and serialized paths',async()=>{
  const f=await fixture();assert.equal(f.widget('vision_model').value,'models/Qwen3.5-9B');
  const mode=f.widget('preparation');mode.value='local Qwen';mode.callback?.(mode.value);
  assert.equal(f.widget('vision_model').value,'models/Qwen3-VL-8B-Instruct');
  f.widget('vision_model').value='/custom/snapshot';mode.value='local Qwen3.5';mode.callback?.(mode.value);
  assert.equal(f.widget('vision_model').value,'/custom/snapshot');
  f.node.onConfigure();assert.equal(f.widget('vision_model').value,'/custom/snapshot');
});

test('point group switches preserve saved points and require renewed review on reopen',async()=>{
  const f=await fixture();
  await f.button('Accept point review').onclick();
  const character=f.control('Use character points');
  const scenery=f.control('Use background points');
  assert.ok(character);assert.ok(scenery);
  character.checked=false;character.onchange();
  scenery.checked=false;scenery.onchange();
  assert.equal(f.plan().review.state,'pending');
  assert.equal(f.plan().landmarks.length,24);
  assert.equal(f.plan().use_character_points,false);
  assert.equal(f.plan().use_background_points,false);
  f.widget('plan_json').value='{}';f.node.onConfigure();
  assert.equal(f.plan().use_character_points,false);
  assert.equal(f.plan().landmarks.length,24);
  character.checked=true;character.onchange();
  assert.equal(f.plan().review.state,'pending');
});

test('direct Render queues without a prepared plan',async()=>{
  const f=await fixture();
  f.widget('plan_json').value='{}';
  f.app.graph._nodes.push({id:5,type:'ComfyLTXLoopSaveCandidate'});
  f.app.graphToPrompt=async()=>({workflow:{},output:{
    '1':{class_type:'LoadImage',inputs:{}},
    '2':{class_type:'ComfyLTXLoopMotionEditor',inputs:{image:['1',0],plan_json:'{}'}},
    '5':{class_type:'ComfyLTXLoopSaveCandidate',inputs:{motion_plan:['2',2]}}
  }});
  let queued;
  globalThis.comfy_ltx_loopEditorFixture.api.queuePrompt=async(_index,prompt)=>{queued=prompt;return{prompt_id:'render'};};
  await f.button('Render').onclick();
  assert.equal(queued.output['2'].inputs.stage,'render');
  assert.equal(Object.keys(queued.output).length,3);
});

test('dense landmarks select nearest dot, edit roles and retain semantic edits on reopen',async()=>{
  const f=await fixture();
  const rows=f.elements().filter(el=>String(el['aria-label']??'').startsWith('Select landmark'));
  assert.equal(rows.length,24);
  assert.notEqual(rows[0].style.color,rows[23].style.color);
  const canvas=f.elements().find(el=>el.tag==='canvas');
  // Image is 200x300 at x=140. Neighbors are one pixel apart; select exact point 18.
  canvas.onpointerdown({clientX:140+(.2+18*.005)*200,clientY:120,pointerId:1});
  assert.equal(f.elements().find(el=>el.placeholder==='Point label').value,'hair 18');
  const role=f.control('Motion role');assert.ok(role);role.value='anchor';role.onchange();
  assert.equal(f.plan().landmarks[18].motion_role,'anchor');
  assert.ok(f.plan().landmarks[18].path.every(k=>Math.abs(k.x-.29)<1e-10&&k.y===.4));
  const body=f.control('Part / object');body.value='face';body.oninput();
  const reason=f.control('Role reason');reason.value='Keep the eyebrow stationary';reason.oninput();
  const serialized=JSON.stringify(f.plan());f.widget('plan_json').value='{}';f.node.onConfigure();
  assert.equal(JSON.stringify(f.plan()),serialized);
  assert.equal(f.plan().landmarks[18].reason,'Keep the eyebrow stationary');
  assert.equal(f.plan().review.state,'pending');
});

test('source image clears points and prompt changes invalidate review',async()=>{
  const f=await fixture();await f.button('Accept point review').onclick();
  assert.equal(f.plan().review.state,'reviewed');
  const original=JSON.stringify(f.plan().landmarks);
  f.widget('vision_model').value='other';f.widget('vision_model').callback?.('other');
  f.widget('motion_prompt').value='New prompt';f.widget('motion_prompt').callback?.('New prompt');
  assert.equal(f.plan().review.state,'pending');
  f.widget('strength').value=.02;f.widget('strength').callback?.(.02);
  f.app.graph._nodes[0].widgets[0].value='new.png';
  f.app.graph._nodes[0].widgets[0].callback?.('new.png');
  assert.match(f.elements().find(el=>el.tag==='canvas').drawnImage.source,/new.png/);
  assert.deepEqual(f.plan(),{});
  f.widget('plan_json').value='{}';f.node.onConfigure();
  assert.deepEqual(f.plan(),{});
  assert.equal(f.requests.length,1);
});

test('background placement uses its group and prompt clearing preserves points',async()=>{
  const f=await fixture();
  const prompt=f.widget('background_prompt');prompt.value='Leaves sway';prompt.callback?.(prompt.value);
  const groups=f.control('New point group');groups.value='background';groups.onchange();
  f.button('Add point').onclick();
  const canvas=f.elements().find(el=>el.tag==='canvas');
  canvas.onpointerdown({clientX:240,clientY:150,pointerId:1});
  assert.equal(f.plan().landmarks.at(-1).group,'background');
  const added=f.plan().landmarks.length-1;
  canvas.onpointerdown({clientX:240,clientY:150,pointerId:2});
  canvas.onpointermove({clientX:250,clientY:155,pointerId:2});canvas.onpointerup();
  assert.equal(f.plan().landmarks[added].group,'background');
  assert.ok(f.plan().landmarks[added].x>.5);
  const saved=JSON.stringify(f.plan());f.widget('plan_json').value='{}';f.node.onConfigure();
  assert.equal(JSON.stringify(f.plan()),saved);
  assert.ok(f.elements().some(el=>el['aria-label']==='background points'));
  f.button('Delete').onclick();
  assert.equal(f.plan().landmarks.length,24);
  assert.equal(f.plan().landmarks.filter(p=>p.group==='background').length,0);
  f.button('Add point').onclick();canvas.onpointerdown({clientX:240,clientY:150,pointerId:3});
  prompt.value='   ';prompt.callback?.(prompt.value);
  assert.equal(f.plan().landmarks.length,25);
  assert.equal(f.plan().landmarks.at(-1).group,'background');
  assert.equal(f.plan().background.enabled,false);
});

test('visible points filters markers, lists, and selection without changing groups',async()=>{
  const f=await fixture();
  const p=f.plan();
  p.landmarks.push({...p.landmarks[0],label:'leaf',group:'background',x:.75,y:.3});
  f.widget('plan_json').value=JSON.stringify(p);f.node.onConfigure();
  const visible=f.control('Visible points');assert.ok(visible);
  visible.value='background';visible.onchange();
  assert.equal(f.elements().filter(el=>String(el['aria-label']??'').startsWith('Select landmark')).length,1);
  const canvas=f.elements().find(el=>el.tag==='canvas');
  canvas.onpointerdown({clientX:180,clientY:120,pointerId:1});
  assert.equal(f.elements().find(el=>el.placeholder==='Point label').value,'');
  visible.value='all';visible.onchange();
  assert.equal(f.plan().landmarks.at(-1).group,'background');
});

test('legacy background checkbox state migrates from Background motion and invalidates review',async()=>{
  const f=await fixture();
  const p=f.plan();p.review={state:'reviewed'};p.background={enabled:false,prompt:'',preparation:'manual'};
  f.widget('plan_json').value=JSON.stringify(p);
  f.widget('background_prompt').value='Leaves sway';
  f.widget('background_preparation').value='manual';
  f.node.onConfigure();
  assert.equal(f.plan().background.enabled,true);
  assert.equal(f.plan().review.state,'pending');
  assert.match(f.elements().find(el=>el.tag==='p').textContent,/migrated/i);
});
