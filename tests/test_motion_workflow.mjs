import fs from 'node:fs';
import test from 'node:test';
import assert from 'node:assert/strict';

const official=JSON.parse(fs.readFileSync('workflows/ltx-2.5-motion-track.official.json','utf8'));
const adapted=JSON.parse(fs.readFileSync('workflows/comfy-ltx-loop-motion.json','utf8'));
test('Official generation, guide injection and decode remain unchanged',()=>{
  for(const name of ['Load Models','Sampler - Distilled (8 steps)','Preprocess','Decode']) {
    assert.deepEqual(adapted.definitions.subgraphs.find(s=>s.name===name),
                     official.definitions.subgraphs.find(s=>s.name===name));
  }
});
test('Every top-level socket link is consistent',()=>{
  for(const [id,source,slot,target,input] of adapted.links) {
    assert.ok(adapted.nodes.find(n=>n.id===source).outputs[slot].links.includes(id));
    assert.equal(adapted.nodes.find(n=>n.id===target).inputs[input].link,id);
  }
});
test('Preparation uses original image and saved selection has no generation links',()=>{
  const editor=adapted.nodes.find(n=>n.type==='ComfyLTXLoopMotionEditor');
  assert.equal(editor.widgets_values[7],'models/Qwen3.5-9B');
  assert.deepEqual(editor.widgets_values.slice(8,11),['local Qwen3.5','{}','render']);
  assert.deepEqual(editor.widgets_values.slice(11),[false,'','model','character',true,true,'free_motion']);
  const link=adapted.links.find(l=>l[0]===editor.inputs[0].link);
  assert.equal(adapted.nodes.find(n=>n.id===link[1]).type,'LoadImage');
  const selector=adapted.nodes.find(n=>n.type==='ComfyLTXLoopSavedCandidate');
  assert.equal(selector.inputs.length,0);
  const finish=adapted.nodes.find(n=>n.type==='ComfyLTXLoopFinish');
  assert.ok(finish);
  assert.deepEqual(finish.widgets_values,['1080p','Fast',4]);
  assert.equal(adapted.links.find(l=>l[0]===finish.inputs[0].link)[1],selector.id);
  assert.equal(adapted.nodes.some(n=>n.type==='ComfyLTXLoopUpscale'),false);
  const saver=adapted.nodes.find(n=>n.type==='ComfyLTXLoopSaveCandidate');
  assert.equal(saver.inputs[3].name,'source_image');
  assert.deepEqual(adapted.links.find(l=>l[0]===saver.inputs[3].link).slice(1,5),[editor.id,7,saver.id,3]);
});
test('Recorded canvas bypasses official resizes',()=>{
  const input=adapted.definitions.subgraphs.find(s=>s.name==='Input Parameters');
  assert.equal(input.nodes.some(n=>n.type==='ResizeImageMaskNode'),false);
  // The frontend cannot flatten a subgraph input wired straight to its output.
  assert.equal(input.links.some(l=>l.target_id===-20&&l.target_slot===1),false);
  const consumer=adapted.nodes.find(n=>n.id===9002);
  const link=adapted.links.find(l=>l[0]===consumer.inputs[4].link);
  assert.deepEqual(link.slice(1,5),[10000,0,9002,4]);
});
test('Render saver retains Input Parameters and generation ancestors',()=>{
  const reached=new Set();
  function visit(id) {
    if(reached.has(id))return;
    reached.add(id);
    for(const link of adapted.links.filter(l=>l[3]===id))visit(link[1]);
  }
  visit(4852);
  for(const id of [2004,10000,5014,9002,5516,5518,4852])assert.ok(reached.has(id),`missing ${id}`);
  assert.equal(reached.has(10002),false);
});
