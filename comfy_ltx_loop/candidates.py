"""Disk-backed render handles and bounded, generation-free finishing."""
import json
import shutil
import subprocess
import uuid
from fractions import Fraction
from pathlib import Path

import numpy as np
from PIL import Image

from .motion import validate_plan, plan_fingerprint, active_point, strict_mask
from .project import atomic_json, sha


def list_candidates(root):
    """Completed original renders, newest first, using portable widget values."""
    root = Path(root)
    records = []
    for path in root.glob('candidate-*/record.json'):
        try:
            record = json.loads(path.read_text(encoding='utf-8'))
            if (not isinstance(record,dict) or record.get('schema') != 'comfy-ltx-loop-render-handle/1'
                    or record.get('kind') != 'candidate'
                    or record.get('state') != 'awaiting_visual_review'
                    or not all((path.parent/name).is_file() for name in ('loop.mp4','seam.mp4'))):
                continue
            records.append((path.stat().st_mtime_ns,path.relative_to(root).as_posix()))
        except (OSError,ValueError):
            continue
    return [name for _,name in sorted(records,reverse=True)]


def output_size(size, short_side):
    scale = short_side/min(size)
    return tuple(max(2, round(value*scale/2)*2) for value in size)


def exact_widescreen_size(size):
    """Return a centered-crop 16:9/9:16 size for a source within 2% tolerance."""
    width,height = size
    short,long = sorted((width,height))
    if abs(long/short/(16/9)-1) > .02:
        return size
    if width >= height:
        scale = min(width//16,height//9)
        return (16*scale,9*scale)
    scale = min(width//9,height//16)
    return (9*scale,16*scale)


def crop_exact_widescreen(image):
    """Center-crop a near-widescreen exported frame without resizing it."""
    width,height = image.size
    target_w,target_h = exact_widescreen_size(image.size)
    x = (width-target_w)//2
    y = (height-target_h)//2
    return image.crop((x,y,x+target_w,y+target_h))


def allocate(root, prefix):
    directory = Path(root)/f'{prefix}-{uuid.uuid4().hex[:12]}'
    directory.mkdir(parents=True, exist_ok=False)
    (directory/'frames').mkdir()
    return directory


def encode(out, count, fps, name='loop.mp4'):
    temporary = out/(name+'.tmp.mp4')
    subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-framerate',str(fps),
                    '-i',str(out/'frames/%06d.png'),'-frames:v',str(count),'-an',
                    '-c:v','libx264','-crf','18','-pix_fmt','yuv420p','-movflags',
                    '+faststart',str(temporary)],check=True)
    info = json.loads(subprocess.run(['ffprobe','-v','error','-count_frames',
                     '-show_streams','-of','json',str(temporary)],check=True,
                     capture_output=True,text=True).stdout)['streams']
    with Image.open(out/'frames/000000.png') as image:
        size = image.size
    if (len(info) != 1 or info[0]['codec_type'] != 'video' or
        int(info[0]['nb_read_frames']) != count or
        Fraction(info[0]['r_frame_rate']) != fps or
        (info[0]['width'], info[0]['height']) != size):
        raise ValueError('Video frame count, FPS, dimensions or silence validation failed')
    temporary.replace(out/name)


def encode_previews(out, count, fps):
    encode(out,count,fps)
    seam = out/'seam-encode'
    (seam/'frames').mkdir(parents=True)
    edge = min(fps//2,count//2)
    indices = list(range(count-edge,count))+list(range(edge))
    for index, source in enumerate(indices):
        shutil.copyfile(out/'frames'/f'{source:06d}.png', seam/'frames'/f'{index:06d}.png')
    encode(seam,len(indices),fps,'seam.mp4')
    (seam/'seam.mp4').replace(out/'seam.mp4')
    # Keep the small seam frame sequence as lossless evidence.


def save_record(out, record):
    record.update(schema='comfy-ltx-loop-render-handle/1', directory=str(out.resolve()),
                  record=str((out/'record.json').resolve()),
                  frame_hashes={p.name:sha(p) for p in sorted((out/'frames').glob('*.png'))})
    atomic_json(out/'record.json',record)
    return record


def protected_reference(plan, source, size):
    """Map the fixed original and approved source mask into saved-frame space."""
    pixels = np.asarray(source)
    if pixels.shape[:2] != tuple(reversed(plan['source_size'])):
        raise ValueError('Source reference dimensions differ from the reviewed source image')
    image = Image.fromarray(pixels[:,:,:3].astype(np.uint8)).resize(
        output_size(plan['source_size'], min(size)), Image.Resampling.LANCZOS)
    mask = Image.fromarray(np.asarray(strict_mask(plan), dtype=np.uint8)).resize(
        image.size, Image.Resampling.NEAREST)
    return crop_exact_widescreen(image), crop_exact_widescreen(mask)


def protect_image(image, reference, mask):
    """Keep zero-mask pixels byte-identical to the fixed source reference."""
    if image.size != reference.size or image.size != mask.size:
        raise ValueError('Protection reference dimensions differ from generated frame')
    return Image.composite(image.convert('RGB'), reference.convert('RGB'), mask)


def protect_finished_frames(out, handle, target):
    source = Path(handle['directory'])/'source-reference.png'
    mask = Path(handle['directory'])/'approved-motion-mask.png'
    if not source.is_file() or not mask.is_file():
        raise ValueError('Strict candidate is missing its source protection artifacts')
    with Image.open(source) as reference, Image.open(mask) as approved:
        reference = crop_exact_widescreen(reference.convert('RGB')).resize(target, Image.Resampling.LANCZOS)
        approved = crop_exact_widescreen(approved.convert('L')).resize(target, Image.Resampling.NEAREST)
        for frame_path in sorted((out/'frames').glob('*.png')):
            with Image.open(frame_path) as frame:
                protect_image(frame, reference, approved).save(frame_path)


def save_candidate(images, plan, seed, root, settings, source=None):
    validate_plan(plan)
    no_review_needed = (plan.get('review',{}).get('state') == 'not_required' and
                        not any(active_point(plan, point) for point in plan['landmarks']))
    if not no_review_needed and plan.get('review',{}).get('fingerprint') != plan_fingerprint(plan):
        raise ValueError('Reviewed plan required before saving a candidate')
    if len(images) != plan['frames']:
        raise ValueError(f"Expected {plan['frames']} generated frames including the endpoint")
    expected_w, expected_h = plan['transform']['canvas']
    if tuple(images.shape[1:3]) != (expected_h,expected_w):
        raise ValueError('Decoded dimensions differ from the reviewed motion canvas')
    out = allocate(root, f'candidate-{seed}')
    (out/'raw').mkdir()
    x,y,w,h = plan['transform']['content']
    size = exact_widescreen_size(output_size(plan['source_size'],min(w,h)))
    reference = mask = None
    if plan.get('render_mode') == 'only_pointed_parts':
        if source is None:
            raise ValueError('Strict Render requires the original source image for protected pixels')
        reference, mask = protected_reference(plan, source, size)
        reference.save(out/'source-reference.png')
        mask.save(out/'approved-motion-mask.png')
    first = last = None
    for index in range(len(images)):
        value = images[index]
        if hasattr(value,'detach'):
            value = value.detach().cpu().numpy()
        value = np.asarray(value)
        if value.dtype != np.uint8:
            if not np.isfinite(value).all():
                raise ValueError('Decoded frame has non-finite pixels')
            value = np.rint(np.clip(value,0,1)*255).astype(np.uint8)
        image = Image.fromarray(value[:,:,:3])
        image.save(out/'raw'/f'{index:06d}.png')
        image = image.crop((x,y,x+w,y+h)).resize(
            output_size(plan['source_size'],min(w,h)),Image.Resampling.LANCZOS)
        image = crop_exact_widescreen(image)
        if reference is not None:
            image = protect_image(image, reference, mask)
        pixels = np.asarray(image,dtype=np.float32)
        if first is None:
            first = pixels
        last = pixels
        if index < len(images)-1:
            image.save(out/'frames'/f'{index:06d}.png')
    closure = float(np.mean(np.abs(last-first))/255)
    record = save_record(out, {'kind':'candidate','dimensions':list(size),
        'fps':plan['fps'],'frame_count':len(images)-1,'generated_frames':len(images),
        'seed':seed,'generation_settings':settings,'motion_plan':plan,
        'closure_mean':closure,'visual_review_required':True,
        'feedback':['Inspect face identity, hair, background drift and the loop seam.',
                    'Returning tracks do not guarantee closure; retry visibly poor seams.'],
        'state':'encoding'})
    encode_previews(out,record['frame_count'],record['fps'])
    record['state'] = 'awaiting_visual_review'
    return save_record(out,record)


def load_handle(path, root):
    root = Path(root).resolve()
    path = Path(path).resolve()
    if not path.is_relative_to(root) or path.name != 'record.json':
        raise ValueError('Select a saved candidate inside the Comfy LTX Loop output directory')
    record = json.loads(path.read_text(encoding='utf-8'))
    if record.get('schema') != 'comfy-ltx-loop-render-handle/1' or record.get('state') != 'awaiting_visual_review':
        raise ValueError('Render record is invalid or unfinished')
    out = path.parent
    expected = [f'{i:06d}.png' for i in range(record['frame_count'])]
    if sorted(record['frame_hashes']) != expected:
        raise ValueError('Saved frame sequence is incomplete')
    for name in expected:
        frame = out/'frames'/name
        if not frame.is_file() or sha(frame) != record['frame_hashes'][name]:
            raise ValueError(f'Saved frame missing or modified: {name}')
        with Image.open(frame) as image:
            if list(image.size) != record['dimensions']:
                raise ValueError('Saved frame dimensions changed')
    # Resolve from the actual selected record, allowing persistent volume relocation.
    record.update(directory=str(out),record=str(path))
    return record


def finish_candidate(handle, root, resolution, chunk_size=4, enhancer=None, method='original_ai'):
    resolutions = {'1080p':1080, '1440p':1440, '4K':2160}
    if resolution not in resolutions or not 1 <= chunk_size <= 32:
        raise ValueError('Choose 1080p, 1440p or 4K and a chunk size from 1 to 32')
    if method not in ('fast','balanced_ai','original_ai'):
        raise ValueError('Choose a valid finish method')
    handle = load_handle(Path(handle['record']),root)
    if handle['kind'] != 'candidate':
        raise ValueError('Select an original animation candidate to upscale')
    target = exact_widescreen_size(output_size(handle['dimensions'],resolutions[resolution]))
    out = allocate(root,f"finish-{Path(handle['directory']).name}-{resolution}")
    if method == 'fast':
        source = Path(handle['directory'])/'frames'
        crop_w,crop_h = exact_widescreen_size(handle['dimensions'])
        width,height = handle['dimensions']
        crop = (f'crop={crop_w}:{crop_h}:{(width-crop_w)//2}:{(height-crop_h)//2},'
                if (crop_w,crop_h) != (width,height) else '')
        subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y',
                        '-framerate',str(handle['fps']),'-start_number','0',
                        '-i',str(source/'%06d.png'),'-vf',
                        f'{crop}scale={target[0]}:{target[1]}:flags=lanczos',
                        '-frames:v',str(handle['frame_count']),'-fps_mode','passthrough',
                        '-start_number','0','-pix_fmt','rgb24',
                        str(out/'frames/%06d.png')],check=True)
        for index in range(handle['frame_count']):
            frame = out/'frames'/f'{index:06d}.png'
            if not frame.is_file():
                raise ValueError(f'Fast finish omitted frame {index}')
            with Image.open(frame) as image:
                if image.size != target:
                    raise ValueError('Fast finish returned unexpected dimensions')
    else:
        enhancer = enhancer or (anime_enhancer(precision='fp16') if method == 'balanced_ai'
                                else anime_enhancer())
        try:
            for start in range(0,handle['frame_count'],chunk_size):
                # At most one input/output image lives in memory; chunk boundaries allow
                # cancellation/progress and never materialize the complete tensor batch.
                for index in range(start,min(start+chunk_size,handle['frame_count'])):
                    with Image.open(Path(handle['directory'])/'frames'/f'{index:06d}.png') as image:
                        result = enhancer(crop_exact_widescreen(image.convert('RGB')),target)
                        if result.size != target:
                            raise ValueError('Upscaler returned unexpected dimensions')
                        result.save(out/'frames'/f'{index:06d}.png')
                try:
                    from comfy.model_management import throw_exception_if_processing_interrupted
                    throw_exception_if_processing_interrupted()
                except ImportError:
                    pass
        finally:
            close = getattr(enhancer,'close',None)
            if close:
                close()
    if handle.get('motion_plan', {}).get('render_mode') == 'only_pointed_parts':
        protect_finished_frames(out, handle, target)
    record = save_record(out, {'kind':'finish','parent':handle['record'],
        'dimensions':list(target),'fps':handle['fps'],'frame_count':handle['frame_count'],
        'seed':handle['seed'],'generation_settings':handle['generation_settings'],
        'finish_method':method,
        'upscale_model':None if method == 'fast' else 'realesr-animevideov3',
        'upscale_model_sha256':getattr(enhancer,'model_sha256',None) if method != 'fast' else None,
        'state':'encoding',
        'visual_review_required':True,'feedback':['Inspect upscale flicker before downloading.']})
    encode_previews(out,record['frame_count'],record['fps'])
    record['state'] = 'awaiting_visual_review'
    return save_record(out,record)


def tiled_anime_scale(tensor, model, precision, utils, management, torch, tile_state=None):
    initial_tile = 512 if precision == 'fp16' else 256
    tile = tile_state.get('size',initial_tile) if tile_state is not None else initial_tile
    while True:
        try:
            return utils.tiled_scale(tensor,lambda chunk:model(chunk if precision == 'fp16' else chunk.float()),
                tile_x=tile,tile_y=tile,overlap=32,upscale_amount=4,
                output_device=torch.device('cpu'))
        except Exception as error:
            management.raise_non_oom(error)
            tile //= 2
            if tile < 128:
                raise
            if tile_state is not None:
                tile_state['size'] = tile


def anime_enhancer(precision='fp32'):
    import folder_paths
    import torch
    import comfy.model_management as management
    import comfy.utils as utils
    from spandrel import ModelLoader, ImageModelDescriptor
    management.unload_all_models()
    path = Path(folder_paths.models_dir)/'upscale_models/realesr-animevideov3.pth'
    if not path.is_file():
        raise ValueError(f'Install realesr-animevideov3 weights at {path}')
    weights = utils.load_torch_file(str(path),safe_load=True)
    weights = weights.get('params_ema',weights.get('params',weights))
    model = ModelLoader().load_from_state_dict(weights).eval()
    if not isinstance(model,ImageModelDescriptor) or model.scale != 4:
        raise ValueError('Expected the x4 realesr-animevideov3 image model')
    if precision == 'fp16':
        if not getattr(model,'supports_half',False):
            raise ValueError('Installed realesr-animevideov3 model does not support FP16; choose Original AI or Fast')
        model.half()
    device = management.get_torch_device()
    model.to(device)
    class Enhancer:
        model_sha256 = sha(path)
        def __init__(self):
            self.tile_state = {}
        @torch.inference_mode()
        def __call__(self,image,size):
            # Spandrel consumes RGB. Tiled inference emits one frame on CPU.
            tensor = torch.from_numpy(np.asarray(image).copy()).float().div_(255).movedim(-1,0).unsqueeze(0).to(device)
            if precision == 'fp16':
                tensor = tensor.half()
            result = tiled_anime_scale(tensor,model,precision,utils,management,torch,self.tile_state)
            pixels = result[0].movedim(0,-1).clamp_(0,1).mul_(255).round().byte().numpy()
            return Image.fromarray(pixels).resize(size,Image.Resampling.LANCZOS)
        def close(self):
            model.to('cpu')
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
    return Enhancer()
