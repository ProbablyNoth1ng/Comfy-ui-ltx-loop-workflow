"""Real-media acceptance tests for the uploaded Upscale source."""
import importlib
import importlib.util
import errno
import json
import shutil
import subprocess
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image
from comfy_ltx_loop.candidates import finish_candidate, load_handle
from comfy_ltx_loop.project import sha
from comfy_ltx_loop.staged_comfy import ComfyLTXLoopSavedCandidate


def ffmpeg(*args):
    subprocess.run(['ffmpeg', '-v', 'error', '-y', *map(str, args)],
                   check=True, capture_output=True)


def clip(path, size='96x64', fps='8', duration='0.5'):
    ffmpeg('-f', 'lavfi', '-i', f'testsrc2=size={size}:rate={fps}:duration={duration}',
           '-c:v', 'libx264', '-pix_fmt', 'yuv420p', path)
    return path


@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'FFmpeg required')
class VideoTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.inputs, self.outputs = self.root/'input', self.root/'output'

    def api(self):
        self.assertIsNotNone(importlib.util.find_spec('comfy_ltx_loop.videos'),
                             'Uploaded video storage/import API is missing')
        return importlib.import_module('comfy_ltx_loop.videos')

    def store(self, source, filename=None):
        api = self.api()
        # Same finalization as HTTP ingestion, after the streamed file is closed.
        return api.store_video(source, filename or source.name, self.inputs)

    def test_uploads_have_unique_ids_even_for_same_filename_and_reject_paths(self):
        source = clip(self.root/'source.mp4')
        first = self.store(source, 'my video.mp4')
        second = self.store(source, 'my video.mp4')
        self.assertNotEqual(first['id'], second['id'])
        self.assertEqual(first['filename'], 'my video.mp4')
        self.assertEqual(first['sha256'], sha(source))
        self.assertEqual(len(self.api().list_videos(self.inputs)), 2)
        for bad in ('../escape.mp4', '/abs.mp4', r'C:\clip.mp4', r'..\clip.mp4', 'clip.exe'):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                self.store(source, bad)
        for bad in ('../escape', '/abs', r'..\clip', first['id']+'/original.mp4'):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                self.api().load_video(self.inputs, bad)

    def test_corrupt_image_and_audio_only_files_are_rejected(self):
        bad = self.root/'bad.mp4'; bad.write_bytes(b'not a video')
        image = self.root/'image.mp4'; Image.new('RGB', (32, 32)).save(image, format='PNG')
        audio = self.root/'audio.mp4'
        ffmpeg('-f', 'lavfi', '-i', 'sine=duration=0.1', '-c:a', 'aac', audio)
        for source in (bad, image, audio):
            with self.subTest(source=source), self.assertRaisesRegex(ValueError, 'video|decode'):
                self.store(source)
        self.assertEqual(self.api().list_videos(self.inputs), [])

    def test_fps_fallback_and_error_for_missing_rates(self):
        api = self.api()
        self.assertEqual(api.video_fps({'avg_frame_rate':'30000/1001','r_frame_rate':'30/1'}),
                         '30000/1001')
        self.assertEqual(api.video_fps({'avg_frame_rate':'0/0','r_frame_rate':'24000/1001'}),
                         '24000/1001')
        for value in ('0/0', '-5', 'NaN', '0'):
            with self.assertRaisesRegex(ValueError, 'FPS|frame rate'):
                api.video_fps({'avg_frame_rate':value, 'r_frame_rate':'0/0'})

    def test_unknown_sample_aspect_ratio_uses_square_pixels(self):
        api = self.api()
        source = clip(self.root/'unknown-sar.mp4')
        run = api.run_media
        def unknown_sar(command, **kwargs):
            result = run(command, **kwargs)
            if '-show_streams' in command:
                data = json.loads(result.stdout)
                data['streams'][0]['sample_aspect_ratio'] = 'N/A'
                result.stdout = json.dumps(data)
            return result
        with patch('comfy_ltx_loop.videos.run_media', side_effect=unknown_sar):
            meta = self.store(source)
        self.assertEqual(meta['dimensions'], [96,64])

    def test_posix_cache_publish_race_reuses_the_completed_winner(self):
        api = self.api()
        meta = self.store(clip(self.root/'race.mp4'))
        rename = Path.rename
        def other_executor_won(stage, destination):
            if stage.name.startswith('.import-'):
                shutil.copytree(stage, destination)
                raise OSError(errno.ENOTEMPTY, 'Directory not empty')
            return rename(stage, destination)
        with patch.object(Path, 'rename', other_executor_won):
            handle = api.import_video(self.inputs, meta['id'], self.outputs)
        self.assertEqual(handle['frame_count'], 4)
        self.assertEqual(load_handle(handle['record'], self.outputs)['frame_count'], 4)

    def test_import_keeps_all_frames_fractional_fps_and_reuses_completed_source_hash(self):
        source = clip(self.root/'source.mp4', fps='30000/1001', duration='0.2')
        meta = self.store(source)
        before = source.read_bytes()
        handle = self.api().import_video(self.inputs, meta['id'], self.outputs)
        self.assertEqual(handle['kind'], 'imported_video')
        self.assertEqual(handle['fps'], '30000/1001')
        self.assertEqual(handle['frame_count'], 6)
        self.assertEqual(handle['source']['sha256'], sha(source))
        for key in ('seed', 'motion_plan', 'generation_settings'):
            self.assertNotIn(key, handle)
        self.assertEqual(load_handle(handle['record'], self.outputs)['frame_count'], 6)
        # Compare PNGs against an independent direct, unnormalized decode.
        expected = self.root/'expected'; expected.mkdir()
        ffmpeg('-i', source, '-fps_mode', 'passthrough', '-start_number', '0', expected/'%06d.png')
        for frame in sorted(expected.glob('*.png')):
            with Image.open(frame) as a, Image.open(Path(handle['directory'])/'frames'/frame.name) as b:
                self.assertEqual(a.tobytes(), b.tobytes())
        duplicate = self.store(source, 'other.mp4')
        with patch('comfy_ltx_loop.videos.decode_video', side_effect=AssertionError('decoded twice')):
            again = self.api().import_video(self.inputs, duplicate['id'], self.outputs)
        self.assertEqual(again['record'], handle['record'])
        self.assertEqual(source.read_bytes(), before)

    def test_portrait_rotation_sar_near_widescreen_long_and_single_frame(self):
        rotated = clip(self.root/'rotate-base.mp4', size='96x64')
        ffmpeg('-display_rotation', '90', '-i', rotated, '-c', 'copy', self.root/'rotated.mp4')
        anamorphic = clip(self.root/'sar-base.mp4', size='96x64')
        ffmpeg('-i', anamorphic, '-vf', 'setsar=2', self.root/'sar.mp4')
        cases = [
            (clip(self.root/'portrait.mp4', size='64x96'), (64,96), 4),
            (self.root/'rotated.mp4', (64,96), 4),
            (self.root/'sar.mp4', (192,64), 4),
            (clip(self.root/'wide.mp4', size='258x144'), (258,144), 4),
            (clip(self.root/'long.mp4', fps='2', duration='7.5'), (96,64), 15),
            (clip(self.root/'short.mp4', fps='24', duration='0.01'), (96,64), 1),
        ]
        for source, size, count in cases:
            with self.subTest(source=source):
                meta = self.store(source)
                handle = self.api().import_video(self.inputs, meta['id'], self.outputs)
                self.assertEqual(tuple(handle['dimensions']), size)
                self.assertEqual(handle['frame_count'], count)
                self.assertEqual(len(list((Path(handle['directory'])/'frames').glob('*.png'))), count)
                self.assertAlmostEqual(float(handle['duration']), count/float(Fraction(handle['fps'])))

    def test_variable_fps_duration_is_within_one_normalized_frame(self):
        source = self.root/'vfr.mp4'
        ffmpeg('-f','lavfi','-i','testsrc2=size=96x64:rate=10:duration=2',
               '-vf', "select='if(lt(t,1),1,not(mod(n,3)))'", '-fps_mode','vfr', source)
        meta = self.store(source)
        handle = self.api().import_video(self.inputs, meta['id'], self.outputs)
        self.assertLessEqual(abs(float(handle['duration'])-meta['duration']),
                             1/float(Fraction(handle['fps'])))
        self.assertTrue(meta['normalization_warning'])
        decoded = self.root/'vfr-original'; decoded.mkdir()
        ffmpeg('-i', source, '-fps_mode','passthrough','-start_number','0', decoded/'%06d.png')
        identities = {}
        for index, path in enumerate(sorted(decoded.glob('*.png'))):
            with Image.open(path) as frame: identities[frame.tobytes()] = index
        order = []
        for path in sorted((Path(handle['directory'])/'frames').glob('*.png')):
            with Image.open(path) as frame: order.append(identities[frame.tobytes()])
        self.assertEqual(order, sorted(order))
        self.assertEqual((order[0], order[-1]), (0, len(identities)-1))
        self.assertLess(len(set(order)), len(order))  # VFR normalization repeats frames.

    def test_cancellation_during_frame_hashing_does_not_publish_finish(self):
        from comfy_ltx_loop import candidates
        meta = self.store(clip(self.root/'cancel.mp4'))
        handle = self.api().import_video(self.inputs, meta['id'], self.outputs)
        interrupted = False
        original_sha = candidates.sha
        def interrupt_during_hash(path):
            nonlocal interrupted
            result = original_sha(path)
            if Path(path).parent.parent.name.startswith('finish-'):
                interrupted = True
            return result
        def check():
            if interrupted: raise RuntimeError('cancelled during hashing')
        with patch('comfy_ltx_loop.candidates.sha', side_effect=interrupt_during_hash), \
             patch('comfy_ltx_loop.candidates.check_interrupted', side_effect=check):
            with self.assertRaisesRegex(RuntimeError, 'cancelled during hashing'):
                finish_candidate(handle, self.outputs, '1080p', method='fast')
        self.assertEqual(list(self.outputs.glob('finish-*/record.json')), [])

    def test_supported_containers_and_unspecified_sar(self):
        api = self.api()
        for extension, codec in [('mov','libx264'),('mkv','ffv1'),('avi','mpeg4'),('webm','libvpx-vp9')]:
            with self.subTest(extension=extension):
                source = self.root/('container.'+extension)
                ffmpeg('-f','lavfi','-i','testsrc2=size=96x64:rate=8:duration=0.25',
                       '-vf','setsar=0','-c:v',codec,source)
                meta = self.store(source)
                handle = api.import_video(self.inputs, meta['id'], self.outputs)
                self.assertEqual(handle['dimensions'], [96,64])
                self.assertEqual(handle['frame_count'], 2)

    def test_finish_import_preserves_near_widescreen_fractional_rate_silence_and_original(self):
        source = self.root/'audio-video.mp4'
        ffmpeg('-f','lavfi','-i','testsrc2=size=258x144:rate=30000/1001:duration=0.07',
               '-f','lavfi','-i','sine=duration=0.07','-c:v','libx264','-c:a','aac',source)
        meta = self.store(source)
        handle = self.api().import_video(self.inputs, meta['id'], self.outputs)
        original = Path(handle['record']).read_bytes()
        final = finish_candidate(handle, self.outputs, '1080p', method='fast')
        self.assertEqual(final['dimensions'], [1936,1080])
        self.assertEqual(final['frame_count'], handle['frame_count'])
        self.assertEqual(final['fps'], '30000/1001')
        self.assertEqual(final['source_kind'], 'imported_video')
        self.assertNotIn('seed', final)
        streams = json.loads(subprocess.run(['ffprobe','-v','error','-show_streams','-of','json',
            str(Path(final['directory'])/'loop.mp4')], check=True, capture_output=True, text=True).stdout)['streams']
        self.assertEqual([s['codec_type'] for s in streams], ['video'])
        self.assertEqual(Fraction(streams[0]['avg_frame_rate']), Fraction(30000,1001))
        self.assertEqual(Path(handle['record']).read_bytes(), original)
        self.assertEqual(sha(source), meta['sha256'])
        # Both AI policies must also avoid the generated-candidate crop.
        sizes = []
        def enhance(image, target):
            sizes.append(image.size)
            return image.resize(target)
        for method in ('balanced_ai', 'original_ai'):
            with patch('comfy_ltx_loop.candidates.encode'):
                result = finish_candidate(handle, self.outputs, '1080p', enhancer=enhance, method=method)
            self.assertEqual(result['dimensions'], [1936,1080])
        self.assertEqual(set(sizes), {(258,144)})

    def test_failed_import_and_finish_are_never_published_or_reused(self):
        source = clip(self.root/'source.mp4')
        meta = self.store(source)
        with patch('comfy_ltx_loop.videos.decode_video', side_effect=RuntimeError('cancelled')):
            with self.assertRaises(RuntimeError):
                self.api().import_video(self.inputs, meta['id'], self.outputs)
        self.assertEqual(list(self.outputs.glob('**/record.json')), [])
        handle = self.api().import_video(self.inputs, meta['id'], self.outputs)
        with patch('comfy_ltx_loop.candidates.encode', side_effect=RuntimeError('cancelled')):
            with self.assertRaises(RuntimeError):
                finish_candidate(handle, self.outputs, '1080p', method='fast')
        self.assertEqual(list(self.outputs.glob('finish-*/record.json')), [])

    def test_node_preserves_legacy_default_and_validates_only_active_source(self):
        folder_paths = SimpleNamespace(get_input_directory=lambda:str(self.inputs))
        with patch.dict('sys.modules', {'folder_paths':folder_paths}), \
             patch('comfy_ltx_loop.staged_comfy.output_root', return_value=self.outputs):
            inputs = ComfyLTXLoopSavedCandidate.INPUT_TYPES()
            self.assertEqual(list(inputs['required']), ['candidate'])
            self.assertEqual(list(inputs.get('optional', {})), ['source_mode', 'uploaded_video'])
            self.assertEqual(ComfyLTXLoopSavedCandidate.RETURN_TYPES, ('RENDER_HANDLE',))
            meta = self.store(clip(self.root/'source.mp4'))
            handle = ComfyLTXLoopSavedCandidate().execute('Select a saved candidate',
                source_mode='uploaded_video', uploaded_video=meta['id'])[0]
            self.assertEqual(handle['kind'], 'imported_video')
            self.assertIs(ComfyLTXLoopSavedCandidate.VALIDATE_INPUTS(
                candidate='deleted', source_mode='uploaded_video', uploaded_video=meta['id']), True)
            with patch('comfy_ltx_loop.staged_comfy.load_handle', return_value={'legacy':True}) as load:
                self.assertEqual(ComfyLTXLoopSavedCandidate().execute('candidate-old/record.json'), ({'legacy':True},))
                self.assertTrue(load.called)
