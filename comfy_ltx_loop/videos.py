"""Immutable uploaded videos and reusable, disk-backed Upscale imports."""
import asyncio
import errno
import hashlib
import json
import math
import re
import shutil
import tempfile
import uuid
from fractions import Fraction
from pathlib import Path

from PIL import Image

from .candidates import load_handle, save_record
from .media import check_interrupted, run_media
from .project import atomic_json, sha

EXTENSIONS = {'.mp4', '.mov', '.mkv', '.webm', '.avi'}
CONTAINERS = {'mov', 'mp4', 'm4a', '3gp', '3g2', 'mj2', 'matroska', 'webm', 'avi'}


def video_root(input_root):
    return Path(input_root)/'comfy-ltx-loop-videos'


def upload_name(filename):
    if (not isinstance(filename, str) or not filename or
            any(c in filename for c in '/\\:') or
            any(ord(c) < 32 for c in filename) or
            Path(filename).suffix.lower() not in EXTENSIONS):
        raise ValueError('Choose one MP4, MOV, MKV, WebM or AVI video filename without a path')
    return filename


def video_fps(stream):
    for name in ('avg_frame_rate', 'r_frame_rate'):
        try:
            rate = Fraction(stream.get(name, '0/0'))
            if rate > 0:
                return str(rate)
        except (ValueError, ZeroDivisionError, TypeError):
            pass
    raise ValueError('Video has no valid positive FPS (avg_frame_rate or r_frame_rate)')


def probe_video(path):
    result = run_media(['ffprobe', '-v', 'error', '-count_frames', '-show_streams',
                        '-show_format', '-of', 'json', str(path)])
    try:
        data = json.loads(result.stdout)
        formats = set(data.get('format', {}).get('format_name', '').split(','))
        stream = next(s for s in data['streams'] if s.get('codec_type') == 'video'
                      and not s.get('disposition', {}).get('attached_pic'))
        if (not formats.intersection(CONTAINERS) or result.stderr.strip() or
                int(stream.get('nb_read_frames', 0)) < 1):
            raise ValueError('No decodable video frames in a supported video container')
        fps = video_fps(stream)
        width, height = int(stream['width']), int(stream['height'])
        try:
            sar = Fraction(stream.get('sample_aspect_ratio', '1:1').replace(':', '/'))
        except (ValueError, ZeroDivisionError):
            sar = Fraction(1)
        if sar <= 0: sar = Fraction(1)
        # FFmpeg autorotation is applied before user filters; square-pixel scale
        # consequently uses the rotated width/height and corresponding SAR.
        rotation = float(stream.get('tags', {}).get('rotate', 0))
        for side in stream.get('side_data_list', []):
            if 'rotation' in side:
                rotation = float(side['rotation'])
        displayed = [float(width*sar), float(height)]
        if round(rotation) % 180 == 90:
            displayed.reverse()
        # Some VFR muxers report a shorter stream/format duration than the final
        # displayed frame. Read decoded timestamps on disk, never collect frames
        # or per-frame metadata into a Python list.
        with tempfile.TemporaryDirectory() as tmp:
            timeline = Path(tmp)/'timestamps.csv'
            run_media(['ffprobe', '-v', 'error', '-select_streams', str(stream['index']),
                '-show_frames', '-show_entries', 'frame=best_effort_timestamp_time,duration_time',
                '-of', 'csv=p=0', str(path)], stdout_path=timeline)
            start, end = math.inf, -math.inf
            with timeline.open(encoding='utf-8') as timestamps:
                for line in timestamps:
                    try:
                        values = line.strip().split(',')
                        timestamp = float(values[0])
                        period = float(values[1]) if len(values) > 1 and values[1] not in ('', 'N/A') else 1/float(Fraction(fps))
                        if math.isfinite(timestamp) and math.isfinite(period):
                            start, end = min(start, timestamp), max(end, timestamp+period)
                    except ValueError:
                        continue
            duration = end-start
        if not math.isfinite(duration) or duration <= 0:
            raise ValueError('Video has no valid decoded frame timing')
        return {'dimensions':[max(1, round(v)) for v in displayed], 'fps':fps,
                'duration':duration, 'stream_index':int(stream['index']),
                'decoded_frames':int(stream['nb_read_frames']), 'rotation':rotation,
                'normalization_warning':f'Output is normalized to {fps} FPS; variable-rate video may repeat or drop frames.'}
    except (KeyError, StopIteration, TypeError, ZeroDivisionError) as error:
        raise ValueError('File has no decodable video track') from error


def store_video(source, filename, input_root):
    """Finalize a closed local spool; never move or modify the supplied file."""
    filename = upload_name(filename)
    root = video_root(input_root)
    root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.upload-', dir=root) as tmp:
        stage = Path(tmp)
        original = stage/('original'+Path(filename).suffix.lower())
        shutil.copyfile(source, original)
        meta = {'schema':'comfy-ltx-loop-video/1', 'id':uuid.uuid4().hex,
                'filename':filename, 'original':original.name, 'size':original.stat().st_size,
                'sha256':sha(original), **probe_video(original)}
        atomic_json(stage/'metadata.json', meta)
        check_interrupted()
        stage.rename(root/meta['id'])
    return meta


def load_video(input_root, video_id):
    if not isinstance(video_id, str) or not re.fullmatch(r'[a-f0-9]{32}', video_id):
        raise ValueError('Select an uploaded video from the list')
    root = video_root(input_root).resolve()
    directory = (root/video_id).resolve()
    if not directory.is_relative_to(root):
        raise ValueError('Video path is outside the input directory')
    try:
        meta = json.loads((directory/'metadata.json').read_text(encoding='utf-8'))
        name = 'original'+Path(upload_name(meta['filename'])).suffix.lower()
        source = (directory/name).resolve()
        if (meta.get('schema') != 'comfy-ltx-loop-video/1' or meta.get('id') != video_id
                or meta.get('original') != name or not source.is_relative_to(directory)
                or not source.is_file() or source.stat().st_size != meta['size']):
            raise ValueError('Uploaded video metadata or original file is invalid')
        return meta, source
    except (OSError, KeyError, TypeError) as error:
        raise ValueError('Uploaded video is missing; upload it again') from error


def list_videos(input_root):
    records = []
    for path in video_root(input_root).glob('*/metadata.json'):
        try:
            meta, _ = load_video(input_root, path.parent.name)
            records.append((path.stat().st_mtime_ns, meta))
        except (ValueError, OSError):
            continue
    return [meta for _, meta in sorted(records, key=lambda pair:pair[0], reverse=True)]


async def receive_video(request, input_root):
    """Read one multipart video with a limit even when Content-Length is absent."""
    from aiohttp import web
    limit = request.client_max_size
    def check_size(size):
        actual = max(size, getattr(request.content, 'total_bytes', 0))
        if limit and actual > limit:
            raise web.HTTPRequestEntityTooLarge(max_size=limit, actual_size=actual)
    check_size(request.content_length or 0)
    root = video_root(input_root)
    root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.receiving-', dir=root) as tmp:
        reader = await request.multipart()
        part = await reader.next()
        check_size(0)
        if part is None or part.name != 'video' or not part.filename:
            raise ValueError('Upload exactly one file in the video field')
        filename = upload_name(part.filename)
        source = Path(tmp)/'upload'
        size = 0
        with source.open('wb') as out:
            while chunk := await part.read_chunk(size=64*1024):
                size += len(chunk)
                check_size(size)
                out.write(chunk)
        if await reader.next() is not None:
            raise ValueError('Upload exactly one video file at a time')
        check_size(size)
        # FFprobe is synchronous and may scan a long clip. Keep the event loop
        # available; on cancellation wait for the worker before removing its spool.
        task = asyncio.create_task(asyncio.to_thread(store_video, source, filename, input_root))
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            try:
                meta = await task
                shutil.rmtree(root/meta['id'])
            except Exception:
                pass
            raise


def decode_video(source, meta, frames):
    run_media(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-xerror', '-nostdin', '-y',
        '-i', str(source), '-map', f"0:{meta['stream_index']}", '-an',
        '-vf', f"setpts=PTS-STARTPTS,scale=round(iw*sar):ih,setsar=1,fps={meta['fps']}:eof_action=pass",
        '-fps_mode', 'passthrough', '-start_number', '0', '-pix_fmt', 'rgb24',
        str(frames/'%06d.png')])


def import_video(input_root, video_id, output_root):
    meta, source = load_video(input_root, video_id)
    if sha(source) != meta['sha256']:
        raise ValueError('Uploaded original changed; upload it again')
    normalization = {'version':1, 'fps':meta['fps'], 'orientation':'autorotate',
                     'pixels':'square-rgb24', 'timing':'cfr-eof-pass'}
    key = hashlib.sha256((meta['sha256']+json.dumps(normalization, sort_keys=True)).encode()).hexdigest()
    root = Path(output_root)
    root.mkdir(parents=True, exist_ok=True)
    destination = root/('imported-'+key)
    if destination.exists():
        return load_handle(destination/'record.json', root)
    with tempfile.TemporaryDirectory(prefix='.import-', dir=root) as tmp:
        stage = Path(tmp)
        frames = stage/'frames'; frames.mkdir()
        decode_video(source, meta, frames)
        paths = sorted(frames.glob('*.png'))
        if not paths:
            raise ValueError('Video decode produced no frames')
        with Image.open(paths[0]) as image:
            size = list(image.size)
        record = {'kind':'imported_video', 'source':{
            'id':meta['id'], 'filename':meta['filename'], 'sha256':meta['sha256']},
            'normalization':normalization, 'dimensions':size, 'fps':meta['fps'],
            'frame_count':len(paths), 'duration':len(paths)/float(Fraction(meta['fps'])),
            'feedback':[meta['normalization_warning']], 'state':'awaiting_visual_review'}
        save_record(stage, record)
        check_interrupted()
        try:
            stage.rename(destination)
        except OSError as error:
            if error.errno not in (errno.EEXIST, errno.ENOTEMPTY):
                raise
            # Another executor can finish the same immutable import concurrently.
            return load_handle(destination/'record.json', root)
    return load_handle(destination/'record.json', root)
