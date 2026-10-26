import asyncio
import importlib.util
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

try:
    from aiohttp import FormData, web
    from aiohttp.test_utils import TestClient, TestServer
except ImportError:
    web = None

from comfy_ltx_loop.comfy_routes import register_routes


@unittest.skipUnless(web and shutil.which('ffmpeg'), 'aiohttp/FFmpeg required (ComfyUI runtime)')
class VideoRouteTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.inputs = self.root/'input'
        routes = web.RouteTableDef()
        server = SimpleNamespace(PromptServer=SimpleNamespace(instance=SimpleNamespace(routes=routes)))
        folders = SimpleNamespace(get_input_directory=lambda:str(self.inputs),
                                  get_output_directory=lambda:str(self.root/'output'))
        self.patches = patch.dict(sys.modules, {'server':server, 'folder_paths':folders})
        self.patches.start(); self.addCleanup(self.patches.stop)
        register_routes()
        app = web.Application(client_max_size=16384)
        app.add_routes(routes)
        self.client = TestClient(TestServer(app))
        await self.client.start_server(); self.addAsyncCleanup(self.client.close)
        from test_videos import clip
        source = clip(self.root/'source.mp4')
        self.video = source.read_bytes()

    async def upload(self, data=None, filename='video.mp4', extra=False):
        form = FormData(quote_fields=False)
        form.add_field('video', self.video if data is None else data,
                       filename=filename, content_type='application/octet-stream')
        if extra:
            form.add_field('video', self.video, filename='another.mp4')
        return await self.client.post('/comfy-ltx-loop/videos', data=form)

    async def test_api_lists_complete_uploads_with_unique_names(self):
        response = await self.client.get('/comfy-ltx-loop/videos')
        self.assertEqual(response.status, 200, 'GET video inventory route is missing')
        self.assertEqual(await response.json(), [])
        a = await self.upload(); self.assertEqual(a.status, 200, await a.text())
        b = await self.upload(); self.assertEqual(b.status, 200, await b.text())
        first, second = await a.json(), await b.json()
        self.assertNotEqual(first['id'], second['id'])
        response = await self.client.get('/comfy-ltx-loop/videos')
        self.assertEqual({r['id'] for r in await response.json()}, {first['id'], second['id']})

    async def test_bad_uploads_have_clear_errors_and_no_completed_data(self):
        for data, name, extra, status in [(b'bad','bad.mp4',False,400),
                (self.video,'../bad.mp4',False,400), (self.video,'bad.exe',False,400),
                (self.video,'video.mp4',True,400), (b'x'*20000,'big.mp4',False,413)]:
            with self.subTest(name=name, extra=extra):
                response = await self.upload(data, name, extra)
                self.assertEqual(response.status, status, await response.text())
                self.assertTrue((await response.json())['error'])
                self.assertEqual(list(self.inputs.glob('comfy-ltx-loop-videos/*')), [])

    async def test_chunked_body_enforces_server_limit(self):
        boundary = 'video-test'
        async def body():
            yield (f'--{boundary}\r\nContent-Disposition: form-data; name="video"; filename="a.mp4"\r\n'
                   'Content-Type: application/octet-stream\r\n\r\n').encode()
            for _ in range(24):
                yield b'x'*1000
                await asyncio.sleep(0)
            yield f'\r\n--{boundary}--\r\n'.encode()
        response = await self.client.post('/comfy-ltx-loop/videos', data=body(),
            headers={'Content-Type':f'multipart/form-data; boundary={boundary}'})
        self.assertEqual(response.status, 413, await response.text())
        self.assertEqual(list(self.inputs.glob('comfy-ltx-loop-videos/*')), [])

    async def test_interrupted_upload_removes_temporary_file(self):
        self.assertIsNotNone(importlib.util.find_spec('comfy_ltx_loop.videos'),
                             'Streaming video upload implementation is missing')
        from comfy_ltx_loop.videos import receive_video
        class Part:
            filename = 'clip.mp4'
            name = 'video'
            calls = 0
            async def read_chunk(self, size):
                self.calls += 1
                if self.calls == 1: return b'partial'
                raise asyncio.CancelledError()
        class Reader:
            async def next(self): return Part()
        class Request:
            client_max_size = 8192
            content_length = None
            content = SimpleNamespace(total_bytes=0)
            async def multipart(self): return Reader()
        with self.assertRaises(asyncio.CancelledError):
            await receive_video(Request(), self.inputs)
        self.assertEqual(list(self.inputs.glob('comfy-ltx-loop-videos/*')), [])
