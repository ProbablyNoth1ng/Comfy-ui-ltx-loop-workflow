import test from 'node:test';
import assert from 'node:assert/strict';
import {installStageQueueControl,installUnsafePromptGuard,resolveStageTargets,isCurrentStageSelection,requireQueueSuccess} from '../comfy_nodes/comfy_ltx_loop/web/queue_control.mjs';

const comfy_ltx_loop = type => ({_nodes:[{id:1,comfyClass:type}]});
const ordinary = {_nodes:[{id:1,comfyClass:'KSampler'}]};

function controlledApp(graph, implementation = async function (...args) { return {receiver:this,args}; }) {
  return {graph, queuePrompt:implementation};
}

test('main Run on an Comfy LTX workflow opens stage controls without queueing', async () => {
  const graph=comfy_ltx_loop('ComfyLTXLoopSaveCandidate');
  let originalCalls=0, shown;
  const app=controlledApp(graph, async () => { originalCalls++; return true; });
  installStageQueueControl(app, value => { shown=value; }, () => assert.fail('unexpected notice'));

  assert.equal(await app.queuePrompt(0,1),false);
  assert.equal(shown,graph);
  assert.equal(originalCalls,0);
});

test('ordinary queues preserve arguments, receiver, result, and errors', async () => {
  const app=controlledApp(ordinary);
  const original=app.queuePrompt;
  installStageQueueControl(app, () => assert.fail('unexpected chooser'), () => assert.fail('unexpected notice'));
  const result=await app.queuePrompt(3,2,{priority:4},'later');
  assert.equal(result.receiver,app);
  assert.deepEqual(result.args,[3,2,{priority:4},'later']);

  const failing=controlledApp(ordinary, async () => { throw new Error('conversion failed'); });
  installStageQueueControl(failing, () => {}, () => {});
  await assert.rejects(failing.queuePrompt(0,1),/conversion failed/);
  assert.notEqual(app.queuePrompt,original);
});

test('explicit partial execution stays on ComfyUI queue path', async () => {
  for (const options of [{queueNodeIds:[1]},[1,2],{partialExecutionTargets:[1]}]) {
    let calls=0;
    const app=controlledApp(comfy_ltx_loop('ComfyLTXLoopMotionEditor'),async function (...args) { calls++; return {receiver:this,args}; });
    installStageQueueControl(app, () => assert.fail('partial run must not open chooser'), () => assert.fail('partial run is not auto queue'));
    const result=await app.queuePrompt(0,1,options);
    assert.equal(calls,1);
    assert.equal(result.receiver,app);
    assert.equal(result.args[2],options);
  }
});

test('auto queue is cancelled with one notice and all Comfy LTX outputs are recognized', async () => {
  for (const type of ['ComfyLTXLoopMotionEditor','ComfyLTXLoopSaveCandidate','ComfyLTXLoopUpscale','ComfyLTXLoopFinish']) {
    let originalCalls=0, notices=0;
    const app=controlledApp(comfy_ltx_loop(type),async () => { originalCalls++; return true; });
    installStageQueueControl(app, () => assert.fail('auto queue must not open chooser'), () => { notices++; });
    assert.equal(await app.queuePrompt(0,1,{autoQueue:true}),false);
    assert.equal(await app.queuePrompt(0,1,{autoQueue:true}),false);
    assert.equal(originalCalls,0);
    assert.equal(notices,1);
  }
});

test('unsafe prompt guard preserves trailing API arguments and rejects mixed stages before submission', async () => {
  let calls=0;
  const api={queuePrompt:async function (...args) { calls++; return {receiver:this,args}; }};
  installUnsafePromptGuard(api);
  const prompt={output:{1:{class_type:'KSampler'}}};
  const options={partialExecutionTargets:[1]};
  const result=await api.queuePrompt(0,prompt,options,'later');
  assert.equal(calls,1);
  assert.equal(result.receiver,api);
  assert.deepEqual(result.args,[0,prompt,options,'later']);

  await assert.rejects(api.queuePrompt(0,{output:{1:{class_type:'ComfyLTXLoopSaveCandidate'},2:{class_type:'ComfyLTXLoopUpscale'}}}),/separate Prepare/i);
  await assert.rejects(api.queuePrompt(0,{output:{1:{class_type:'ComfyLTXLoopSaveCandidate'},2:{class_type:'ComfyLTXLoopFinish'}}}),/separate Prepare/i);
  await assert.rejects(api.queuePrompt(0,{output:{1:{class_type:'ComfyLTXLoopSaveCandidate'},2:{class_type:'ComfyLTXLoopMotionEditor',inputs:{stage:'prepare'}}}}),/cannot start generation/i);
  assert.equal(calls,1);
});

test('stage choices disable missing targets and ambiguous Render editors', () => {
  const one={_nodes:[{id:2,comfyClass:'ComfyLTXLoopMotionEditor'},{id:5,comfyClass:'ComfyLTXLoopSaveCandidate'},{id:7,comfyClass:'ComfyLTXLoopUpscale'}]};
  const targets=resolveStageTargets(one);
  assert.equal(targets.prepare.target.id,2);
  assert.equal(targets.render.target.id,5);
  assert.equal(targets.upscale.target.id,7);
  const newFinish={_nodes:[one._nodes[0],one._nodes[1],{id:8,comfyClass:'ComfyLTXLoopFinish'}]};
  assert.equal(resolveStageTargets(newFinish).upscale.target.id,8);
  assert.match(resolveStageTargets({_nodes:[...one._nodes,{id:8,comfyClass:'ComfyLTXLoopFinish'}]}).upscale.reason,/one output node/i);

  const ambiguous={_nodes:[{id:2,comfyClass:'ComfyLTXLoopMotionEditor'},{id:3,comfyClass:'ComfyLTXLoopMotionEditor'},{id:5,comfyClass:'ComfyLTXLoopSaveCandidate'}]};
  const disabled=resolveStageTargets(ambiguous);
  assert.match(disabled.render.reason,/exactly one motion editor/i);
  assert.match(disabled.upscale.reason,/Comfy LTX Loop Upscale/i);
});

test('a captured stage target cannot submit after a graph change or removal', () => {
  const graph={_nodes:[{id:2,comfyClass:'ComfyLTXLoopMotionEditor'}]};
  const app={graph};
  const target=graph._nodes[0];
  assert.equal(isCurrentStageSelection(app,graph,target),true);
  app.graph={_nodes:[target]};
  assert.equal(isCurrentStageSelection(app,graph,target),false);
  app.graph=graph;graph._nodes=[];
  assert.equal(isCurrentStageSelection(app,graph,target),false);
});

test('a captured target becomes invalid when its stage is ambiguous', () => {
  const target={id:5,comfyClass:'ComfyLTXLoopSaveCandidate'};
  const graph={_nodes:[{id:2,comfyClass:'ComfyLTXLoopMotionEditor'},target]};
  const app={graph};
  assert.equal(isCurrentStageSelection(app,graph,target,'render'),true);
  graph._nodes.push({id:3,comfyClass:'ComfyLTXLoopMotionEditor'});
  assert.equal(isCurrentStageSelection(app,graph,target,'render'),false);
});

test('a stage submission needs a real backend prompt id', () => {
  assert.equal(requireQueueSuccess({prompt_id:'queued-1',node_errors:{}}).prompt_id,'queued-1');
  assert.throws(() => requireQueueSuccess({}),/without a prompt id/i);
  assert.throws(() => requireQueueSuccess({error:'backend rejected'}),/without a prompt id/i);
  assert.throws(() => requireQueueSuccess({prompt_id:'queued-1',node_errors:{5:{errors:['bad']}}}),/validation failed/i);
});
