import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from comfy_ltx_loop.staged_comfy import ComfyLTXLoopMotionEditor, ComfyLTXLoopSavedCandidate, ComfyLTXLoopUpscale, ComfyLTXLoopFinish


class StageTests(unittest.TestCase):
    def test_qwen2b_choice_preserves_existing_widget_slots_and_defaults(self):
        inputs = ComfyLTXLoopMotionEditor.INPUT_TYPES()['required']
        self.assertEqual(list(inputs), ['image','motion_prompt','requested_parts','duration',
            'fps','strength','short_side','seed','vision_model','preparation','plan_json','stage'])
        self.assertEqual(inputs['preparation'][0][:3], ['local Qwen','manual','local Qwen3.5'])
        self.assertIn('local Qwen3-VL 2B', inputs['preparation'][0])
        self.assertEqual(inputs['preparation'][1]['default'], 'local Qwen3.5')
        self.assertEqual(inputs['vision_model'][1]['default'], 'models/Qwen3.5-9B')

    def test_qwen2b_prepares_each_target_with_the_selected_snapshot(self):
        import numpy as np
        image = np.zeros((1,100,80,3),dtype=np.float32)
        path = 'models/Qwen3-VL-2B-Instruct'
        def proposals(source, prompt, requested, model, feedback=None, target='character'):
            self.assertEqual(model, path)
            return [dict(label='leaf' if target == 'background' else 'hair tip',
                x=.3,y=.4,body_part='foliage' if target == 'background' else 'hair',
                motion_role='move',reason='Requested sway')]
        for target, labels in [('character',['hair tip']),('background',['leaf']),
                               ('both',['hair tip','leaf'])]:
            with self.subTest(target=target), \
                 patch('comfy_ltx_loop.staged_comfy.canvas_image',return_value=image), \
                 patch('comfy_ltx_loop.staged_comfy.analyze',side_effect=proposals):
                plan = ComfyLTXLoopMotionEditor().execute(image,'Hair sway','auto',6,24,.01,720,
                    42,path,'local Qwen3-VL 2B','{}','prepare',background_prompt='Leaves sway',
                    prepare_target=target)['result'][2]
            self.assertEqual([p['label'] for p in plan['landmarks']], labels)
            self.assertEqual(plan['review']['state'], 'pending')
            for group in (['character','background'] if target == 'both' else [target]):
                settings = plan['analysis' if group == 'character' else 'background']
                self.assertEqual(settings['prepared_model_path'], path)

    def test_switching_to_2b_requires_reprepare_of_each_model_group(self):
        import numpy as np
        from comfy_ltx_loop.motion import review_plan
        image = np.zeros((1,100,80,3),dtype=np.float32)
        points = [dict(label='tip',x=.3,y=.4,body_part='hair',motion_role='move',reason='sway')]
        with patch('comfy_ltx_loop.staged_comfy.canvas_image',return_value=image), \
             patch('comfy_ltx_loop.staged_comfy.analyze',return_value=points):
            editor = ComfyLTXLoopMotionEditor()
            old = editor.execute(image,'hair','auto',6,24,.01,720,42,
                'models/Qwen3-VL-8B-Instruct','local Qwen','{}','prepare',
                background_prompt='Leaves sway',prepare_target='both')['result'][2]
            reviewed = json.dumps(review_plan(old))
            for active in [(True,False),(False,True)]:
                with self.subTest(active=active), self.assertRaisesRegex(ValueError, 'prepare'):
                    editor.execute(image,'hair','auto',6,24,.01,720,42,
                        'models/Qwen3-VL-2B-Instruct','local Qwen3-VL 2B',reviewed,'render',
                        background_prompt='Leaves sway',use_character_points=active[0],
                        use_background_points=active[1])
            partial = editor.execute(image,'hair','auto',6,24,.01,720,42,
                'models/Qwen3-VL-2B-Instruct','local Qwen3-VL 2B',reviewed,'prepare',
                background_prompt='Leaves sway',prepare_target='character')['result'][2]
            self.assertEqual(partial['analysis']['prepared_model_path'], 'models/Qwen3-VL-2B-Instruct')
            with self.assertRaisesRegex(ValueError, 'Prepare background'):
                review_plan(partial)
            complete = editor.execute(image,'hair','auto',6,24,.01,720,42,
                'models/Qwen3-VL-2B-Instruct','local Qwen3-VL 2B',json.dumps(partial),'prepare',
                background_prompt='Leaves sway',prepare_target='background')['result'][2]
            self.assertEqual(review_plan(complete)['review']['state'], 'reviewed')

    def test_qwen2b_load_failure_preserves_points_and_preparation_history(self):
        import numpy as np
        image = np.zeros((1,100,80,3),dtype=np.float32)
        points = [dict(label='tip',x=.3,y=.4,body_part='hair',motion_role='move',reason='sway')]
        with patch('comfy_ltx_loop.staged_comfy.canvas_image',return_value=image):
            editor = ComfyLTXLoopMotionEditor()
            with patch('comfy_ltx_loop.staged_comfy.analyze',return_value=points):
                old = editor.execute(image,'hair','auto',6,24,.01,720,42,
                    'models/Qwen3.5-9B','local Qwen3.5','{}','prepare')['result'][2]
            with patch('comfy_ltx_loop.staged_comfy.analyze',side_effect=RuntimeError('loading failed')):
                failed = editor.execute(image,'hair','auto',6,24,.01,720,42,
                    'models/Qwen3-VL-2B-Instruct','local Qwen3-VL 2B',json.dumps(old),'prepare')['result'][2]
        self.assertEqual(failed['landmarks'], old['landmarks'])
        self.assertEqual(failed['analysis'], old['analysis'])
        self.assertIn('loading failed', failed['feedback'][0])
        self.assertEqual(failed['review']['state'], 'pending')

    def test_direct_render_without_preparation_uses_empty_tracks_and_text(self):
        import numpy as np
        image = np.zeros((1,100,80,3),dtype=np.float32)
        with patch('comfy_ltx_loop.staged_comfy.canvas_image',return_value=image), \
             patch('comfy_ltx_loop.staged_comfy.analyze') as analyze:
            result = ComfyLTXLoopMotionEditor().execute(image,'Hair sways','auto',6,24,.01,720,
                42,'model','local Qwen3.5','{}','render',background_prompt='Leaves sway')
        analyze.assert_not_called()
        self.assertEqual(json.loads(result['result'][1]),[])
        plan = result['result'][2]
        self.assertEqual(plan['review']['state'],'not_required')
        self.assertIn('Hair sways',result['result'][6])
        self.assertIn('Background motion: Leaves sway',result['result'][6])

    def test_saved_points_with_both_groups_off_render_without_review(self):
        import hashlib
        import numpy as np
        from comfy_ltx_loop.motion import new_plan
        image = np.zeros((1,100,80,3),dtype=np.float32)
        identity = hashlib.sha256(image[0].astype(np.uint8).tobytes()+str((80,100)).encode()).hexdigest()
        old = new_plan(identity,(80,100),'old text',['auto'],[{'label':'tip','x':.3,'y':.4}])
        old['landmarks'].append({**old['landmarks'][0],'label':'leaf','group':'background'})
        with patch('comfy_ltx_loop.staged_comfy.canvas_image',return_value=image):
            result = ComfyLTXLoopMotionEditor().execute(image,'new text','auto',6,24,.01,720,
                42,'model','manual',json.dumps(old),'render',background_prompt='Leaves sway',
                use_character_points=False,use_background_points=False)
        self.assertEqual(json.loads(result['result'][1]),[])
        self.assertEqual(len(result['result'][2]['landmarks']),2)
        self.assertEqual(result['result'][2]['review']['state'],'not_required')

    def test_direct_render_preserves_preparation_history_for_reenabled_points(self):
        import hashlib
        import numpy as np
        from comfy_ltx_loop.motion import new_plan, review_plan
        image = np.zeros((1,100,80,3),dtype=np.float32)
        identity = hashlib.sha256(image[0].astype(np.uint8).tobytes()+str((80,100)).encode()).hexdigest()
        old = new_plan(identity,(80,100),'old hair',['auto'],[{'label':'tip','x':.3,'y':.4}])
        old['analysis'] = {'preparation':'manual','model_path':'model',
                           'prepared_prompt':'old hair','prepared_requested':['auto'],
                           'prepared_preparation':'manual','prepared_model_path':'model'}
        old['landmarks'].append({**old['landmarks'][0],'label':'leaf','group':'background'})
        old['background'] = {'enabled':True,'prompt':'Old leaves','preparation':'manual',
                             'prepared_prompt':'Old leaves','prepared_preparation':'manual'}
        with patch('comfy_ltx_loop.staged_comfy.canvas_image',return_value=image):
            rendered = ComfyLTXLoopMotionEditor().execute(image,'new hair','auto',6,24,.01,720,
                42,'model','manual',json.dumps(old),'render',background_prompt='New leaves',
                background_preparation='manual',use_character_points=False,
                use_background_points=False)['result'][2]
        rendered['use_character_points'] = True
        with self.assertRaisesRegex(ValueError,'Prepare character'):
            review_plan(rendered)
        rendered['use_character_points'] = False
        rendered['use_background_points'] = True
        with self.assertRaisesRegex(ValueError,'Prepare background'):
            review_plan(rendered)

    def test_enabling_background_text_activates_saved_background_points(self):
        import hashlib
        import numpy as np
        from comfy_ltx_loop.motion import new_plan
        image = np.zeros((1,100,80,3),dtype=np.float32)
        identity = hashlib.sha256(image[0].astype(np.uint8).tobytes()+str((80,100)).encode()).hexdigest()
        old = new_plan(identity,(80,100),'hair',['auto'],[{'label':'leaf','x':.3,'y':.4}])
        old['landmarks'][0]['group'] = 'background'
        old['background'] = {'enabled':False,'prompt':'','preparation':'manual'}
        with patch('comfy_ltx_loop.staged_comfy.canvas_image',return_value=image):
            with self.assertRaisesRegex(ValueError,'review'):
                ComfyLTXLoopMotionEditor().execute(image,'hair','auto',6,24,.01,720,
                    42,'model','manual',json.dumps(old),'render',background_prompt='Leaves sway')

    def test_new_finish_defaults_and_old_upscale_contract(self):
        modern = ComfyLTXLoopFinish.INPUT_TYPES()['required']
        legacy = ComfyLTXLoopUpscale.INPUT_TYPES()['required']
        self.assertEqual(modern['resolution'][1]['default'],'1080p')
        self.assertEqual(modern['method'][1]['default'],'Fast')
        self.assertEqual(modern['method'][0],['Fast','Balanced AI','Original AI'])
        self.assertEqual(list(legacy),['candidate','resolution','chunk_size'])
        self.assertEqual(legacy['resolution'][1]['default'],'1440p')
        candidate = {'record':'saved'}
        with patch('comfy_ltx_loop.staged_comfy.output_root',return_value=Path('output')), \
             patch('comfy_ltx_loop.staged_comfy.finish_candidate',return_value={'directory':'output/finish','record':'output/finish/record.json'}) as finish, \
             patch('comfy_ltx_loop.staged_comfy.preview_ui',return_value={}):
            ComfyLTXLoopFinish().execute(candidate,'1080p','Balanced AI',4)
            self.assertEqual(finish.call_args.kwargs,{'method':'balanced_ai'})
            ComfyLTXLoopUpscale().execute(candidate,'1440p',4)
            self.assertEqual(finish.call_args.kwargs,{})

    def test_combined_prepare_builds_both_groups_in_one_plan(self):
        import numpy as np
        image = np.zeros((1,100,80,3),dtype=np.float32)
        suggestions = [
            [dict(label='tip',x=.3,y=.4,body_part='hair',motion_role='move',reason='sway')],
            [dict(label='leaf',x=.7,y=.3,body_part='foliage',motion_role='move',reason='wind')],
        ]
        with patch('comfy_ltx_loop.staged_comfy.canvas_image',return_value=image), \
             patch('comfy_ltx_loop.staged_comfy.analyze',side_effect=suggestions) as analyze:
            plan = ComfyLTXLoopMotionEditor().execute(image,'hair','auto',6,24,.01,720,
                42,'model','local Qwen','{}','prepare',background_prompt='Leaves sway',
                background_preparation='model',prepare_target='both')['result'][2]
        self.assertEqual(analyze.call_count,2)
        self.assertEqual([point.get('group','character') for point in plan['landmarks']],
                         ['character','background'])
        self.assertEqual(plan['review']['state'],'pending')
        self.assertEqual(plan['background']['enabled'],True)

    def test_background_model_replaces_only_background_and_render_combines_guidance(self):
        import hashlib
        import numpy as np
        from comfy_ltx_loop.motion import new_plan, review_plan
        image = np.zeros((1,100,80,3),dtype=np.float32)
        identity = hashlib.sha256(image[0].astype(np.uint8).tobytes()+str((80,100)).encode()).hexdigest()
        old = new_plan(identity,(80,100),'hair',['auto'],[{'label':'tip','x':.3,'y':.4}])
        old['analysis'] = {'preparation':'manual','model_path':'model','prepared_prompt':'hair',
                           'prepared_requested':['auto'],'prepared_preparation':'manual','prepared_model_path':'model'}
        old['landmarks'][0]['path'][1]['x'] = .304
        old['background'] = {'enabled':True,'prompt':'Old leaves','preparation':'model',
            'prepared_prompt':'Old leaves','prepared_preparation':'model'}
        old['landmarks'].append({**old['landmarks'][0],'label':'old leaf','group':'background'})
        suggestion = [dict(label='leaf',x=.6,y=.3,body_part='foliage',motion_role='move',reason='sway')]
        with patch('comfy_ltx_loop.staged_comfy.canvas_image',return_value=image), \
             patch('comfy_ltx_loop.staged_comfy.analyze',return_value=suggestion) as analyze:
            prepared = ComfyLTXLoopMotionEditor().execute(image,'hair','auto',6,24,.01,720,
                42,'model','manual',json.dumps(old),'prepare',animate_background=True,
                background_prompt='Leaves sway',background_preparation='model',prepare_target='background')['result'][2]
        self.assertEqual(analyze.call_args.kwargs['target'],'background')
        self.assertEqual(prepared['landmarks'][0],old['landmarks'][0])
        self.assertEqual([p['label'] for p in prepared['landmarks']],['tip','leaf'])
        self.assertEqual(prepared['analysis'],old['analysis'])
        reviewed = review_plan(prepared)
        with patch('comfy_ltx_loop.staged_comfy.canvas_image',return_value=image):
            result = ComfyLTXLoopMotionEditor().execute(image,'hair','auto',6,24,.01,720,
                42,'model','manual',json.dumps(reviewed),'render',animate_background=True,
                background_prompt='Leaves sway',background_preparation='model')
        self.assertEqual(len(json.loads(result['result'][1])),2)
        self.assertIn('Background motion: Leaves sway',result['result'][6])
        self.assertIn('Stationary camera',result['result'][6])
        reviewed['background']['enabled'] = False
        reviewed = review_plan(reviewed)
        with patch('comfy_ltx_loop.staged_comfy.canvas_image',return_value=image):
            off = ComfyLTXLoopMotionEditor().execute(image,'hair','auto',6,24,.01,720,
                42,'model','manual',json.dumps(reviewed),'render',animate_background=False,
                background_prompt='',background_preparation='model')
        self.assertEqual(len(json.loads(off['result'][1])),1)
        self.assertEqual(len(off['result'][2]['landmarks']),2)
        self.assertIn('stationary background',off['result'][6])

    def test_failed_background_model_preserves_existing_points_and_stale_preparation(self):
        import hashlib
        import numpy as np
        from comfy_ltx_loop.motion import new_plan
        image = np.zeros((1,100,80,3),dtype=np.float32)
        identity = hashlib.sha256(image[0].astype(np.uint8).tobytes()+str((80,100)).encode()).hexdigest()
        old = new_plan(identity,(80,100),'hair',['auto'],[{'label':'tip','x':.3,'y':.4}])
        old['landmarks'].append({**old['landmarks'][0],'label':'leaf','group':'background'})
        old['background'] = {'enabled':True,'prompt':'Old leaves','preparation':'model',
            'prepared_prompt':'Old leaves','prepared_preparation':'model'}
        with patch('comfy_ltx_loop.staged_comfy.canvas_image',return_value=image), \
             patch('comfy_ltx_loop.staged_comfy.analyze',side_effect=RuntimeError('GPU failed')):
            plan = ComfyLTXLoopMotionEditor().execute(image,'hair','auto',6,24,.01,720,
                42,'model','manual',json.dumps(old),'prepare',animate_background=True,
                background_prompt='New leaves',background_preparation='model',prepare_target='background')['result'][2]
        self.assertEqual(plan['landmarks'],old['landmarks'])
        self.assertEqual(plan['background']['prepared_prompt'],'Old leaves')
        self.assertIn('GPU failed',plan['feedback'][0])
        with self.assertRaisesRegex(ValueError, 'Prepare background'):
            from comfy_ltx_loop.motion import review_plan
            review_plan(plan)

    def test_background_prepare_does_not_refresh_changed_character_prompt(self):
        import hashlib
        import numpy as np
        from comfy_ltx_loop.motion import new_plan, review_plan
        image = np.zeros((1,100,80,3),dtype=np.float32)
        identity = hashlib.sha256(image[0].astype(np.uint8).tobytes()+str((80,100)).encode()).hexdigest()
        old = new_plan(identity,(80,100),'old hair',['auto'],[{'label':'tip','x':.3,'y':.4}])
        old['analysis'] = {'preparation':'manual','model_path':'model','prepared_prompt':'old hair',
            'prepared_requested':['auto'],'prepared_preparation':'manual','prepared_model_path':'model'}
        with patch('comfy_ltx_loop.staged_comfy.canvas_image',return_value=image):
            plan = ComfyLTXLoopMotionEditor().execute(image,'new hair','auto',6,24,.01,720,
                42,'model','manual',json.dumps(old),'prepare',animate_background=True,
                background_prompt='Leaves sway',background_preparation='manual',prepare_target='background')['result'][2]
        self.assertEqual(plan['analysis'],old['analysis'])
        with self.assertRaisesRegex(ValueError, 'Prepare character'):
            review_plan(plan)

    def test_background_manual_prepare_preserves_character_without_model(self):
        import numpy as np
        from comfy_ltx_loop.motion import new_plan
        image = np.zeros((1,100,80,3),dtype=np.float32)
        import hashlib
        identity = hashlib.sha256(image[0].astype(np.uint8).tobytes()+str((80,100)).encode()).hexdigest()
        old = new_plan(identity,(80,100),'hair',['auto'],[{'label':'tip','x':.3,'y':.4}])
        old['landmarks'][0]['path'][1]['x'] = .305
        with patch('comfy_ltx_loop.staged_comfy.canvas_image',return_value=image), \
             patch('comfy_ltx_loop.staged_comfy.analyze') as analyze:
            result = ComfyLTXLoopMotionEditor().execute(image,'hair','auto',6,24,.01,720,
                42,'model','manual',json.dumps(old),'prepare',animate_background=True,
                background_prompt='Leaves sway',background_preparation='manual',prepare_target='background')
        analyze.assert_not_called()
        plan = result['result'][2]
        self.assertEqual(plan['landmarks'][0],old['landmarks'][0])
        self.assertEqual(plan['background']['prepared_prompt'],'Leaves sway')

    def test_new_qwen_choice_keeps_widget_order_and_blocks_stale_analysis_settings(self):
        import numpy as np
        from comfy_ltx_loop.motion import review_plan
        image = np.zeros((1,100,80,3),dtype=np.float32)
        inputs = ComfyLTXLoopMotionEditor.INPUT_TYPES()['required']
        self.assertEqual(list(inputs)[8:12], ['vision_model','preparation','plan_json','stage'])
        self.assertIn('local Qwen3.5', inputs['preparation'][0])
        self.assertEqual(inputs['requested_parts'][1]['default'], 'auto')
        points = [dict(label='tip',x=.3,y=.4,body_part='hair',motion_role='move',reason='sway')]
        with patch('comfy_ltx_loop.staged_comfy.canvas_image',return_value=image), \
             patch('comfy_ltx_loop.staged_comfy.analyze',return_value=points):
            prepared = ComfyLTXLoopMotionEditor().execute(image,'hair','auto',6,24,.01,720,
                         42,'models/Qwen3.5-9B','local Qwen3.5','{}','prepare')['result'][2]
            self.assertEqual(prepared['analysis']['prepared_prompt'], 'hair')
            reviewed = json.dumps(review_plan(prepared))
            for model, mode in [('other','local Qwen3.5'),('models/Qwen3.5-9B','manual')]:
                with self.assertRaisesRegex(ValueError, 'prepare'):
                    ComfyLTXLoopMotionEditor().execute(image,'hair','auto',6,24,.01,720,
                         43,model,mode,reviewed,'render')

    def test_qwen35_partial_feedback_and_load_failure_leave_manual_editor_available(self):
        import numpy as np
        image = np.zeros((1,100,80,3),dtype=np.float32)
        def partial(source,prompt,requested,model,feedback=None):
            feedback.append('Omitted: shoulder hidden')
            return [dict(label='eye',x=.4,y=.3,body_part='face',motion_role='anchor',reason='stationary face')]
        with patch('comfy_ltx_loop.staged_comfy.canvas_image',return_value=image):
            for analyzer in [partial, RuntimeError('loading failed')]:
                with patch('comfy_ltx_loop.staged_comfy.analyze',side_effect=analyzer):
                    plan = ComfyLTXLoopMotionEditor().execute(image,'hair','auto',6,24,.01,720,
                        42,'models/Qwen3.5-9B','local Qwen3.5','{}','prepare')['result'][2]
                self.assertEqual(plan['review']['state'],'pending')
                self.assertTrue(plan['feedback'])
                self.assertEqual(len(plan['landmarks']), 0 if isinstance(analyzer,Exception) else 1)

    def test_saved_candidates_are_complete_and_newest_first_with_portable_paths(self):
        from comfy_ltx_loop.candidates import list_candidates
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name, state, stamp in [('candidate-a-new','awaiting_visual_review',300),
                                       ('candidate-z-old','awaiting_visual_review',100),
                                       ('candidate-pending','encoding',400)]:
                directory = root/name
                directory.mkdir()
                path = directory/'record.json'
                path.write_text(json.dumps({'schema':'comfy-ltx-loop-render-handle/1','kind':'candidate','state':state}))
                (directory/'loop.mp4').write_bytes(b'video')
                (directory/'seam.mp4').write_bytes(b'video')
                os.utime(path, ns=(stamp,stamp))
            corrupt = root/'candidate-corrupt'
            corrupt.mkdir()
            (corrupt/'record.json').write_text('{')
            missing = root/'candidate-missing'
            missing.mkdir()
            (missing/'record.json').write_text(json.dumps({'schema':'comfy-ltx-loop-render-handle/1',
                'kind':'candidate','state':'awaiting_visual_review'}))
            expected = ['candidate-a-new/record.json','candidate-z-old/record.json']
            self.assertEqual(list_candidates(root),expected)
            with patch('comfy_ltx_loop.staged_comfy.output_root',return_value=root):
                self.assertEqual(ComfyLTXLoopSavedCandidate.INPUT_TYPES()['required']['candidate'][0],expected)

    def test_interfaces_have_no_upstream_generation_for_finishing(self):
        with tempfile.TemporaryDirectory() as tmp, patch('comfy_ltx_loop.staged_comfy.output_root',return_value=Path(tmp)):
            inputs = ComfyLTXLoopSavedCandidate.INPUT_TYPES()['required']
        self.assertEqual(set(inputs),{'candidate'})
        self.assertEqual(ComfyLTXLoopMotionEditor.RETURN_TYPES[2],'MOTION_PLAN')

    def test_prepare_failure_keeps_manual_plan(self):
        import numpy as np
        image = np.zeros((1,100,80,3),dtype=np.float32)
        with patch('comfy_ltx_loop.staged_comfy.image_array',return_value=image[0].astype(np.uint8)), \
             patch('comfy_ltx_loop.staged_comfy.canvas_image',return_value=image), \
             patch('comfy_ltx_loop.staged_comfy.analyze',side_effect=ValueError('Missing hair tip')):
            result = ComfyLTXLoopMotionEditor().execute(image,'hair','hair tip',6,24,.01,720,
                         42,'Qwen3-VL-8B-Instruct','local Qwen','{}','prepare')
        plan = result['result'][2]
        self.assertEqual(plan['landmarks'],[])
        self.assertIn('Missing hair tip',plan['feedback'][0])
        self.assertEqual(plan['review']['state'],'pending')
        self.assertEqual(result['ui']['motion_plan'][0], plan)
        self.assertTrue(result['ui']['bg_image'][0])

    def test_manual_prepare_exposes_the_same_plan_in_ui_and_result(self):
        import numpy as np
        image = np.zeros((1,100,80,3),dtype=np.float32)
        with patch('comfy_ltx_loop.staged_comfy.image_array',return_value=image[0].astype(np.uint8)), \
             patch('comfy_ltx_loop.staged_comfy.canvas_image',return_value=image):
            result = ComfyLTXLoopMotionEditor().execute(image,'hair','hair tip',3,24,.01,720,
                         42,'Qwen3-VL-8B-Instruct','manual','{}','prepare')
        self.assertEqual(result['ui']['motion_plan'][0], result['result'][2])
        self.assertEqual(result['result'][2]['frames'],73)
        self.assertEqual(result['result'][2]['landmarks'],[])
        self.assertTrue(result['ui']['bg_image'][0])

    def test_manual_accepted_points_reject_new_image(self):
        import numpy as np
        from comfy_ltx_loop.motion import new_plan, review_plan
        old = review_plan(new_plan('old', (80, 100), 'old prompt', ['tip'],
                    [{'label':'tip','x':.25,'y':.4}], 6, 24, .01, 720))
        image = np.zeros((1,60,90,3), dtype=np.float32)
        with patch('comfy_ltx_loop.staged_comfy.canvas_image', return_value=image):
            with self.assertRaisesRegex(ValueError, 'Source image changed'):
                ComfyLTXLoopMotionEditor().execute(image, 'new prompt', 'head', 3, 24,
                    .02, 800, 99, 'unused', 'manual', json.dumps(old), 'render')

    def test_render_never_analyzes_and_stale_review_fails(self):
        import numpy as np
        from comfy_ltx_loop.motion import new_plan
        image = np.zeros((1,100,80,3),dtype=np.float32)
        old = new_plan('stale',(80,100),'hair',['hair tip'],[{'label':'tip','x':.3,'y':.4}])
        with patch('comfy_ltx_loop.staged_comfy.image_array',return_value=image[0].astype(np.uint8)), \
             patch('comfy_ltx_loop.staged_comfy.analyze') as analysis:
            with self.assertRaises(ValueError):
                ComfyLTXLoopMotionEditor().execute(image,'hair','hair tip',6,24,.01,720,
                             42,'Qwen3-VL-8B-Instruct','local Qwen',json.dumps(old),'render')
        analysis.assert_not_called()
