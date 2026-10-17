"""Install the saved Comfy LTX Loop workflow in an initialized ComfyUI environment."""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import tempfile
import time
from urllib.parse import urlparse
from urllib.request import urlopen


QWEN_REPO = 'Qwen/Qwen3.5-9B'
VISION_REPOS = (QWEN_REPO, 'Qwen/Qwen3-VL-8B-Instruct')
LIGHT_VISION_REPO = 'Qwen/Qwen3-VL-2B-Instruct'
# ComfyUI v0.38.0 includes the LTX-2.5 diffusion video VAE loader.
COMFY_COMPAT_REVISION = '6b747c0428c343e1417219641db93a4fb7cb69ae'
UPSCALER = 'upscale_models/realesr-animevideov3.pth'
UPSCALER_URL = ('https://github.com/xinntao/Real-ESRGAN/releases/download/'
                'v0.2.5.0/realesr-animevideov3.pth')


def relative_path(value):
    path = PurePosixPath(value)
    if not value or path.is_absolute() or '..' in path.parts or '\\' in value:
        raise ValueError('Unsafe model path')
    return path


def model_assets(workflow):
    assets = {}

    def visit(value):
        if isinstance(value, dict):
            for item in value.get('models', []):
                url = urlparse(item['url'])
                parts = url.path.strip('/').split('/')
                if url.scheme != 'https' or url.netloc != 'huggingface.co' or len(parts) < 5 or parts[2] != 'resolve':
                    raise ValueError('Expected a Hugging Face model URL')
                filename = str(relative_path('/'.join(parts[4:])))
                name = str(relative_path(item['name']))
                if '/' in name or PurePosixPath(filename).name != name:
                    raise ValueError('Model filename does not match URL')
                target = str(relative_path(item['directory']) / name)
                source_parent = PurePosixPath(filename).parent
                target_parent = PurePosixPath(target).parent
                if source_parent == target_parent:
                    local_dir = '.'
                elif str(source_parent) == '.':
                    local_dir = str(target_parent)
                else:
                    raise ValueError('Unsupported model directory mapping')
                asset = dict(repo='/'.join(parts[:2]), revision=parts[3], filename=filename,
                             target=target, local_dir=local_dir)
                if target in assets and assets[target] != asset:
                    raise ValueError('Conflicting sources for model: ' + target)
                assets[target] = asset
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(workflow)
    if not assets:
        raise ValueError('Workflow has no model metadata')
    return sorted(assets.values(), key=lambda a: a['target'])


def files_complete(root, records):
    return bool(records) and all(
        (root / relative_path(r['target'])).is_file()
        and (root / r['target']).stat().st_size == r['size'] > 0 for r in records)


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8')) if path.is_file() else None


def write_json(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)


def sha256(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def select_vision_repo(selection, ready):
    if selection is None and ready:
        selection = ready.get('vision_repo') or next(
            (r['repo'] for r in ready.get('files', []) if r.get('repo') in VISION_REPOS), None)
    selection = selection or QWEN_REPO
    if selection not in VISION_REPOS:
        raise ValueError('Choose a supported vision model: '+', '.join(VISION_REPOS))
    return selection


def model_signature(assets, vision_repo):
    return hashlib.sha256(json.dumps({'assets':assets,'vision_repo':vision_repo}, sort_keys=True).encode()).hexdigest()


def resolve_plan(assets, vision_repo=QWEN_REPO):
    if vision_repo != LIGHT_VISION_REPO:
        vision_repo = select_vision_repo(vision_repo, None)
    from huggingface_hub import HfApi
    api = HfApi()
    repositories = {}
    for repo, revision in sorted({(a['repo'], a['revision']) for a in assets} | {(vision_repo, 'main')}):
        print('Checking model access: ' + repo, flush=True)
        try:
            info = api.model_info(repo, revision=revision, files_metadata=True)
        except Exception as error:
            raise RuntimeError('Cannot access ' + repo + '. Check HF_TOKEN, access terms and network ('
                               + type(error).__name__ + ').') from None
        repositories[repo, revision] = info

    records = []
    for asset in assets:
        info = repositories[asset['repo'], asset['revision']]
        sibling = next((s for s in info.siblings if s.rfilename == asset['filename']), None)
        if sibling is None or not sibling.size:
            raise RuntimeError('Missing model at source: ' + asset['target'])
        records.append(dict(asset, revision=info.sha, size=sibling.size,
                            sha256=getattr(sibling.lfs, 'sha256', None)))
    info = repositories[vision_repo, 'main']
    folder = vision_repo.split('/')[-1]
    qwen_files = [s for s in info.siblings if s.rfilename.endswith(
        ('.json', '.safetensors', '.txt', '.model', '.jinja'))]
    if not any(s.rfilename == 'config.json' for s in qwen_files) or not any(
            s.rfilename.endswith('.safetensors') for s in qwen_files):
        raise RuntimeError('Qwen snapshot has no config or weights')
    for sibling in qwen_files:
        if not sibling.size:
            raise RuntimeError('Qwen file size unavailable: ' + sibling.rfilename)
        records.append(dict(repo=vision_repo, revision=info.sha, filename=sibling.rfilename,
                            target=str(relative_path(folder+'/'+sibling.rfilename)),
                            local_dir=folder, size=sibling.size,
                            sha256=getattr(sibling.lfs, 'sha256', None)))
    return records


def download_records(root, records):
    from huggingface_hub import hf_hub_download
    missing_bytes = sum(r['size'] for r in records if not files_complete(root, [r]))
    if shutil.disk_usage(root).free < missing_bytes + 5 * 1024 ** 3:
        raise RuntimeError(f'Insufficient disk space: need about {missing_bytes / 1024**3 + 5:.1f} GiB free.')
    completed = []
    for record in records:
        print('Downloading/checking: ' + record['target'], flush=True)
        destination = root / record['target']
        # Hub's pinned-commit metadata may reuse a local file without a size check.
        force = destination.is_file() and destination.stat().st_size != record['size']
        try:
            path = Path(hf_hub_download(repo_id=record['repo'], filename=record['filename'],
                                       revision=record['revision'], local_dir=root / record['local_dir'],
                                       force_download=force))
        except Exception as error:
            raise RuntimeError('Download failed for ' + record['target']
                               + '. Check HF_TOKEN/access/network and restart to resume ('
                               + type(error).__name__ + ').') from None
        if path.resolve() != (root / record['target']).resolve() or path.stat().st_size != record['size']:
            raise RuntimeError('Incomplete model: ' + record['target'])
        print('Verifying SHA256: ' + record['target'], flush=True)
        digest = sha256(path)
        if record['sha256'] and digest != record['sha256']:
            raise RuntimeError('Model checksum mismatch: ' + record['target'])
        completed.append(dict(record, sha256=digest))
    return completed


def ensure_light_vision(root, state):
    folder = LIGHT_VISION_REPO.split('/')[-1]
    manifest_path = state / ('vision-'+folder+'.json')
    ready = read_json(manifest_path)
    if ready and files_complete(root, ready['files']):
        return
    plan_path = state / ('vision-'+folder+'-plan.json')
    plan = read_json(plan_path)
    if not plan:
        # A completed manifest is also a recovery plan; never resolve main again.
        records = ready['files'] if ready else resolve_plan([], LIGHT_VISION_REPO)
        plan = dict(vision_repo=LIGHT_VISION_REPO, files=records)
        write_json(plan_path, plan)
    completed = download_records(root, plan['files'])
    write_json(manifest_path, dict(vision_repo=LIGHT_VISION_REPO, files=completed))


def download_models(project, comfy, state, vision_repo=None):
    assets = model_assets(read_json(project / 'workflows/ltx-2.5-motion-track.official.json'))
    root = comfy / 'models'
    root.mkdir(exist_ok=True)
    ready = read_json(state / 'models-ready.json')
    if ready:
        # Retain comparison provenance before replacing the active manifest.
        previous_repo = select_vision_repo(None, ready)
        legacy_signature = hashlib.sha256(json.dumps(assets, sort_keys=True).encode()).hexdigest()
        if ready['signature'] == legacy_signature:
            # The old manifest already pins these exact assets; do not resolve main again.
            ready = dict(ready, signature=model_signature(assets, previous_repo), vision_repo=previous_repo)
            write_json(state / 'models-ready.json', ready)
        write_json(state / ('models-'+previous_repo.split('/')[-1]+'-ready.json'), ready)
        previous_files = [r for r in ready.get('files', []) if r.get('repo') == previous_repo]
        if previous_files:
            write_json(state / ('vision-'+previous_repo.split('/')[-1]+'.json'),
                       dict(vision_repo=previous_repo, files=previous_files))
    vision_repo = select_vision_repo(vision_repo, ready)
    signature = model_signature(assets, vision_repo)
    cached = read_json(state / ('models-'+vision_repo.split('/')[-1]+'-ready.json'))
    if cached and cached['signature'] == signature:
        ready = cached
    if ready and ready['signature'] == signature and files_complete(root, ready['files']):
        upscaler = next(r for r in ready['files'] if r['target'] == UPSCALER)
        if sha256(root / UPSCALER) == upscaler['sha256']:
            ensure_light_vision(root, state)
            write_json(state / 'models-ready.json', ready)
            print('Models already downloaded; using existing files on this disk.', flush=True)
            return
    plan = read_json(state / 'models-plan.json')
    if not plan or plan['signature'] != signature:
        records = ([r for r in ready['files'] if r['target'] != UPSCALER]
                   if ready and ready['signature'] == signature else resolve_plan(assets, vision_repo))
        plan = dict(signature=signature, vision_repo=vision_repo, files=records)
        write_json(state / 'models-plan.json', plan)
    completed = download_records(root, plan['files'])
    upscaler = root / UPSCALER
    upscaler.parent.mkdir(exist_ok=True)
    if not ready or not files_complete(root, [r for r in ready['files'] if r['target'] == UPSCALER]) or (
            sha256(upscaler) != next(r['sha256'] for r in ready['files'] if r['target'] == UPSCALER)):
        temporary = upscaler.with_suffix('.part.pth')
        for attempt in range(3):
            try:
                with urlopen(UPSCALER_URL, timeout=120) as response, temporary.open('wb') as stream:
                    if 'text/html' in response.headers.get('Content-Type', ''):
                        raise RuntimeError('Upscale download returned HTML')
                    shutil.copyfileobj(response, stream)
                # Validate the actual checkpoint before accepting it as complete.
                from spandrel import ModelLoader
                ModelLoader().load_from_file(str(temporary))
                temporary.replace(upscaler)
                break
            except Exception:
                if attempt == 2:
                    raise RuntimeError('Real-ESRGAN download/validation failed. Restart to retry.') from None
                time.sleep(3)
    completed.append(dict(target=UPSCALER, size=upscaler.stat().st_size, sha256=sha256(upscaler)))
    ensure_light_vision(root, state)
    completed_manifest = dict(signature=signature, vision_repo=vision_repo, files=completed)
    write_json(state / 'models-ready.json', completed_manifest)
    write_json(state / ('models-'+vision_repo.split('/')[-1]+'-ready.json'), completed_manifest)
    write_json(state / ('vision-'+vision_repo.split('/')[-1]+'.json'),
               dict(vision_repo=vision_repo, files=[r for r in completed if r.get('repo') == vision_repo]))


def clone_once(repo, destination, revision=None):
    if destination.exists():
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=destination.name + '.installing-', dir=destination.parent))
    subprocess.run(['git', 'clone', '--depth', '1', repo, str(temporary)], check=True)
    subprocess.run(['git', '-C', str(temporary), 'rev-parse', '--verify', 'HEAD'], check=True)
    if revision:
        subprocess.run(['git', '-C', str(temporary), 'fetch', '--depth', '1', 'origin', revision], check=True)
        subprocess.run(['git', '-C', str(temporary), 'checkout', '--detach', 'FETCH_HEAD'], check=True)
    temporary.rename(destination)


def ensure_comfy_compatibility(comfy):
    def supports_diffusion_vae():
        source = comfy / 'comfy/sd.py'
        decoder = comfy / 'comfy/ldm/lightricks/vae/na_diffusion_decoder.py'
        if not source.is_file() or not decoder.is_file():
            return False
        loader = source.read_text(encoding='utf-8')
        return ('"decoder.conv_in_x_t.weight" in sd' in loader
                and 'na_diffusion_decoder.CausalDiffusionVAE(' in loader)

    if supports_diffusion_vae():
        return
    git = ['git', '-C', str(comfy)]
    changes = subprocess.check_output(git + ['status', '--porcelain', '--untracked-files=no'])
    if changes.strip():
        raise RuntimeError('ComfyUI lacks the LTX-2.5 diffusion VAE loader and has local changes. '
                           'Save those changes and update ComfyUI before restarting setup.')
    previous = subprocess.check_output(git + ['rev-parse', 'HEAD'], text=True).strip()
    print('Updating ComfyUI to v0.38.0 for LTX-2.5 diffusion VAE support.', flush=True)
    subprocess.run(git + ['fetch', '--depth', '1', 'origin', COMFY_COMPAT_REVISION], check=True)
    subprocess.run(git + ['checkout', '--detach', 'FETCH_HEAD'], check=True)
    if not supports_diffusion_vae():
        subprocess.run(git + ['checkout', '--detach', previous], check=True)
        raise RuntimeError('ComfyUI update lacks LTX-2.5 diffusion VAE support; previous revision restored.')


def install_workflows(project, destination, vision_repo):
    vision_repo = select_vision_repo(vision_repo, None)
    destination.mkdir(parents=True, exist_ok=True)
    for name in ('comfy-ltx-loop-motion.json', 'ltx-2.5-motion-track.official.json'):
        target = destination / name
        if target.exists():
            continue
        if name == 'comfy-ltx-loop-motion.json':
            workflow = read_json(project / 'workflows' / name)
            for node in workflow['nodes']:
                if node['type'] == 'ComfyLTXLoopMotionEditor':
                    node['widgets_values'][7:9] = ['models/'+vision_repo.split('/')[-1],
                        'local Qwen3.5' if vision_repo == QWEN_REPO else 'local Qwen']
            write_json(target, workflow)
        else:
            shutil.copy2(project / 'workflows' / name, target)


def install(project, comfy, vision_repo=None):
    vision_args = ['--vision-model', vision_repo] if vision_repo else []
    if sys.version_info < (3, 12):
        raise RuntimeError('Use Python 3.12+ from the ComfyUI environment.')
    if not (comfy / 'main.py').is_file() or not (project / 'pyproject.toml').is_file():
        raise RuntimeError('ComfyUI or Comfy LTX Loop installation is missing.')
    if Path(sys.prefix).resolve() == Path(sys.base_prefix).resolve():
        candidates = [comfy / name / 'bin/python' for name in ('.venv-cu128', '.venv-cu130', '.venv')]
        python = next((p for p in candidates if p.is_file()), None)
        if python is None:
            raise RuntimeError('Wait for the official image to initialize its ComfyUI virtual environment.')
        os.execv(str(python), [str(python), __file__, '--project-root', str(project), '--comfy-root', str(comfy), *vision_args])
    state = comfy / '.comfy-ltx-loop-install'
    state.mkdir(exist_ok=True)
    ensure_comfy_compatibility(comfy)
    for command in ('ffmpeg', 'ffprobe'):
        if not shutil.which(command):
            subprocess.run(['apt-get', 'update'], check=True)
            subprocess.run(['apt-get', 'install', '-y', '--no-install-recommends', 'ffmpeg'], check=True)
            break
    import torch
    if not torch.cuda.is_available():
        raise RuntimeError('CUDA is unavailable. Check host driver compatibility with this CUDA 13 image.')
    print('GPU: ' + torch.cuda.get_device_name(0) + '; Torch ' + torch.__version__, flush=True)
    ltx = comfy / 'custom_nodes/ComfyUI-LTXVideo'
    clone_once('https://github.com/Lightricks/ComfyUI-LTXVideo.git', ltx, os.environ.get('LTX_REVISION'))
    constraints = state / 'torch-constraints.txt'
    versions = {p: importlib.metadata.version(p) for p in ('torch', 'torchvision', 'torchaudio')}
    constraints.write_text(''.join(f'{p}=={v}\n' for p, v in versions.items()), encoding='utf-8')
    fingerprint = hashlib.sha256()
    for path in (project / 'pyproject.toml', comfy / 'requirements.txt', ltx / 'requirements.txt'):
        fingerprint.update(path.read_bytes())
    fingerprint.update((str(sys.version_info[:3]) + json.dumps(versions, sort_keys=True)).encode())
    fingerprint.update(str(project).encode())
    fingerprint.update(subprocess.check_output(['git', '-C', str(comfy), 'rev-parse', 'HEAD']))
    fingerprint.update(subprocess.check_output(['git', '-C', str(ltx), 'rev-parse', 'HEAD']))
    expected = fingerprint.hexdigest()
    installed = read_json(state / 'dependencies.json')
    changed = not installed or installed['fingerprint'] != expected
    if changed:
        print('Installing Comfy LTX Loop and LTX dependencies in ' + sys.prefix, flush=True)
        subprocess.run([sys.executable, '-m', 'pip', 'install', '-c', str(constraints),
                        '-r', str(comfy / 'requirements.txt'), '-r', str(ltx / 'requirements.txt'),
                        '-e', str(project) + '[vision]'], check=True)
    subprocess.run([sys.executable, '-c', 'import numpy, PIL, scipy, accelerate, spandrel; '
                    'from transformers import AutoProcessor, Qwen3VLForConditionalGeneration, Qwen3_5ForConditionalGeneration; '
                    'import comfy_ltx_loop.comfy'], cwd=comfy, check=True)
    write_json(state / 'dependencies.json', dict(fingerprint=expected, torch=versions))
    if changed:
        # pip may have replaced packages already imported by torch in this process.
        os.execv(sys.executable, [sys.executable, __file__, '--project-root', str(project),
                                '--comfy-root', str(comfy), *vision_args])
    link = comfy / 'custom_nodes/comfy_ltx_loop'
    source = project / 'comfy_nodes/comfy_ltx_loop'
    if link.is_symlink():
        if link.resolve() != source.resolve():
            raise RuntimeError('Existing Comfy LTX Loop node points to another project.')
    elif link.exists():
        raise RuntimeError('Existing comfy_ltx_loop custom node is not this project symlink.')
    else:
        link.symlink_to(source, target_is_directory=True)
    download_models(project, comfy, state, vision_repo)
    install_workflows(project, comfy / 'user/default/workflows',
                      select_vision_repo(vision_repo, read_json(state / 'models-ready.json')))
    (state / 'packages.txt').write_bytes(subprocess.check_output([sys.executable, '-m', 'pip', 'freeze']))
    print('COMFY_LTX_LOOP INSTALLED. Starting ComfyUI; GPU rendering still needs qualification.', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--comfy-root', default='/workspace/runpod-slim/ComfyUI')
    parser.add_argument('--project-root', default='/workspace/comfy-ltx-loop')
    parser.add_argument('--vision-model', choices=VISION_REPOS, default=os.environ.get('COMFY_LTX_LOOP_VISION_MODEL'),
                        help='Vision snapshot (new installs default to Qwen3.5; existing installs keep their selection)')
    args = parser.parse_args()
    os.environ.setdefault('HF_HOME', '/workspace/.cache/huggingface')
    try:
        install(Path(args.project_root).resolve(), Path(args.comfy_root).resolve(), args.vision_model)
    except (RuntimeError, ValueError, OSError, subprocess.CalledProcessError) as error:
        print('COMFY_LTX_LOOP SETUP FAILED: ' + str(error), file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
