const comfy_ltx_loopClasses = new Set(['ComfyLTXLoopMotionEditor','ComfyLTXLoopSaveCandidate','ComfyLTXLoopUpscale','ComfyLTXLoopFinish']);
const installed = new WeakSet();
const guardedApis = new WeakSet();
const noticedGraphs = new WeakSet();

const nodeClass = node => node?.comfyClass ?? node?.type;
const graphNodes = graph => graph?._nodes ?? graph?.nodes ?? [];
const hasComfyLTXLoopNode = graph => graphNodes(graph).some(node => comfy_ltx_loopClasses.has(nodeClass(node)));

function hasExplicitTargets(options) {
    if (Array.isArray(options)) return true;
    return Boolean(options && typeof options === 'object' &&
        (Array.isArray(options.queueNodeIds) || Array.isArray(options.partialExecutionTargets)));
}

function isAutoQueue(options) {
    return Boolean(options && typeof options === 'object' && options.autoQueue);
}

export function resolveStageTargets(graph) {
    const find = type => graphNodes(graph).filter(node => nodeClass(node) === type);
    const editors=find('ComfyLTXLoopMotionEditor');
    const savers=find('ComfyLTXLoopSaveCandidate');
    const upscalers=[...find('ComfyLTXLoopUpscale'),...find('ComfyLTXLoopFinish')];
    return {
        prepare: editors.length===1 ? {target:editors[0]} : {reason:editors.length?'Prepare points needs one motion editor.':'Prepare points needs an Comfy LTX Loop Motion Editor.'},
        areas: editors.length===1 ? {target:editors[0]} : {reason:editors.length?'Update motion areas needs one motion editor.':'Update motion areas needs an Comfy LTX Loop Motion Editor.'},
        render: editors.length!==1 ? {reason:'Render needs exactly one motion editor; resolve the editor ambiguity.'} : savers.length===1 ? {target:savers[0]} : {reason:savers.length?'Render needs one candidate saver.':'Render needs an Comfy LTX Loop Save Candidate node.'},
        upscale: upscalers.length===1 ? {target:upscalers[0]} : {reason:upscalers.length?'Upscale needs one output node.':'Upscale needs an Comfy LTX Loop Upscale or Comfy LTX Loop Finish node.'}
    };
}

export function isCurrentStageSelection(app, graph, target, stage) {
    if ((app.rootGraph ?? app.graph) !== graph || !graphNodes(graph).includes(target)) return false;
    return !stage || resolveStageTargets(graph)[stage]?.target === target;
}

export function requireQueueSuccess(result) {
    if (result?.node_errors && Object.keys(result.node_errors).length) {
        throw new Error(`queue validation failed: ${JSON.stringify(result.node_errors)}`);
    }
    if (!result?.prompt_id) throw new Error('ComfyUI returned without a prompt id. Check the queue and retry.');
    return result;
}

/**
 * Offer Comfy LTX Loop's stage controls before ComfyUI converts a whole graph.
 * Explicit partial execution deliberately remains ComfyUI's responsibility.
 */
export function installStageQueueControl(app, showStageChooser, showAutoQueueNotice) {
    if (installed.has(app)) return;
    const original = app.queuePrompt;
    if (typeof original !== 'function') throw new Error('ComfyUI app.queuePrompt is unavailable.');
    installed.add(app);
    app.queuePrompt = async function (...args) {
        const graph = app.rootGraph ?? app.graph;
        const options = args[2];
        if (!hasComfyLTXLoopNode(graph) || hasExplicitTargets(options)) return original.apply(this,args);
        if (isAutoQueue(options)) {
            if (!noticedGraphs.has(graph)) {
                noticedGraphs.add(graph);
                showAutoQueueNotice(graph);
            }
            return false;
        }
        showStageChooser(graph);
        return false;
    };
}

/** Preserve the last line of defence when a caller bypasses stage controls. */
export function installUnsafePromptGuard(api) {
    if (guardedApis.has(api)) return;
    const original=api.queuePrompt;
    if (typeof original !== 'function') throw new Error('ComfyUI api.queuePrompt is unavailable.');
    guardedApis.add(api);
    api.queuePrompt=async function (...args) {
        const prompt=args[1]??{};
        const output=prompt.output??{};
        const classes=Object.values(output).map(node=>node.class_type);
        if(classes.some(c=>c==='ComfyLTXLoopUpscale'||c==='ComfyLTXLoopFinish')&&classes.includes('ComfyLTXLoopSaveCandidate')) {
            throw new Error('Use the separate Prepare, Render or Upscale buttons to queue one stage.');
        }
        if(classes.includes('ComfyLTXLoopSaveCandidate')&&Object.values(output).some(node=>node.class_type==='ComfyLTXLoopMotionEditor'&&node.inputs?.stage==='prepare')) {
            throw new Error('Preparing points cannot start generation. Use Prepare points.');
        }
        return original.apply(this,args);
    };
}
