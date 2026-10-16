"""ComfyUI stage nodes; optional GPU imports are deferred to their own stages."""
import base64
import hashlib
import json
from io import BytesIO
from pathlib import Path

import numpy as np
from PIL import Image

from .motion import new_plan, require_review, canvas_tracks, validate_plan, active_point
from .vision import analyze
from .candidates import save_candidate, load_handle, finish_candidate, list_candidates


def output_root():
    import folder_paths
    return Path(folder_paths.get_output_directory())/'comfy-ltx-loop'


def image_array(image):
    if len(image) != 1:
        raise ValueError('Load exactly one source image')
    value = image[0]
    if hasattr(value,'detach'):
        value = value.detach().cpu().numpy()
    if not np.isfinite(value).all():
        raise ValueError('Source image contains invalid pixels')
    return np.rint(np.clip(value[:,:,:3],0,1)*255).astype(np.uint8)


def canvas_image(image, transform):
    import torch
    x,y,w,h = transform['content']
    image = image.resize((w,h),Image.Resampling.LANCZOS)
    # Edge padding does not stretch the original image or alter track mapping.
    cw,ch = transform['canvas']
    pixels = np.pad(np.asarray(image),((y,ch-h-y),(x,cw-w-x),(0,0)),mode='edge')
    return torch.from_numpy(pixels.astype(np.float32)/255).unsqueeze(0)


def preview_ui(record):
    directory = Path(record['directory']).relative_to(output_root()).as_posix()
    return {'render_handle':[record], 'preview_paths':[
        f'comfy-ltx-loop/{directory}/loop.mp4',f'comfy-ltx-loop/{directory}/seam.mp4']}


class ComfyLTXLoopMotionEditor:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required':{
            'image':('IMAGE',),
            'motion_prompt':('STRING',{'default':'Gentle hair sway. Stationary camera.','multiline':True}),
            'requested_parts':('STRING',{'default':'auto'}),
            'duration':('FLOAT',{'default':6.,'min':1.,'max':30.,'step':1/24}),
            'fps':('INT',{'default':24,'min':8,'max':60}),
            'strength':('FLOAT',{'default':.01,'min':0.,'max':.1,'step':.001}),
            'short_side':('INT',{'default':720,'min':256,'max':2160,'step':8}),
            'seed':('INT',{'default':42,'min':0,'max':2**63-1,'control_after_generate':False}),
            'vision_model':('STRING',{'default':'models/Qwen3.5-9B'}),
            'preparation':(['local Qwen','manual','local Qwen3.5'],{'default':'local Qwen3.5'}),
            'plan_json':('STRING',{'default':'{}','multiline':True}),
            'stage':(['render','prepare'],)},
            'optional':{
                'animate_background':('BOOLEAN',{'default':False}),
                'background_prompt':('STRING',{'default':'','multiline':True,
                    'placeholder':'Example: Gently sway the visible leaves; keep the tree trunk still.'}),
                'background_preparation':(['model','manual'],{'default':'model'}),
                'prepare_target':(['character','background','both'],{'default':'character'}),
                'use_character_points':('BOOLEAN',{'default':True}),
                'use_background_points':('BOOLEAN',{'default':True})},
            'hidden':{'extra_pnginfo':'EXTRA_PNGINFO','unique_id':'UNIQUE_ID'}}

    RETURN_TYPES = ('IMAGE','STRING','MOTION_PLAN','FLOAT','FLOAT','INT','STRING')
    RETURN_NAMES = ('canvas','tracks','motion_plan','fps','duration','seed','prompt')
    FUNCTION = 'execute'
    CATEGORY = 'comfy-ltx-loop/staged'
    OUTPUT_NODE = True

    @classmethod
    def IS_CHANGED(cls,**kwargs):
        return float('nan')

    def execute(self,image,motion_prompt,requested_parts,duration,fps,strength,short_side,
                seed,vision_model,preparation,plan_json,stage,extra_pnginfo=None,unique_id=None,
                animate_background=False,background_prompt='',background_preparation='model',
                prepare_target='character',use_character_points=True,use_background_points=True):
        pixels = image_array(image)
        source = Image.fromarray(pixels)
        identity = hashlib.sha256(pixels.tobytes()+str(source.size).encode()).hexdigest()
        requested = [v.strip() for v in requested_parts.split(',') if v.strip()]
        analysis = {'preparation':preparation, 'model_path':vision_model}
        # `animate_background` remains an optional legacy slot so old workflows
        # deserialize in the same order. Text is now the sole animation switch.
        background = {'enabled':bool(background_prompt.strip()),'prompt':background_prompt,
                      'preparation':background_preparation,'model_path':vision_model}
        if stage == 'prepare':
            if prepare_target not in ('character','background','both'):
                raise ValueError('Choose character, background, or combined preparation')
            if prepare_target in ('background','both') and not background_prompt.strip():
                raise ValueError('Enter background motion before preparing background points')
            try:
                old = validate_plan(json.loads(plan_json))
                if old['source_id'] != identity:
                    old = None
            except (ValueError, KeyError, TypeError, json.JSONDecodeError):
                old = None
            targets = ('character','background') if prepare_target == 'both' else (prepare_target,)
            for target in targets:
                points,feedback = [],[]
                failed = False
                mode = preparation if target == 'character' else background_preparation
                current_prompt = motion_prompt if target == 'character' else background_prompt
                if mode in ('local Qwen','local Qwen3.5','model'):
                    try:
                        if target == 'background':
                            points = analyze(source,current_prompt,['auto'],vision_model,feedback=feedback,target='background')
                        else:
                            points = analyze(source,current_prompt,requested,vision_model,feedback=feedback)
                    except Exception as error:
                        failed = True
                        feedback.append(f'{target.capitalize()} automatic preparation failed: {error}. Add/edit points manually or retry.')
                plan = new_plan(identity,source.size,motion_prompt,requested,[],
                                duration,fps,strength,short_side,feedback,analysis=analysis)
                if old:
                    plan['landmarks'] = [p for p in old['landmarks'] if p.get('group','character') != target]
                    if target == 'background':
                        plan['analysis'] = old.get('analysis', analysis)
                        background.update({k:v for k,v in old.get('background', {}).items() if k.startswith('prepared_')})
                    else:
                        background = old.get('background', background) | background
                if target == 'character':
                    if failed and old:
                        plan['analysis'] = old.get('analysis', analysis)
                    elif not failed:
                        plan['analysis'] = {**analysis,'prepared_prompt':motion_prompt,
                            'prepared_requested':requested,'prepared_preparation':preparation,
                            'prepared_model_path':vision_model}
                elif not failed:
                    background.update(prepared_prompt=background_prompt,
                                      prepared_preparation=background_preparation,
                                      prepared_model_path=vision_model)
                if old and (mode == 'manual' or failed or not points):
                    plan['landmarks'].extend(p for p in old['landmarks'] if p.get('group','character') == target)
                else:
                    for point in new_plan(identity,source.size,motion_prompt,requested,points,
                            duration,fps,strength,short_side)['landmarks']:
                        if target == 'background': point['group'] = 'background'
                        plan['landmarks'].append(point)
                plan['background'] = background
                plan['use_character_points'] = use_character_points
                plan['use_background_points'] = use_background_points
                old = plan
            validate_plan(plan)
        elif stage == 'render':
            try:
                plan = json.loads(plan_json)
            except json.JSONDecodeError as error:
                raise ValueError('Invalid saved plan; Prepare and review points') from error
            if plan == {}:
                plan = new_plan(identity,source.size,motion_prompt,requested,[],
                                duration,fps,strength,short_side,analysis=analysis)
                plan['background'] = background
            else:
                validate_plan(plan)
            if (plan.get('use_character_points',True) != use_character_points or
                    plan.get('use_background_points',True) != use_background_points):
                plan['review'] = {'state':'pending'}
            plan['use_character_points'] = use_character_points
            plan['use_background_points'] = use_background_points
            effective = {**plan, 'background':background}
            if not any(active_point(effective,point) for point in plan['landmarks']):
                preserved = plan['landmarks'] if plan['source_id'] == identity else []
                fresh = new_plan(identity,source.size,motion_prompt,requested,[],
                                 duration,fps,strength,short_side,analysis=analysis)
                fresh['landmarks'] = preserved
                if preserved:
                    fresh['analysis'] = {**plan.get('analysis', {}), **analysis}
                    fresh['background'] = {**plan.get('background', {}), **background}
                else:
                    fresh['background'] = background
                fresh['use_character_points'] = use_character_points
                fresh['use_background_points'] = use_background_points
                fresh['review'] = {'state':'not_required'}
                plan = validate_plan(fresh)
            else:
                require_review(plan,identity,source.size,motion_prompt,duration,fps,strength,short_side,
                               requested=requested,analysis=analysis,background=background)
                plan['requested'] = requested
                if 'prepared_prompt' not in plan.get('analysis', {}):
                    plan['analysis'] = analysis
        else:
            raise ValueError('Choose Prepare or Render')
        canvas = canvas_image(source,plan['transform'])
        buffer = BytesIO()
        source.save(buffer,format='PNG')
        ui = {'motion_plan':[plan], 'bg_image':[base64.b64encode(buffer.getvalue()).decode()]}
        if extra_pnginfo is not None:
            workflow = extra_pnginfo.setdefault('workflow',{})
            workflow.setdefault('extra',{}).setdefault('comfy_ltx_loop_motion_plans',{})[str(unique_id)] = plan
        render_prompt = motion_prompt
        if plan.get('background', {}).get('enabled'):
            render_prompt += ('\nBackground motion: '+background_prompt.strip()+
                              '\nStationary camera. Keep unrequested areas still.')
        else:
            render_prompt += '\nStationary camera and stationary background.'
        return {'ui':ui,'result':(canvas,json.dumps(canvas_tracks(plan)),plan,
                                 float(fps),float(duration),seed,render_prompt)}


class ComfyLTXLoopSaveCandidate:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required':{'video':('VIDEO',),'motion_plan':('MOTION_PLAN',),
                            'seed':('INT',{'default':42})},
                'hidden':{'prompt':'PROMPT','extra_pnginfo':'EXTRA_PNGINFO'}}
    RETURN_TYPES = ('RENDER_HANDLE',)
    RETURN_NAMES = ('candidate',)
    FUNCTION = 'execute'
    CATEGORY = 'comfy-ltx-loop/staged'
    OUTPUT_NODE = True
    @classmethod
    def IS_CHANGED(cls,**kwargs):
        return float('nan')
    def execute(self,video,motion_plan,seed,prompt=None,extra_pnginfo=None):
        components = video.get_components()
        if float(components.frame_rate) != motion_plan['fps']:
            raise ValueError('Decoded FPS differs from the reviewed plan')
        settings = {'recipe':'LTX-2.5-single-stage-motion-track',
                    'api_graph':prompt,'workflow':(extra_pnginfo or {}).get('workflow')}
        record = save_candidate(components.images,motion_plan,seed,output_root(),settings)
        return {'ui':preview_ui(record),'result':(record,)}


class ComfyLTXLoopSavedCandidate:
    @classmethod
    def INPUT_TYPES(cls):
        records = list_candidates(output_root())
        return {'required':{'candidate':(records or ['Select a saved candidate'],)}}
    RETURN_TYPES = ('RENDER_HANDLE',)
    FUNCTION = 'execute'
    CATEGORY = 'comfy-ltx-loop/staged'
    @classmethod
    def IS_CHANGED(cls,**kwargs):
        return float('nan')
    def execute(self,candidate):
        return (load_handle(output_root()/candidate,output_root()),)


class ComfyLTXLoopUpscale:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required':{'candidate':('RENDER_HANDLE',),
                 'resolution':(['1440p','1080p','4K'],{'default':'1440p'}),
                 'chunk_size':('INT',{'default':4,'min':1,'max':32})}}
    RETURN_TYPES = ('RENDER_HANDLE',)
    FUNCTION = 'execute'
    CATEGORY = 'comfy-ltx-loop/staged'
    OUTPUT_NODE = True
    @classmethod
    def IS_CHANGED(cls,**kwargs):
        return float('nan')
    def execute(self,candidate,resolution,chunk_size):
        record = finish_candidate(candidate,output_root(),resolution,chunk_size)
        return {'ui':preview_ui(record),'result':(record,)}


class ComfyLTXLoopFinish:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required':{'candidate':('RENDER_HANDLE',),
                 'resolution':(['1080p','1440p','4K'],{'default':'1080p'}),
                 'method':(['Fast','Balanced AI','Original AI'],{'default':'Fast'}),
                 'chunk_size':('INT',{'default':4,'min':1,'max':32})}}
    RETURN_TYPES = ('RENDER_HANDLE',)
    FUNCTION = 'execute'
    CATEGORY = 'comfy-ltx-loop/staged'
    OUTPUT_NODE = True
    @classmethod
    def IS_CHANGED(cls,**kwargs):
        return float('nan')
    def execute(self,candidate,resolution,method,chunk_size):
        methods = {'Fast':'fast','Balanced AI':'balanced_ai','Original AI':'original_ai'}
        if method not in methods:
            raise ValueError('Choose Fast, Balanced AI or Original AI')
        record = finish_candidate(candidate,output_root(),resolution,chunk_size,method=methods[method])
        return {'ui':preview_ui(record),'result':(record,)}


NODE_CLASS_MAPPINGS = {'ComfyLTXLoopMotionEditor':ComfyLTXLoopMotionEditor,
                       'ComfyLTXLoopSaveCandidate':ComfyLTXLoopSaveCandidate,
                       'ComfyLTXLoopSavedCandidate':ComfyLTXLoopSavedCandidate,
                       'ComfyLTXLoopUpscale':ComfyLTXLoopUpscale,
                       'ComfyLTXLoopFinish':ComfyLTXLoopFinish}
NODE_DISPLAY_NAME_MAPPINGS = {'ComfyLTXLoopMotionEditor':'Comfy LTX Loop · Prepare and review',
    'ComfyLTXLoopSaveCandidate':'Comfy LTX Loop · Render preview',
    'ComfyLTXLoopSavedCandidate':'Comfy LTX Loop · Select saved candidate',
    'ComfyLTXLoopUpscale':'Comfy LTX Loop · Upscale preview',
    'ComfyLTXLoopFinish':'Comfy LTX Loop · Finish preview'}
