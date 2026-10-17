import json
import hashlib
from io import BytesIO
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from cloud import install


class VisionInstallTests(unittest.TestCase):
    def test_complete_legacy_cache_migrates_without_resolving_or_replacing_weights(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(sys.modules, {'huggingface_hub':self.hub([])}):
            root=Path(tmp);comfy=root/'ComfyUI';(comfy/'models').mkdir(parents=True);state=root/'state';state.mkdir()
            assets=[dict(repo='Org/Renderer',revision='main',filename='renderer.safetensors',
                         target='renderer.safetensors',local_dir='.')]
            records=[]
            for target,repo in [('renderer.safetensors','Org/Renderer'),
                ('Qwen3-VL-8B-Instruct/config.json','Qwen/Qwen3-VL-8B-Instruct'),
                ('Qwen3-VL-8B-Instruct/model.safetensors','Qwen/Qwen3-VL-8B-Instruct'),
                (install.UPSCALER,None)]:
                path=comfy/'models'/target;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'kept')
                record=dict(target=target,size=4,sha256=install.sha256(path))
                if repo:record.update(repo=repo,revision='b'*40,filename=path.name,
                                      local_dir=str(Path(target).parent).replace('\\','/'))
                records.append(record)
            signature=hashlib.sha256(json.dumps(assets,sort_keys=True).encode()).hexdigest()
            install.write_json(state/'models-ready.json',dict(signature=signature,files=records))
            resolve = install.resolve_plan
            def resolve_only_2b(assets, vision_repo):
                self.assertEqual(assets, [])
                self.assertEqual(vision_repo, 'Qwen/Qwen3-VL-2B-Instruct')
                return resolve(assets, vision_repo)
            with patch.object(install,'model_assets',return_value=assets),patch.object(install,'resolve_plan',side_effect=resolve_only_2b):
                install.download_models(root,comfy,state)
            ready=install.read_json(state/'models-ready.json')
            self.assertEqual(ready['vision_repo'],'Qwen/Qwen3-VL-8B-Instruct')
            self.assertEqual(ready['files'],records)
            self.assertEqual((comfy/'models/Qwen3-VL-8B-Instruct/model.safetensors').read_bytes(),b'kept')
            self.assertEqual((comfy/'models/Qwen3-VL-2B-Instruct/model.safetensors').read_bytes(),b'data')
            self.assertEqual(install.read_json(state/'vision-Qwen3-VL-8B-Instruct.json')['files'][0]['revision'], 'b'*40)

    def test_new_workflow_matches_installed_analyzer_and_saved_workflows_are_preserved(self):
        project=Path(__file__).resolve().parents[1]
        for repo,path,mode in [('Qwen/Qwen3.5-9B','models/Qwen3.5-9B','local Qwen3.5'),
                               ('Qwen/Qwen3-VL-8B-Instruct','models/Qwen3-VL-8B-Instruct','local Qwen')]:
            with tempfile.TemporaryDirectory() as tmp:
                destination=Path(tmp)
                install.install_workflows(project,destination,repo)
                workflow=json.loads((destination/'comfy-ltx-loop-motion.json').read_text())
                editor=next(n for n in workflow['nodes'] if n['type']=='ComfyLTXLoopMotionEditor')
                self.assertEqual(editor['widgets_values'][7:9],[path,mode])
                self.assertEqual((destination/'ltx-2.5-motion-track.official.json').read_bytes(),
                                 (project/'workflows/ltx-2.5-motion-track.official.json').read_bytes())
                saved=destination/'comfy-ltx-loop-motion.json';saved.write_text('{"custom":"saved widgets"}')
                install.install_workflows(project,destination,'Qwen/Qwen3.5-9B')
                self.assertEqual(saved.read_text(),'{"custom":"saved widgets"}')

    def hub(self, downloads, revisions=None):
        revisions = revisions or {}
        class Api:
            def model_info(self, repo, revision, files_metadata):
                names = ['config.json','model.safetensors'] if repo.startswith('Qwen/') else ['renderer.safetensors']
                return types.SimpleNamespace(sha=revisions.get(repo,'a'*40),siblings=[types.SimpleNamespace(
                    rfilename=name,size=4,lfs=None) for name in names])
        def download(repo_id, filename, revision, local_dir, force_download=False):
            self.assertEqual(revision,revisions.get(repo_id,'a'*40))
            downloads.append((repo_id,filename))
            path = Path(local_dir)/filename;path.parent.mkdir(parents=True,exist_ok=True)
            path.write_bytes(b'data');return str(path)
        return types.SimpleNamespace(HfApi=Api,hf_hub_download=download)

    def test_all_snapshots_have_distinct_destinations_and_immutable_revisions(self):
        with patch.dict(sys.modules, {'huggingface_hub':self.hub([])}):
            for repo, folder in [('Qwen/Qwen3.5-9B','Qwen3.5-9B'),
                                 ('Qwen/Qwen3-VL-8B-Instruct','Qwen3-VL-8B-Instruct'),
                                 ('Qwen/Qwen3-VL-2B-Instruct','Qwen3-VL-2B-Instruct')]:
                records = install.resolve_plan([], vision_repo=repo)
                self.assertEqual({r['target'] for r in records},{folder+'/config.json',folder+'/model.safetensors'})
                self.assertTrue(all(r['revision']=='a'*40 for r in records))

    def test_clean_install_downloads_2b_and_defaults_workflow_to_9b(self):
        calls = []
        response = BytesIO(b'anime');response.headers = {'Content-Type':'application/octet-stream'}
        spandrel = types.SimpleNamespace(ModelLoader=lambda:types.SimpleNamespace(
            load_from_file=lambda path:None))
        with tempfile.TemporaryDirectory() as tmp, patch.dict(sys.modules, {
            'huggingface_hub':self.hub(calls), 'spandrel':spandrel}):
            root = Path(tmp);comfy = root/'ComfyUI';comfy.mkdir();state = root/'state';state.mkdir()
            assets = [dict(repo='Org/Renderer',revision='main',filename='renderer.safetensors',
                           target='renderer.safetensors',local_dir='.')]
            with patch.object(install,'model_assets',return_value=assets), \
                 patch.object(install,'urlopen',return_value=response):
                install.download_models(root,comfy,state)
            ready = install.read_json(state/'models-ready.json')
            self.assertEqual(ready['vision_repo'], 'Qwen/Qwen3.5-9B')
            self.assertEqual({repo for repo,_ in calls}, {
                'Org/Renderer','Qwen/Qwen3.5-9B','Qwen/Qwen3-VL-2B-Instruct'})
            project = Path(__file__).resolve().parents[1]
            install.install_workflows(project, comfy/'user/workflows', ready['vision_repo'])
            workflow = install.read_json(comfy/'user/workflows/comfy-ltx-loop-motion.json')
            editor = next(n for n in workflow['nodes'] if n['type'] == 'ComfyLTXLoopMotionEditor')
            self.assertEqual(editor['widgets_values'][7:9], ['models/Qwen3.5-9B','local Qwen3.5'])

    def install_fixture(self, tmp):
        root = Path(tmp);comfy = root/'ComfyUI';comfy.mkdir();state = root/'state';state.mkdir()
        upscaler = comfy/'models'/install.UPSCALER
        upscaler.parent.mkdir(parents=True);upscaler.write_bytes(b'anime')
        install.write_json(state/'models-ready.json', {'signature':'old','files':[
            dict(target=install.UPSCALER,size=5,sha256=install.sha256(upscaler))]})
        assets = [dict(repo='Org/Renderer',revision='main',filename='renderer.safetensors',
                       target='renderer.safetensors',local_dir='.')]
        return root, comfy, state, assets

    def test_default_install_adds_2b_with_independent_pins_and_reuses_both_snapshots(self):
        calls = []
        hub = self.hub(calls, {'Qwen/Qwen3-VL-2B-Instruct':'2'*40})
        with tempfile.TemporaryDirectory() as tmp, patch.dict(sys.modules, {'huggingface_hub':hub}):
            root,comfy,state,assets = self.install_fixture(tmp)
            with patch.object(install,'model_assets',return_value=assets):
                install.download_models(root,comfy,state)
                self.assertEqual(install.read_json(state/'models-ready.json')['vision_repo'], 'Qwen/Qwen3.5-9B')
                for folder, revision in [('Qwen3.5-9B','a'*40),('Qwen3-VL-2B-Instruct','2'*40)]:
                    manifest = install.read_json(state/('vision-'+folder+'.json'))
                    self.assertIsNotNone(manifest, folder+' must have independent provenance')
                    self.assertEqual({r['revision'] for r in manifest['files']}, {revision})
                    self.assertTrue(all(r['sha256'] == hashlib.sha256(b'data').hexdigest()
                                        for r in manifest['files']))
                    self.assertEqual((comfy/'models'/folder/'model.safetensors').read_bytes(), b'data')
                count = len(calls)
                with patch.object(install,'resolve_plan',side_effect=AssertionError('must reuse pins')):
                    install.download_models(root,comfy,state)
                self.assertEqual(len(calls), count)

    def test_interrupted_2b_download_resumes_its_pinned_plan(self):
        calls = []
        hub = self.hub(calls, {'Qwen/Qwen3-VL-2B-Instruct':'2'*40})
        download = hub.hf_hub_download
        interrupted = False
        def interrupt_once(**kwargs):
            nonlocal interrupted
            if kwargs['repo_id'] == 'Qwen/Qwen3-VL-2B-Instruct' and kwargs['filename'].endswith('.safetensors') and not interrupted:
                interrupted = True
                (Path(kwargs['local_dir'])/kwargs['filename']).write_bytes(b'da')
                raise ConnectionError('interrupted')
            return download(**kwargs)
        hub.hf_hub_download = interrupt_once
        with tempfile.TemporaryDirectory() as tmp, patch.dict(sys.modules, {'huggingface_hub':hub}):
            root,comfy,state,assets = self.install_fixture(tmp)
            with patch.object(install,'model_assets',return_value=assets):
                with self.assertRaisesRegex(RuntimeError, 'restart to resume'):
                    install.download_models(root,comfy,state)
                self.assertFalse((state/'vision-Qwen3-VL-2B-Instruct.json').exists())
                plan = install.read_json(state/'vision-Qwen3-VL-2B-Instruct-plan.json')
                self.assertEqual({r['revision'] for r in plan['files']}, {'2'*40})
                # Both the larger plan and the 2B plan must survive the interrupted run.
                with patch.object(install,'resolve_plan',side_effect=AssertionError('must resume pins')):
                    install.download_models(root,comfy,state)
                self.assertEqual((comfy/'models/Qwen3-VL-2B-Instruct/model.safetensors').read_bytes(), b'data')
                self.assertIsNotNone(install.read_json(state/'vision-Qwen3-VL-2B-Instruct.json'))

    def test_truncated_2b_cache_recovers_without_touching_larger_snapshot(self):
        calls = []
        with tempfile.TemporaryDirectory() as tmp, patch.dict(sys.modules, {'huggingface_hub':self.hub(calls)}):
            root,comfy,state,assets = self.install_fixture(tmp)
            with patch.object(install,'model_assets',return_value=assets):
                install.download_models(root,comfy,state)
                weights = comfy/'models/Qwen3-VL-2B-Instruct/model.safetensors'
                self.assertTrue(weights.is_file(), '2B must be installed by default')
                larger = (state/'vision-Qwen3.5-9B.json').read_bytes()
                for content in (b'da', None):
                    if content is None:
                        weights.unlink()
                    else:
                        weights.write_bytes(content)
                    calls.clear()
                    with patch.object(install,'resolve_plan',side_effect=AssertionError('must reuse pins')):
                        install.download_models(root,comfy,state)
                    self.assertEqual(weights.read_bytes(), b'data')
                    self.assertTrue(calls)
                    self.assertTrue(all(repo == 'Qwen/Qwen3-VL-2B-Instruct' for repo,_ in calls))
                    self.assertEqual((state/'vision-Qwen3.5-9B.json').read_bytes(), larger)

    def test_truncated_2b_file_with_retained_hub_metadata_is_redownloaded(self):
        calls = []
        hub = self.hub(calls)
        download = hub.hf_hub_download
        def cached_download(**kwargs):
            # An immutable Hub commit with matching local metadata can return the
            # file without checking size. Only force_download bypasses that cache.
            path = Path(kwargs['local_dir'])/kwargs['filename']
            if path.is_file() and not kwargs.get('force_download',False):
                return str(path)
            return download(**kwargs)
        hub.hf_hub_download = cached_download
        with tempfile.TemporaryDirectory() as tmp, patch.dict(sys.modules, {'huggingface_hub':hub}):
            root,comfy,state,assets = self.install_fixture(tmp)
            with patch.object(install,'model_assets',return_value=assets):
                install.download_models(root,comfy,state)
                weights = comfy/'models/Qwen3-VL-2B-Instruct/model.safetensors'
                weights.write_bytes(b'da')
                calls.clear()
                with patch.object(install,'resolve_plan',side_effect=AssertionError('must reuse pins')):
                    install.download_models(root,comfy,state)
                self.assertEqual(weights.read_bytes(), b'data')
                self.assertEqual(calls, [('Qwen/Qwen3-VL-2B-Instruct','model.safetensors')])

    def test_selection_changes_cache_identity_preserves_old_weights_and_records_checksums(self):
        calls=[]
        with tempfile.TemporaryDirectory() as tmp, patch.dict(sys.modules, {'huggingface_hub':self.hub(calls)}):
            root=Path(tmp);comfy=root/'ComfyUI';comfy.mkdir();state=root/'state';state.mkdir()
            upscaler=comfy/'models'/install.UPSCALER;upscaler.parent.mkdir(parents=True);upscaler.write_bytes(b'anime')
            old=comfy/'models/Qwen3-VL-8B-Instruct/model.safetensors';old.parent.mkdir();old.write_bytes(b'old!')
            install.write_json(state/'models-ready.json', {'signature':'old',
                'vision_repo':'Qwen/Qwen3-VL-8B-Instruct', 'files':[{'target':install.UPSCALER,
                'size':5,'sha256':install.sha256(upscaler)}]})
            assets=[dict(repo='Org/Renderer',revision='main',filename='renderer.safetensors',
                         target='renderer.safetensors',local_dir='.')]
            with patch.object(install,'model_assets',return_value=assets),patch.object(install,'read_json',wraps=install.read_json) as read:
                # Only the workflow read is a fixture; manifests use real disk files.
                read.side_effect=lambda path: {} if path.name=='ltx-2.5-motion-track.official.json' else json.loads(path.read_text()) if path.is_file() else None
                install.download_models(root,comfy,state,vision_repo='Qwen/Qwen3.5-9B')
                ready=install.read_json(state/'models-ready.json')
                self.assertEqual(ready['vision_repo'],'Qwen/Qwen3.5-9B')
                self.assertTrue(all(len(r['sha256'])==64 for r in ready['files']))
                first=ready['signature'];count=len(calls)
                install.download_models(root,comfy,state,vision_repo='Qwen/Qwen3.5-9B')
                self.assertEqual(len(calls),count)
                self.assertEqual(old.read_bytes(),b'old!')
                install.download_models(root,comfy,state,vision_repo='Qwen/Qwen3-VL-8B-Instruct')
                self.assertNotEqual(install.read_json(state/'models-ready.json')['signature'],first)
                self.assertTrue((comfy/'models/Qwen3.5-9B/model.safetensors').is_file())
                for folder in ('Qwen3.5-9B','Qwen3-VL-8B-Instruct'):
                    provenance=install.read_json(state/('vision-'+folder+'.json'))
                    self.assertTrue(all(r['revision']=='a'*40 and len(r['sha256'])==64 for r in provenance['files']))
                count=len(calls)
                install.download_models(root,comfy,state,vision_repo='Qwen/Qwen3.5-9B')
                self.assertEqual(len(calls),count)
                self.assertEqual(install.read_json(state/'models-ready.json')['vision_repo'],'Qwen/Qwen3.5-9B')

    def test_new_install_defaults_to_35_and_legacy_install_keeps_its_choice(self):
        self.assertEqual(install.select_vision_repo(None,None),'Qwen/Qwen3.5-9B')
        legacy={'files':[{'repo':'Qwen/Qwen3-VL-8B-Instruct'}]}
        self.assertEqual(install.select_vision_repo(None,legacy),'Qwen/Qwen3-VL-8B-Instruct')
        self.assertEqual(install.select_vision_repo('Qwen/Qwen3.5-9B',legacy),'Qwen/Qwen3.5-9B')
        with self.assertRaises(ValueError):
            install.select_vision_repo('../../outside',None)
