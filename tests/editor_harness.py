"""Local browser fixture for the real editor extension, without GPU/ComfyUI.

Run python tests/editor_harness.py then open http://127.0.0.1:8766.
Queueing is simulated; this does not qualify a deployed ComfyUI frontend.
"""
import base64
import copy
import json
import subprocess
import sys
import tempfile
from http.server import BaseHTTPRequestHandler, HTTPServer
from io import BytesIO
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PIL import Image, ImageDraw
from comfy_ltx_loop.motion import new_plan, review_plan

ROOT = Path(__file__).resolve().parents[1]
image = Image.new('RGB',(600,900),'#354860')
painter = ImageDraw.Draw(image)
painter.ellipse((140,130,460,500),fill='#e1c3b0')
painter.polygon([(130,370),(160,110),(450,120),(480,470),(390,260),(250,210)],fill='#25233f')
painter.polygon([(100,850),(180,510),(410,510),(530,850)],fill='#7092a4')
buffer=BytesIO();image.save(buffer,format='PNG');PNG=buffer.getvalue()
PLAN = new_plan('fixture',(600,900),'Gentle hair sway. Stationary camera.',
                ['hair tip','hair root','head','shoulder'],[],6,24,.01,720)
QWEN_PLAN = new_plan('fixture',(600,900),'Gentle hair sway. Stationary camera.',
                ['hair tip','hair root','head','shoulder'],[
                    {'label':'hair tip','x':.28,'y':.18},
                    {'label':'hair root','x':.49,'y':.19},
                    {'label':'head','x':.5,'y':.32},
                    {'label':'shoulder','x':.52,'y':.58}],6,24,.01,720)
FAILED_PLAN = new_plan('fixture',(600,900),'Gentle hair sway. Stationary camera.',
                ['hair tip','hair root','head','shoulder'],[],6,24,.01,720,
                ['Automatic preparation failed: missing hair tip. Add/edit points manually or retry.'])
DENSE_PLAN = new_plan('fixture',(600,900),'Gentle hair sway. Stationary camera.',
                ['hair tip','hair root','head','shoulder'],[
                    dict(label=f'hair strand {i+1}',x=.23+i*.027,y=.18+(i%3)*.06,
                         body_part='hair',motion_role='move',reason='Synthetic hair sway fixture')
                    for i in range(16)] + [
                    dict(label=label,x=x,y=y,body_part=part,motion_role='anchor',reason='Stationary fixture part')
                    for label,x,y,part in [('hair root',.49,.19,'hair'),('head',.5,.32,'head'),
                                          ('left shoulder',.3,.58,'shoulder'),('right shoulder',.7,.58,'shoulder')]],
                6,24,.01,720)
BACKGROUND_PLAN = copy.deepcopy(DENSE_PLAN)
BACKGROUND_PLAN['background'] = {'enabled':True,'prompt':'Gently sway the visible leaves',
    'preparation':'manual','prepared_prompt':'Gently sway the visible leaves','prepared_preparation':'manual'}
BACKGROUND_PLAN['landmarks'].append({**new_plan('fixture',(600,900),'leaves',['auto'],[
    dict(label='leaf tip',x=.75,y=.3,body_part='foliage',motion_role='move',reason='Requested leaf sway')
])['landmarks'][0],'group':'background'})
COMBINED_PLAN = copy.deepcopy(BACKGROUND_PLAN)
RECORD = {'schema':'comfy-ltx-loop-render-handle/1','kind':'candidate','state':'awaiting_visual_review',
          'frame_count':72,'fps':24,'dimensions':[128,72],'feedback':['Local playback fixture.']}
CANDIDATES = ['candidate-fixture-new/record.json','candidate-fixture-old/record.json']
VIDEO = b''

HTML = '''<!doctype html><meta charset="utf-8"><title>Comfy LTX Loop editor test fixture</title>
<style>body{background:#0d1117;color:white;font:14px system-ui;margin:20px}.panels{display:flex;gap:16px;align-items:start;overflow-x:auto}.panel{flex:0 0 520px}pre{white-space:pre-wrap}input{margin:3px}</style>
<h1>Comfy LTX Loop · local editor fixture</h1><p>Real extension; simulated queue. No GPU generation.</p>
<button id="qwen-fixture">Show Qwen points</button><button id="failed-fixture">Show Qwen failure</button>
<button id="dense-fixture">Show 20 semantic points</button><button id="background-fixture">Show background points</button>
<button id="invalid-fixture">Show invalid Prepare</button><button id="run-fixture">Run</button><button id="run-again-fixture">Run again</button><button id="auto-fixture">Auto queue</button>
<button id="reopen-fixture">Simulate reopen</button>
<button id="render-fixture">Simulate completed render</button>
<label>Saved candidate <select id="candidate-fixture"><option value="candidate-fixture-new/record.json">Latest render</option><option value="candidate-fixture-old/record.json">Older render</option></select></label>
<div class="panels"><section id="editor" class="panel"></section><section id="outputs" class="panel"></section></div>
<pre id="queue">No stage queued</pre>
<script type="module">
import {app} from '/scripts/app.js';import {api} from '/scripts/api.js';
import '/extensions/comfy_ltx_loop/comfy_ltx_loop.js';
const make=(id,type,values,parent)=>({id,type,comfyClass:type,size:[520,300],properties:{},
 widgets:Object.entries(values).map(([name,value])=>({name,value,options:{values:[]}})),
 addDOMWidget(name,type,root){parent.append(root);return{};},setSize(size){this.size=size;}});
const editor=make(2,'ComfyLTXLoopMotionEditor',{motion_prompt:'Gentle hair sway. Stationary camera.',
 requested_parts:'hair tip, hair root, head, shoulder',duration:6,fps:24,strength:.01,short_side:720,seed:42,
 vision_model:'models/Qwen3-VL-8B-Instruct',preparation:'manual',plan_json:'{}',stage:'render',
 animate_background:false,background_prompt:'',background_preparation:'model',prepare_target:'character',
 use_character_points:true,use_background_points:true},document.querySelector('#editor'));
const saver=make(5,'ComfyLTXLoopSaveCandidate',{},document.querySelector('#outputs'));
const selector=make(6,'ComfyLTXLoopSavedCandidate',{candidate:'Select a saved candidate'},document.querySelector('#outputs'));
const upscale=make(7,'ComfyLTXLoopUpscale',{resolution:'1440p',chunk_size:4},document.querySelector('#outputs'));
const load=make(1,'LoadImage',{image:'fixture.png'},document.querySelector('#editor'));
app.graph._nodes=[load,editor,saver,selector,upscale];
await app.extension.setup();for(const node of app.graph._nodes)app.extension.nodeCreated(node);
api.executed=(id,message)=>app.graph._nodes.find(node=>node.id===id)?.onExecuted(message);
document.getElementById('candidate-fixture').onchange=async event=>{
 const choice=selector.widgets.find(w=>w.name==='candidate');choice.value=event.target.value;await choice.callback(choice.value);
};
document.getElementById('render-fixture').onclick=async()=>saver.onExecuted({
 preview_paths:['comfy-ltx-loop/candidate-fixture-new/loop.mp4','comfy-ltx-loop/candidate-fixture-new/seam.mp4'],
 render_handle:[await(await fetch('/comfy-ltx-loop/record?candidate=candidate-fixture-new%2Frecord.json')).json()]});
for(const [id,path] of [['qwen-fixture','/fixture-qwen-plan'],['failed-fixture','/fixture-failed-plan'],['dense-fixture','/fixture-dense-plan'],['background-fixture','/fixture-background-plan']])
 document.getElementById(id).onclick=async()=>editor.onExecuted({motion_plan:[await(await fetch(path)).json()],
 bg_image:[await(await fetch('/fixture-image')).text()]});
document.getElementById('reopen-fixture').onclick=()=>{editor.widgets.find(w=>w.name==='plan_json').value='{}';editor.onConfigure();};
document.getElementById('invalid-fixture').onclick=()=>editor.onExecuted({motion_plan:[{schema:'invalid'}]});
document.getElementById('run-fixture').onclick=()=>app.queuePrompt(0,1);
document.getElementById('run-again-fixture').onclick=()=>app.queuePrompt(0,1);
document.getElementById('auto-fixture').onclick=()=>app.queuePrompt(0,1,{autoQueue:true});
editor.onExecuted({motion_plan:[await(await fetch('/fixture-plan')).json()],bg_image:[await(await fetch('/fixture-image')).text()]});
</script>'''

APP = '''export const app={graph:{_nodes:[],setDirtyCanvas(){}},registerExtension(extension){this.extension=extension;},
 async queuePrompt(number,batchCount,options){const {workflow,output}=await this.graphToPrompt();return globalThis.fixtureApi.queuePrompt(number,{output,workflow},options);},
 async graphToPrompt(){const editor=this.graph._nodes.find(n=>n.id===2);
 const inputs=Object.fromEntries(editor.widgets.map(w=>[w.name,w.value]));inputs.image=['1',0];
 return{workflow:{extra:{}},output:{1:{class_type:'LoadImage',inputs:{image:'fixture.png'}},
 2:{class_type:'ComfyLTXLoopMotionEditor',inputs},3:{class_type:'UNETLoader',inputs:{}},
 4:{class_type:'Sampler',inputs:{model:['3',0],canvas:['2',0]}},
 5:{class_type:'ComfyLTXLoopSaveCandidate',inputs:{video:['4',0],motion_plan:['2',2]}},
 6:{class_type:'ComfyLTXLoopSavedCandidate',inputs:{candidate:this.graph._nodes.find(n=>n.id===6).widgets.find(w=>w.name==='candidate').value}},
 7:{class_type:'ComfyLTXLoopUpscale',inputs:{candidate:['6',0]}}}};}};'''

API = '''export const api={apiURL:path=>path,fetchApi:(path,options)=>fetch(path,options),
 async queuePrompt(number,prompt){document.querySelector('#queue').textContent=JSON.stringify(prompt.output,null,2);
 const data=await(await fetch('/fixture-queue',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(prompt)})).json();
 if(data.ui)this.executed(data.node,data.ui);return{prompt_id:'fixture',node_errors:{}};}};globalThis.fixtureApi=api;'''

class Handler(BaseHTTPRequestHandler):
    def reply(self,data,mime='application/json',status=200):
        payload=data if isinstance(data,bytes) else data.encode() if isinstance(data,str) else json.dumps(data).encode()
        self.send_response(status);self.send_header('Content-Type',mime);self.end_headers();self.wfile.write(payload)
    def do_GET(self):
        parsed=urlsplit(self.path)
        path=parsed.path
        query=parse_qs(parsed.query)
        if path=='/':self.reply(HTML,'text/html')
        elif path=='/scripts/app.js':self.reply(APP,'text/javascript')
        elif path=='/scripts/api.js':self.reply(API,'text/javascript')
        elif path=='/fixture-plan':self.reply(PLAN)
        elif path=='/fixture-qwen-plan':self.reply(QWEN_PLAN)
        elif path=='/fixture-dense-plan':self.reply(DENSE_PLAN)
        elif path=='/fixture-background-plan':self.reply(BACKGROUND_PLAN)
        elif path=='/fixture-failed-plan':self.reply(FAILED_PLAN)
        elif path=='/fixture-image':self.reply(base64.b64encode(PNG),'text/plain')
        elif path=='/view':
            # Match ComfyUI's filename/subfolder contract; the old URL must fail.
            filename=Path(query.get('filename',[''])[0]).name
            subfolder=query.get('subfolder',[''])[0]
            if filename=='fixture.png':self.reply(PNG,'image/png')
            elif (filename in ('loop.mp4','seam.mp4') and query.get('type')==['output']
                  and subfolder in ('comfy-ltx-loop/candidate-fixture-new','comfy-ltx-loop/candidate-fixture-old','comfy-ltx-loop/finish-fixture')):
                self.reply(VIDEO,'video/mp4')
            else:self.reply('Preview file not found','text/plain',404)
        elif path=='/comfy-ltx-loop/candidates':self.reply(CANDIDATES)
        elif path=='/comfy-ltx-loop/record':
            candidate=query.get('candidate',[''])[0]
            if candidate in CANDIDATES:
                self.reply(dict(RECORD,directory='/fixture/'+candidate.rsplit('/',1)[0],record='/fixture/'+candidate))
            else:self.reply('Record not found','text/plain',404)
        elif path.startswith('/extensions/comfy_ltx_loop/'):
            name=path.rsplit('/',1)[-1]
            if name not in ('comfy_ltx_loop.js','stages.mjs','geometry.mjs','queue_control.mjs'):self.reply({},status=404);return
            self.reply((ROOT/'comfy_nodes/comfy_ltx_loop/web'/name).read_bytes(),'text/javascript')
        else:self.reply({},status=404)
    def do_POST(self):
        data=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        if self.path=='/comfy-ltx-loop/review':
            try:self.reply(review_plan(data))
            except (ValueError,KeyError,TypeError) as error:self.reply({'error':str(error)},status=400)
        elif self.path=='/fixture-queue':
            editor=next((n for n in data['output'].values() if n['class_type']=='ComfyLTXLoopMotionEditor'),None)
            if editor and editor['inputs']['stage']=='prepare':
                target=editor['inputs'].get('prepare_target','character')
                self.reply({'node':2,'ui':{'motion_plan':[COMBINED_PLAN if target=='both' else BACKGROUND_PLAN if target=='background' else PLAN],
                    'bg_image':[base64.b64encode(PNG).decode()]}})
            elif any(n['class_type']=='ComfyLTXLoopSaveCandidate' for n in data['output'].values()):
                self.reply({'node':5,'ui':{'preview_paths':['comfy-ltx-loop/candidate-fixture-new/loop.mp4','comfy-ltx-loop/candidate-fixture-new/seam.mp4'],'render_handle':[RECORD]}})
            elif any(n['class_type']=='ComfyLTXLoopUpscale' for n in data['output'].values()):
                self.reply({'node':7,'ui':{'preview_paths':['comfy-ltx-loop/finish-fixture/loop.mp4','comfy-ltx-loop/finish-fixture/seam.mp4'],'render_handle':[dict(RECORD,kind='finish')]}})
            else:self.reply({})
        else:self.reply({},status=404)

if __name__=='__main__':
    with tempfile.TemporaryDirectory() as tmp:
        clip=Path(tmp)/'preview.mp4'
        subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','lavfi',
                        '-i','testsrc2=size=128x72:rate=24:duration=3','-an','-c:v','libx264',
                        '-pix_fmt','yuv420p','-movflags','+faststart',str(clip)],check=True)
        VIDEO=clip.read_bytes()
    print('Editor fixture at http://127.0.0.1:8766',flush=True)
    HTTPServer(('127.0.0.1',8766),Handler).serve_forever()
