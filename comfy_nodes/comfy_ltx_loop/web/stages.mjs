export function stageGraph(output, target, stage) {
    const graph = structuredClone(output);
    const targets = {prepare:'ComfyLTXLoopMotionEditor', areas:'ComfyLTXLoopMotionEditor', render:'ComfyLTXLoopSaveCandidate', upscale:'ComfyLTXLoopUpscale'};
    if (!targets[stage]) throw new Error(`Unknown stage ${stage}`);
    const targetClass=graph[String(target)]?.class_type;
    if (targetClass !== targets[stage] && !(stage === 'upscale' && targetClass === 'ComfyLTXLoopFinish')) {
        throw new Error(`${stage} target ${target} must be ${targets[stage]} or ComfyLTXLoopFinish`);
    }
    const keep = new Set();
    function visit(id) {
        id = String(id);
        if (keep.has(id)) return;
        if (!graph[id]) throw new Error(`Missing workflow node ${id}`);
        keep.add(id);
        for (const value of Object.values(graph[id].inputs ?? {})) {
            if (Array.isArray(value) && value.length === 2 && (typeof value[0] === 'string' || typeof value[0] === 'number') && Number.isInteger(Number(value[1]))) visit(value[0]);
        }
    }
    visit(target);
    for (const id of Object.keys(graph)) if (!keep.has(id)) delete graph[id];
    const classes = new Set(Object.values(graph).map(n => n.class_type));
    if ((stage === 'prepare' || stage === 'areas') && [...classes].some(c => !['ComfyLTXLoopMotionEditor', 'LoadImage'].includes(c))) {
        throw new Error('Preparation must connect directly to Load Image; model nodes cannot be upstream.');
    }
    if (stage !== 'upscale' && (classes.has('ComfyLTXLoopUpscale') || classes.has('ComfyLTXLoopFinish'))) throw new Error('Upscale cannot run in this stage.');
    if (stage === 'upscale' && [...classes].some(c => !['ComfyLTXLoopUpscale','ComfyLTXLoopFinish','ComfyLTXLoopSavedCandidate'].includes(c))) {
        throw new Error('Upscale must use a saved candidate, without generation nodes upstream.');
    }
    if (stage === 'upscale') {
        const link=graph[String(target)].inputs?.candidate;
        if (!Array.isArray(link) || graph[String(link[0])]?.class_type !== 'ComfyLTXLoopSavedCandidate' || keep.size !== 2) {
            throw new Error('Upscale must use one saved candidate directly, without another finishing node.');
        }
    }
    for (const node of Object.values(graph)) {
        if (node.class_type === 'ComfyLTXLoopMotionEditor') node.inputs.stage = (stage === 'prepare' || stage === 'areas') ? stage : 'render';
    }
    return graph;
}
