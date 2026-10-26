"""Same-origin ComfyUI review and persistent-candidate browsing."""
from pathlib import Path

from .motion import review_plan
from .staged_comfy import output_root, input_root
from .candidates import list_candidates
from .videos import list_videos, receive_video


def register_routes():
    from aiohttp import web
    from server import PromptServer

    @PromptServer.instance.routes.post('/comfy-ltx-loop/review')
    async def review(request):
        try:
            return web.json_response(review_plan(await request.json()))
        except (ValueError, KeyError, TypeError, IndexError) as error:
            return web.json_response({'error':str(error)},status=400)

    @PromptServer.instance.routes.get('/comfy-ltx-loop/candidates')
    async def candidates(request):
        return web.json_response(list_candidates(output_root()))

    @PromptServer.instance.routes.get('/comfy-ltx-loop/videos')
    async def videos(request):
        return web.json_response(list_videos(input_root()))

    @PromptServer.instance.routes.post('/comfy-ltx-loop/videos')
    async def upload_video(request):
        try:
            return web.json_response(await receive_video(request, input_root()))
        except web.HTTPRequestEntityTooLarge:
            return web.json_response({'error':'Video upload exceeds the configured server upload limit'}, status=413)
        except (ValueError, OSError, AssertionError) as error:
            return web.json_response({'error':str(error)}, status=400)

    @PromptServer.instance.routes.get('/comfy-ltx-loop/record')
    async def record(request):
        import json
        path = (output_root()/request.query.get('candidate','')).resolve()
        if not path.is_relative_to(output_root().resolve()) or path.name != 'record.json':
            raise web.HTTPBadRequest(text='Choose a saved candidate')
        try:
            return web.json_response(json.loads(path.read_text(encoding='utf-8')))
        except (OSError,ValueError):
            raise web.HTTPNotFound(text='Candidate record not found')
