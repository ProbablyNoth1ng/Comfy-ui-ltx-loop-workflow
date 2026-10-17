import json
import sys
import tempfile
import types
import unittest
import weakref
from contextlib import nullcontext
from pathlib import Path
from unittest.mock import patch

import numpy as np
from PIL import Image

from comfy_ltx_loop.vision import analyze


class VisionTests(unittest.TestCase):
    def run_analysis(self, family, failure=None, target='character'):
        events, refs, templates = [], [], []
        class Model:
            device = 'cpu'
            def fail(self):
                raise ValueError('inner failure retaining model')
            def generate(self, **kwargs):
                events.append('generate')
                if failure == 'generate':
                    raise RuntimeError('generation failed')
                if failure == 'chained':
                    try:
                        self.fail()
                    except ValueError as error:
                        raise RuntimeError('generation failed') from error
                return np.array([[1,2,3]])
        class Loader:
            @classmethod
            def from_pretrained(cls, path, **kwargs):
                events.append(family)
                if failure == 'load':
                    raise RuntimeError('load failed')
                model = Model(); refs.append(weakref.ref(model))
                return model
        class Inputs(dict):
            def to(self, device):
                return self
        class Processor:
            @classmethod
            def from_pretrained(cls, path, **kwargs):
                return cls()
            def apply_chat_template(self, messages, **kwargs):
                templates.append((messages,kwargs))
                return Inputs(input_ids=np.array([[1,2]]))
            def batch_decode(self, tokens, **kwargs):
                return ['{"landmarks":[{"label":"left hair tip","x":300,"y":500,'
                        '"body_part":"hair","motion_role":"move","reason":"Requested sway"}]}']
        torch = types.SimpleNamespace(inference_mode=nullcontext, cuda=types.SimpleNamespace(
            is_available=lambda:True, empty_cache=lambda:events.append(('clean', any(ref() for ref in refs))),
            ipc_collect=lambda:events.append('ipc')))
        transformers = types.SimpleNamespace(__version__='5.2.0', AutoProcessor=Processor,
            Qwen3VLForConditionalGeneration=Loader, Qwen3_5ForConditionalGeneration=Loader)
        management = types.SimpleNamespace(unload_all_models=lambda:events.append('unload'))
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp,'config.json').write_text(json.dumps({'model_type':family,'architectures':[
                'Qwen3_5ForConditionalGeneration' if family=='qwen3_5' else 'Qwen3VLForConditionalGeneration']}))
            with patch.dict(sys.modules, {'torch':torch,'transformers':transformers,
                'comfy':types.ModuleType('comfy'),'comfy.model_management':management}):
                if failure:
                    with self.assertRaisesRegex(RuntimeError, 'failed'):
                        analyze(Image.new('RGB',(40,60)), 'Hair sway. Face stays still.', ['auto'], tmp,target=target)
                else:
                    points = analyze(Image.new('RGB',(40,60)), 'Hair sway. Face stays still.', ['auto'], tmp,target=target)
                    self.assertEqual(points[0]['body_part'], 'hair')
        self.assertIn(('clean', False), events)
        return events, templates

    def test_local_config_dispatches_both_families_and_disables_thinking_for_35(self):
        for family in ('qwen3_vl','qwen3_5'):
            events, templates = self.run_analysis(family)
            self.assertEqual(events[:3], ['unload',family,'generate'])
            self.assertEqual(templates[0][1].get('enable_thinking'), False if family=='qwen3_5' else None)
            instruction = templates[0][0][0]['content'][1]['text']
            self.assertIn('16', instruction)
            self.assertIn('24', instruction)
            self.assertIn('anchor', instruction)
            self.assertIn('Hair sway. Face stays still.', instruction)

    def test_load_and_generation_failures_release_model_before_cuda_cleanup(self):
        for family in ('qwen3_vl','qwen3_5'):
            for failure in ('load','generate','chained'):
                self.run_analysis(family, failure)

    def test_background_target_requests_environmental_motion_and_anchors(self):
        _, templates = self.run_analysis('qwen3_5',target='background')
        instruction = templates[0][0][0]['content'][1]['text']
        self.assertIn('environmental objects',instruction)
        self.assertIn('stationary anchors',instruction)
        self.assertIn('Hair sway. Face stays still.',instruction)

    def test_missing_snapshot_is_actionable_without_loading_model(self):
        with tempfile.TemporaryDirectory() as tmp, self.assertRaisesRegex(ValueError, 'snapshot'):
            analyze(Image.new('RGB',(40,60)), 'hair', ['auto'], tmp)
