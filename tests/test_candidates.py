import tempfile
import unittest
import shutil
import sys
import json
import subprocess
from types import ModuleType, SimpleNamespace
from pathlib import Path
from unittest.mock import patch

import numpy as np
from PIL import Image

from comfy_ltx_loop.candidates import save_candidate, save_record, load_handle, finish_candidate, anime_enhancer, tiled_anime_scale
from comfy_ltx_loop.motion import new_plan, review_plan


class CandidateTests(unittest.TestCase):
    def test_strict_candidate_restores_protected_source_pixels_exactly(self):
        with tempfile.TemporaryDirectory() as tmp, patch('comfy_ltx_loop.candidates.encode_previews'):
            plan = new_plan('abc', (32,32), 'hair', ['tip'], [
                {'label':'tip','x':.5,'y':.5,'motion_role':'move','body_part':'hair','reason':'sway'}],
                duration=1, fps=8, short_side=256)
            plan['render_mode'] = 'only_pointed_parts'
            point = plan['landmarks'][0]['id']
            mask = [[255 if 12 <= x < 20 and 12 <= y < 20 else 0 for x in range(32)] for y in range(32)]
            plan['motion_areas'] = [{'point_id':point,'mask':mask}]
            plan = review_plan(plan)
            generated = np.full((9,256,256,3), [0,255,0], dtype=np.uint8)
            source = np.full((32,32,3), [255,0,0], dtype=np.uint8)
            handle = save_candidate(generated, plan, 42, Path(tmp), {}, source=source)
            with Image.open(Path(handle['directory'])/'frames/000000.png') as frame:
                pixels = np.asarray(frame)
            self.assertEqual(pixels[0,0].tolist(), [255,0,0])
            self.assertEqual(pixels[128,128].tolist(), [0,255,0])
    def test_no_point_render_plan_is_saved_with_review_not_required(self):
        with tempfile.TemporaryDirectory() as tmp, patch('comfy_ltx_loop.candidates.encode_previews'):
            plan = new_plan('abc',(64,64),'Hair sway',['auto'],[],1,8,.01,256)
            plan['review'] = {'state':'not_required'}
            frames = np.zeros((9,256,256,3),dtype=np.uint8)
            record = save_candidate(frames,plan,42,Path(tmp),{'recipe':'motion-track'})
            saved = json.loads(Path(record['record']).read_text())
            self.assertEqual(saved['motion_plan']['review']['state'],'not_required')
            self.assertEqual(saved['frame_count'],8)
            active = new_plan('abc',(64,64),'Hair sway',['auto'],
                              [{'label':'tip','x':.5,'y':.5}],1,8,.01,256)
            active['review'] = {'state':'not_required'}
            with self.assertRaisesRegex(ValueError,'Reviewed plan required'):
                save_candidate(frames,active,43,Path(tmp),{'recipe':'motion-track'})

    def test_fast_finish_uses_saved_frames_and_records_method(self):
        if not shutil.which('ffmpeg') or not shutil.which('ffprobe'):
            self.skipTest('ffmpeg/ffprobe unavailable')
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root/'candidate-fast'
            (source/'frames').mkdir(parents=True)
            (source/'raw').mkdir()
            for index in range(2):
                Image.new('RGB',(1280,720),(index*80,20,40)).save(source/'frames'/f'{index:06d}.png')
            original = save_record(source,{'kind':'candidate','dimensions':[1280,720],
                'fps':8,'frame_count':2,'seed':42,'generation_settings':{},
                'state':'awaiting_visual_review'})
            before = {p.name:p.read_bytes() for p in (source/'frames').glob('*.png')}
            record_bytes = Path(original['record']).read_bytes()
            with patch('comfy_ltx_loop.candidates.anime_enhancer',side_effect=AssertionError('AI loaded')):
                finish = finish_candidate(original,root,'1080p',method='fast')
            self.assertEqual(finish['finish_method'],'fast')
            self.assertEqual(finish['dimensions'],[1920,1080])
            self.assertEqual((finish['fps'],finish['frame_count']),(8,2))
            self.assertIsNone(finish['upscale_model'])
            self.assertNotEqual(finish['record'],original['record'])
            for index in range(2):
                with Image.open(Path(finish['directory'])/'frames'/f'{index:06d}.png') as image:
                    self.assertEqual(image.size,(1920,1080))
                    self.assertEqual(image.getpixel((960,540)),(index*80,20,40))
            streams = json.loads(subprocess.run(['ffprobe','-v','error','-count_frames',
                '-show_streams','-of','json',str(Path(finish['directory'])/'loop.mp4')],
                check=True,capture_output=True,text=True).stdout)['streams']
            self.assertEqual(len(streams),1)
            self.assertEqual(streams[0]['codec_type'],'video')
            self.assertEqual((streams[0]['width'],streams[0]['height']),(1920,1080))
            self.assertEqual((streams[0]['nb_read_frames'],streams[0]['r_frame_rate']),('2','8/1'))
            self.assertEqual({p.name:p.read_bytes() for p in (source/'frames').glob('*.png')},before)
            self.assertEqual(Path(original['record']).read_bytes(),record_bytes)

    def test_balanced_and_original_choose_distinct_model_policies(self):
        with tempfile.TemporaryDirectory() as tmp, patch('comfy_ltx_loop.candidates.encode_previews'):
            root = Path(tmp)
            source = root/'candidate-ai'
            (source/'frames').mkdir(parents=True)
            Image.new('RGB',(16,16)).save(source/'frames/000000.png')
            original = save_record(source,{'kind':'candidate','dimensions':[16,16],
                'fps':8,'frame_count':1,'seed':42,'generation_settings':{},
                'state':'awaiting_visual_review'})
            def enhancer(image,size):
                return image.resize(size)
            enhancer.model_sha256 = 'weights'
            with patch('comfy_ltx_loop.candidates.anime_enhancer',side_effect=[enhancer,enhancer]) as load:
                balanced = finish_candidate(original,root,'1080p',method='balanced_ai')
                original_ai = finish_candidate(original,root,'1080p',method='original_ai')
            self.assertEqual(load.call_args_list[0].kwargs,{'precision':'fp16'})
            self.assertEqual(load.call_args_list[1].kwargs,{})
            self.assertEqual((balanced['finish_method'],original_ai['finish_method']),
                             ('balanced_ai','original_ai'))
            self.assertEqual(balanced['upscale_model_sha256'],'weights')
            self.assertNotEqual(balanced['record'],original_ai['record'])

    def test_invalid_finish_method_rejected_before_allocating(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError,'method'):
                finish_candidate({'record':'unused'},Path(tmp),'1080p',method='unknown')
            self.assertEqual(list(Path(tmp).iterdir()),[])

    def test_balanced_tiles_fall_back_only_on_oom(self):
        attempts = []
        def scale(tensor, run, **kwargs):
            attempts.append(kwargs['tile_x'])
            if len(attempts) < 3:
                raise RuntimeError('CUDA out of memory')
            return 'scaled'
        def oom_only(error):
            if 'out of memory' not in str(error):
                raise error
        tile_state = {}
        result = tiled_anime_scale('input',lambda chunk:chunk,'fp16',
            SimpleNamespace(tiled_scale=scale),SimpleNamespace(raise_non_oom=oom_only),
            SimpleNamespace(device=lambda value:value),tile_state)
        self.assertEqual(result,'scaled')
        self.assertEqual(attempts,[512,256,128])
        self.assertEqual(tile_state['size'],128)
        tiled_anime_scale('input',lambda chunk:chunk,'fp16',
            SimpleNamespace(tiled_scale=scale),SimpleNamespace(raise_non_oom=oom_only),
            SimpleNamespace(device=lambda value:value),tile_state)
        self.assertEqual(attempts,[512,256,128,128])
        attempts.clear()
        with self.assertRaisesRegex(RuntimeError,'kernel failed'):
            tiled_anime_scale('input',lambda chunk:chunk,'fp16',
                SimpleNamespace(tiled_scale=lambda *a,**kw: (_ for _ in ()).throw(RuntimeError('kernel failed'))),
                SimpleNamespace(raise_non_oom=oom_only),SimpleNamespace(device=lambda value:value))

    def test_balanced_rejects_weights_without_half_support(self):
        with tempfile.TemporaryDirectory() as tmp:
            weights = Path(tmp)/'upscale_models/realesr-animevideov3.pth'
            weights.parent.mkdir()
            weights.write_bytes(b'weights')
            class Descriptor:
                scale = 4
                supports_half = False
                def eval(self): return self
            fake_model = Descriptor()
            folder_paths = ModuleType('folder_paths')
            folder_paths.models_dir = tmp
            torch = ModuleType('torch')
            torch.inference_mode = lambda: lambda func: func
            comfy = ModuleType('comfy')
            comfy.__path__ = []
            management = ModuleType('comfy.model_management')
            management.unload_all_models = lambda: None
            utils = ModuleType('comfy.utils')
            utils.load_torch_file = lambda *a,**kw: {}
            comfy.model_management = management
            comfy.utils = utils
            spandrel = ModuleType('spandrel')
            spandrel.ImageModelDescriptor = Descriptor
            spandrel.ModelLoader = lambda: SimpleNamespace(load_from_state_dict=lambda data:fake_model)
            with patch.dict(sys.modules,{'folder_paths':folder_paths,'torch':torch,'comfy':comfy,
                                         'comfy.model_management':management,'comfy.utils':utils,
                                         'spandrel':spandrel}):
                with self.assertRaisesRegex(ValueError,'does not support FP16'):
                    anime_enhancer(precision='fp16')
                del Descriptor.supports_half
                with self.assertRaisesRegex(ValueError,'does not support FP16'):
                    anime_enhancer(precision='fp16')

    def test_near_widescreen_export_center_crops_pixels_and_record(self):
        with tempfile.TemporaryDirectory() as tmp, patch('comfy_ltx_loop.candidates.encode_previews'):
            plan = review_plan(new_plan('abc', (1290,720), 'hair', ['tip'],
                               [{'label':'tip','x':.5,'y':.5}], duration=1, fps=8, short_side=720))
            canvas_w,canvas_h = plan['transform']['canvas']
            images = np.zeros((9,canvas_h,canvas_w,3),dtype=np.uint8)
            content_x,content_y,content_w,content_h = plan['transform']['content']
            images[:,content_y:content_y+content_h,content_x:content_x+content_w,0] = np.arange(content_w,dtype=np.uint16).astype(np.uint8)
            handle = save_candidate(images,plan,42,Path(tmp),{})
            with Image.open(Path(handle['directory'])/'frames/000000.png') as frame:
                frame_size = frame.size
                first_pixel = frame.getpixel((0,0))[0]
                last_pixel = frame.getpixel((1279,0))[0]
            with Image.open(Path(handle['directory'])/'raw/000000.png') as raw:
                raw_size = raw.size
            self.assertEqual(frame_size,(1280,720))
            self.assertEqual(handle['dimensions'],[1280,720])
            self.assertEqual(raw_size,(canvas_w,canvas_h))
            self.assertEqual(first_pixel,5)
            self.assertEqual(last_pixel,4)

    def test_legacy_near_widescreen_candidate_finishes_exactly_without_modifying_source(self):
        with tempfile.TemporaryDirectory() as tmp, patch('comfy_ltx_loop.candidates.encode_previews'):
            root = Path(tmp)
            legacy = root/'candidate-legacy'
            (legacy/'frames').mkdir(parents=True)
            (legacy/'raw').mkdir()
            pixels = np.zeros((720,1290,3),dtype=np.uint8)
            pixels[...,0] = np.arange(1290,dtype=np.uint16).astype(np.uint8)
            for index in range(8):
                Image.fromarray(pixels).save(legacy/'frames'/f'{index:06d}.png')
            Image.fromarray(pixels).save(legacy/'raw'/'000000.png')
            original = save_record(legacy,{'kind':'candidate','dimensions':[1290,720],
                'fps':8,'frame_count':8,'generated_frames':9,'seed':42,
                'generation_settings':{},'state':'awaiting_visual_review'})
            record_bytes = Path(original['record']).read_bytes()
            frame_bytes = (Path(original['directory'])/'frames/000000.png').read_bytes()
            raw_bytes = (Path(original['directory'])/'raw/000000.png').read_bytes()
            calls = []
            def enhance(image, target):
                calls.append((image.size,image.getpixel((0,0))[0],target))
                return image.resize(target)
            for resolution, expected in [('1080p',(1920,1080)),('1440p',(2560,1440)),('4K',(3840,2160))]:
                final = finish_candidate(original,root,resolution,32,enhance)
                self.assertEqual(final['dimensions'],list(expected))
                with Image.open(Path(final['directory'])/'frames/000000.png') as frame:
                    self.assertEqual(frame.size,expected)
            self.assertEqual(calls, [((1280,720),5,(1920,1080))]*8 +
                                    [((1280,720),5,(2560,1440))]*8 +
                                    [((1280,720),5,(3840,2160))]*8)
            self.assertEqual(Path(original['record']).read_bytes(),record_bytes)
            self.assertEqual((Path(original['directory'])/'frames/000000.png').read_bytes(),frame_bytes)
            self.assertEqual((Path(original['directory'])/'raw/000000.png').read_bytes(),raw_bytes)

    def test_exact_widescreen_portrait_and_outside_tolerance_size_rules(self):
        cases = [((1600,900),(1600,900)),((720,1290),(720,1280)),
                 ((1307,720),(1308,720))]
        with tempfile.TemporaryDirectory() as tmp, patch('comfy_ltx_loop.candidates.encode_previews'):
            for source, expected in cases:
                with self.subTest(source=source):
                    plan = review_plan(new_plan('abc',source,'hair',['tip'],
                                       [{'label':'tip','x':.5,'y':.5}],duration=1,fps=8,short_side=min(source)))
                    width,height = plan['transform']['canvas']
                    handle = save_candidate(np.zeros((9,height,width,3),dtype=np.uint8),plan,42,Path(tmp),{})
                    self.assertEqual(handle['dimensions'],list(expected))
    def test_all_resolutions_preserve_orientation_frames_timing_and_original(self):
        from comfy_ltx_loop.staged_comfy import ComfyLTXLoopUpscale
        options = ComfyLTXLoopUpscale.INPUT_TYPES()['required']['resolution']
        self.assertIn('1080p', options[0])
        self.assertEqual(options[1]['default'], '1440p')
        for source, expected in [((1600,900),[(1920,1080),(2560,1440),(3840,2160)]),
                                 ((900,1600),[(1080,1920),(1440,2560),(2160,3840)])]:
            with tempfile.TemporaryDirectory() as tmp, patch('comfy_ltx_loop.candidates.encode_previews'):
                root = Path(tmp)
                plan = review_plan(new_plan('abc',source,'hair',['tip'],
                    [dict(label='tip',x=.5,y=.5)],duration=1,fps=8,short_side=288))
                w,h = plan['transform']['canvas']
                original = save_candidate(np.zeros((9,h,w,3),dtype=np.uint8),plan,42,root,{'cfg':1})
                original_record = Path(original['record']).read_bytes()
                for resolution, size in zip(['1080p','1440p','4K'],expected):
                    calls = []
                    def enhance(image, target):
                        calls.append(target)
                        return Image.new('RGB', target)
                    final = finish_candidate(original,root,resolution,3,enhance)
                    self.assertEqual(final['dimensions'],list(size))
                    self.assertEqual(calls, [size]*8)
                    self.assertEqual(final['fps'],8)
                    self.assertEqual(final['frame_count'],8)
                    self.assertEqual(final['parent'],original['record'])
                    self.assertEqual(final['generation_settings'],{'cfg':1})
                    self.assertEqual(Path(original['record']).read_bytes(),original_record)
                    self.assertEqual(load_handle(Path(final['record']),root)['frame_count'],8)
                self.assertEqual(load_handle(Path(original['record']),root)['frame_hashes'],original['frame_hashes'])

    def test_real_preview_encoding_preserves_fps_and_count(self):
        import shutil
        if not shutil.which('ffmpeg') or not shutil.which('ffprobe'):
            self.skipTest('ffmpeg/ffprobe unavailable')
        with tempfile.TemporaryDirectory() as tmp:
            plan = review_plan(new_plan('abc',(32,32),'hair',['tip'],
                               [{'label':'tip','x':.5,'y':.5}],duration=1,fps=8,short_side=256))
            frames = np.zeros((9,256,256,3),dtype=np.uint8)
            frames[4] = 40
            h = save_candidate(frames,plan,42,Path(tmp),{})
            self.assertEqual(h['frame_count'],8)
            self.assertEqual(h['closure_mean'],0)
            self.assertTrue((Path(h['directory'])/'loop.mp4').is_file())
            self.assertTrue((Path(h['directory'])/'seam.mp4').is_file())

    def test_saved_candidate_reopens_and_finishes_without_generation(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan = review_plan(new_plan('abc', (32,32), 'hair', ['tip'],
                               [{'label':'tip','x':.5,'y':.5}], short_side=256))
            images = np.zeros((145,256,256,3), dtype=np.uint8)
            with patch('comfy_ltx_loop.candidates.encode_previews'):
                handle = save_candidate(images, plan, 42, Path(tmp), {'cfg':1})
                reopened = load_handle(Path(handle['record']), Path(tmp))
                calls = []
                def enhance(image, size):
                    calls.append(image.size)
                    return image.resize(size)
                final = finish_candidate(reopened, Path(tmp), '1440p', 3, enhance)
            self.assertEqual(final['frame_count'], 144)
            self.assertEqual(final['fps'],24)
            self.assertEqual(len(calls),144)
            self.assertNotEqual(handle['record'],final['record'])
            self.assertEqual(len(list(Path(handle['directory']).joinpath('raw').glob('*.png'))),145)
            self.assertNotIn('images',reopened)

    def test_invalid_count_and_external_record_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan = review_plan(new_plan('abc',(32,32),'hair',['tip'],
                               [{'label':'tip','x':.5,'y':.5}],short_side=256))
            with self.assertRaisesRegex(ValueError,'145'):
                save_candidate(np.zeros((144,256,256,3),dtype=np.uint8),plan,42,Path(tmp),{})
            with self.assertRaises(ValueError):
                load_handle(Path(tmp).parent/'record.json',Path(tmp))

    def test_modified_frame_blocks_finishing(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan = review_plan(new_plan('abc',(32,32),'hair',['tip'],
                               [{'label':'tip','x':.5,'y':.5}],short_side=256))
            with patch('comfy_ltx_loop.candidates.encode_previews'):
                h = save_candidate(np.zeros((145,256,256,3),dtype=np.uint8),plan,42,Path(tmp),{})
            Image.new('RGB',(256,256),'white').save(Path(h['directory'])/'frames/000001.png')
            with self.assertRaisesRegex(ValueError,'modified'):
                load_handle(Path(h['record']),Path(tmp))
