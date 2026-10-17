"""Serializable motion plans. Coordinates are normalized to the original image."""
import copy
import hashlib
import json
import math

from .areas import complete_area


def plan_fingerprint(plan):
    data = {'landmarks': plan['landmarks'],
            'strength_reference': plan.get('review', {}).get('strength_reference'),
            'render_mode': plan.get('render_mode', 'free_motion'),
            'motion_areas': plan.get('motion_areas', [])}
    if 'background' in plan:
        data['background'] = plan['background']
    for key in ('use_character_points', 'use_background_points'):
        if key in plan:
            data[key] = plan[key]
    if 'prepared_prompt' in plan.get('analysis', {}):
        data['analysis'] = plan['analysis']
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(',', ':'),
                                    allow_nan=False).encode()).hexdigest()


def legacy_plan_fingerprint(plan):
    data = {k: v for k, v in plan.items() if k not in ('review', 'feedback')}
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(',', ':'),
                                    allow_nan=False).encode()).hexdigest()


def canvas_transform(size, short_side=720):
    width, height = size
    if min(width, height) < 1 or not 256 <= short_side <= 2160:
        raise ValueError('Invalid source size or generation short side')
    scale = short_side / min(size)
    content_w, content_h = round(width * scale), round(height * scale)
    canvas_w, canvas_h = math.ceil(content_w / 64)*64, math.ceil(content_h / 64)*64
    return {'source': list(size), 'canvas': [canvas_w, canvas_h],
            'content': [(canvas_w-content_w)//2, (canvas_h-content_h)//2,
                        content_w, content_h]}


def frame_count(duration, fps):
    count = duration * fps
    if not math.isfinite(count) or count < 8 or abs(count-round(count)) > 1e-6 or round(count) % 8:
        raise ValueError('Duration × FPS must be a positive multiple of 8 (6s × 24 = 144)')
    return round(count) + 1


def returning_path(x, y, amplitude, samples=17):
    # Sinusoidal excursion has zero position and velocity at the cycle boundary.
    path = [{'t': i/(samples-1),
             'x': x + amplitude * (1-math.cos(2*math.pi*i/(samples-1))) / 2,
             'y': y} for i in range(samples)]
    path[-1] = {'t': 1., 'x': x, 'y': y}
    return path


def new_plan(identity, size, prompt, requested, landmarks, duration=6, fps=24,
             strength=.01, short_side=720, feedback=None, analysis=None):
    plan = {'schema': 'comfy-ltx-loop-motion-plan/1', 'source_id': identity,
            'source_size': list(size), 'prompt': prompt, 'requested': requested,
            'duration': float(duration), 'fps': int(fps), 'strength': float(strength),
            'short_side': int(short_side), 'frames': frame_count(duration, fps),
            'transform': canvas_transform(size, short_side), 'landmarks': [],
            'render_mode': 'free_motion', 'motion_areas': [],
            'review': {'state': 'pending'}, 'feedback': feedback or []}
    if analysis is not None:
        plan['analysis'] = copy.deepcopy(analysis)
    for point in landmarks:
        fixed = (point['motion_role'] == 'anchor' if 'motion_role' in point else
                 any(word in point['label'].lower() for word in ('root', 'head', 'shoulder')))
        amplitude = 0 if fixed else min(strength, 1-point['x'])
        stable = point.get('id') or ('point-'+hashlib.sha256(
            json.dumps([point.get('label'), point.get('x'), point.get('y')],
                       separators=(',', ':')).encode()).hexdigest()[:16])
        plan['landmarks'].append({**point, 'id': stable, 'enabled': True, 'strength': 1.,
                                  'path': returning_path(point['x'], point['y'], amplitude)})
    validate_plan(plan)
    return plan


def coordinate(value):
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or not 0 <= value <= 1:
        raise ValueError('Point/path coordinate is outside normalized bounds [0,1]')
    return value


def validate_semantics(point):
    if point.get('motion_role') not in ('move', 'anchor'):
        raise ValueError('Motion role must be move or anchor')
    for field in ('body_part', 'reason'):
        if not isinstance(point.get(field), str) or not point[field].strip():
            raise ValueError(f'Every semantic landmark needs a {field}')


def validate_plan(plan):
    if not isinstance(plan, dict) or plan.get('schema') != 'comfy-ltx-loop-motion-plan/1':
        raise ValueError('Invalid motion plan; Prepare or place points manually')
    if plan['frames'] != frame_count(plan['duration'], plan['fps']):
        raise ValueError('Motion plan timing changed; prepare and review again')
    if plan['transform'] != canvas_transform(plan['source_size'], plan['short_side']):
        raise ValueError('Recorded image transform changed; prepare and review again')
    if not 0 <= plan['strength'] <= .1 or not isinstance(plan['landmarks'], list):
        raise ValueError('Invalid motion strength or landmark list')
    plan.setdefault('render_mode', 'free_motion')
    plan.setdefault('motion_areas', [])
    if plan['render_mode'] not in ('free_motion', 'only_pointed_parts'):
        raise ValueError('Invalid render mode')
    if not isinstance(plan['motion_areas'], list):
        raise ValueError('Invalid motion areas')
    if any(not isinstance(plan[key], bool) for key in ('use_character_points', 'use_background_points')
           if key in plan):
        raise ValueError('Invalid point group selection')
    background = plan.get('background')
    if background is not None and (not isinstance(background, dict) or
            not isinstance(background.get('enabled'), bool) or
            not isinstance(background.get('prompt'), str) or
            background.get('preparation') not in ('model', 'manual')):
        raise ValueError('Invalid background settings')
    ids = set()
    for index, point in enumerate(plan['landmarks']):
        if point.get('group', 'character') not in ('character', 'background'):
            raise ValueError('Invalid landmark group')
        if any(field in point for field in ('motion_role', 'body_part', 'reason')):
            validate_semantics(point)
        if not isinstance(point.get('label'), str) or not point['label'].strip():
            raise ValueError('Every landmark needs a label')
        point.setdefault('id', 'point-'+hashlib.sha256(json.dumps(
            [point['label'], point.get('x'), point.get('y'), index], separators=(',', ':')).encode()
        ).hexdigest()[:16])
        if not isinstance(point['id'], str) or not point['id']:
            raise ValueError('Every landmark needs a stable unique id')
        ids.add(point['id'])
        coordinate(point['x']); coordinate(point['y'])
        if not isinstance(point.get('enabled'), bool) or not 0 <= point['strength'] <= 2:
            raise ValueError('Invalid point enabled state or strength')
        path = point['path']
        if len(path) < 2 or path[0]['t'] != 0 or path[-1]['t'] != 1:
            raise ValueError('Each trajectory must cover timing 0 through 1')
        previous = -1
        for key in path:
            coordinate(key['x']); coordinate(key['y']); coordinate(key['t'])
            if key['t'] <= previous:
                raise ValueError('Path times must increase')
            previous = key['t']
            coordinate(point['x'] + (key['x']-point['x'])*point['strength'])
            coordinate(point['y'] + (key['y']-point['y'])*point['strength'])
            if point.get('motion_role') == 'anchor' and any(
                    abs(key[axis]-point[axis]) > 1e-8 for axis in ('x', 'y')):
                raise ValueError('Anchor paths must stay stationary; change the role to move to edit motion')
        if any(abs(path[0][axis]-point[axis]) > 1e-8 or
               abs(path[-1][axis]-point[axis]) > 1e-8 for axis in ('x','y')):
            raise ValueError('Returning paths must start and end at their landmark')
    for area in plan['motion_areas']:
        if not isinstance(area, dict) or area.get('point_id') not in ids:
            raise ValueError('Invalid motion area')
        mask = area.get('mask')
        if not isinstance(mask, list) or len(mask) != plan['source_size'][1] or any(
                not isinstance(row, list) or len(row) != plan['source_size'][0] or any(
                    isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 255
                    for value in row) for row in mask):
            raise ValueError('Invalid motion area mask')
    return plan


def active_point(plan, point):
    if not point['enabled']:
        return False
    if point.get('group', 'character') == 'background':
        return (plan.get('use_background_points', True) and
                plan.get('background', {}).get('enabled', False))
    return plan.get('use_character_points', True)


def active_moving_point(plan, point):
    """A strict area can be granted only by an enabled non-stationary active point."""
    return active_point(plan, point) and (point.get('motion_role') == 'move' or
        (point.get('motion_role') is None and any(
            abs(key[axis]-point[axis]) > 1e-8 for key in point['path'] for axis in ('x', 'y'))))


def strict_mask(plan):
    """Union source-coordinate areas authorized by currently moving points."""
    validate_plan(plan)
    width, height = plan['source_size']
    result = [[0] * width for _ in range(height)]
    allowed = {point['id'] for point in plan['landmarks'] if active_moving_point(plan, point)}
    for area in plan.get('motion_areas', []):
        if area['point_id'] in allowed:
            for y, row in enumerate(area['mask']):
                for x, value in enumerate(row):
                    result[y][x] = max(result[y][x], value)
    return result


def check_motion_areas(plan):
    if plan.get('render_mode', 'free_motion') != 'only_pointed_parts':
        return
    active = {point['id'] for point in plan['landmarks'] if active_moving_point(plan, point)}
    if len(active) != sum(active_moving_point(plan, point) for point in plan['landmarks']):
        raise ValueError('Update motion areas after assigning unique point ids')
    if not active:
        raise ValueError('Add or enable a moving point, or switch to Free motion')
    by_id = {area['point_id']:area for area in plan.get('motion_areas', [])}
    missing = [point for point in plan['landmarks'] if point['id'] in active and
               not complete_area(by_id.get(point['id']), point, plan['source_id'])]
    if missing or any(area_id not in active for area_id in by_id):
        labels = ', '.join(f"{index+1}. {point['label']}" for index, point in enumerate(plan['landmarks']) if point in missing)
        raise ValueError('Update motion areas: '+labels)
    if not any(value for row in strict_mask(plan) for value in row):
        raise ValueError('Motion areas must contain an approved pixel before review')


def review_plan(plan):
    plan = copy.deepcopy(validate_plan(plan))
    if plan.get('render_mode') == 'only_pointed_parts':
        check_motion_areas(plan)
    elif not any(active_point(plan, p) for p in plan['landmarks']):
        raise ValueError('Add or enable at least one landmark before review')
    check_preparation(plan)
    plan['review'] = {'state': 'reviewed', 'strength_reference': plan['strength']}
    plan['review']['fingerprint'] = plan_fingerprint(plan)
    return plan


def check_preparation(plan):
    analysis = plan.get('analysis', {})
    if any(active_point(plan, p) and p.get('group', 'character') == 'character' for p in plan['landmarks']) and (
            'prepared_prompt' in analysis) and (analysis['prepared_prompt'] != plan['prompt'] or
            analysis.get('prepared_requested') != plan['requested'] or
            analysis.get('prepared_preparation') != analysis.get('preparation') or
            analysis.get('prepared_model_path') != analysis.get('model_path')):
        raise ValueError('Prepare character points for changed prompt or preparation settings')
    background = plan.get('background', {})
    if any(active_point(plan, p) and p.get('group') == 'background' for p in plan['landmarks']):
        if not background.get('prompt', '').strip():
            raise ValueError('Enter background motion before review')
        if (background.get('prepared_prompt') != background['prompt'] or
                background.get('prepared_preparation') != background.get('preparation') or
                (background.get('preparation') == 'model' and
                 'prepared_model_path' in background and
                 background['prepared_model_path'] != background.get('model_path'))):
            raise ValueError('Prepare background points for changed prompt or preparation settings')
        if not any(p['enabled'] and p.get('group') == 'background' and
                   (p.get('motion_role') == 'move' or
                    (p.get('motion_role') is None and any(
                        abs(key[axis]-p[axis]) > 1e-8
                        for key in p['path'] for axis in ('x','y'))))
                   for p in plan['landmarks']):
            raise ValueError('Enable at least one moving background point before review')


def require_review(plan, identity, size, prompt, duration, fps, strength, short_side,
                   requested=None, analysis=None, background=None):
    validate_plan(plan)
    if plan['source_id'] != identity or plan['source_size'] != list(size):
        raise ValueError('Source image changed; prepare points again')
    character_active = any(active_point(plan, p) and p.get('group', 'character') == 'character'
                           for p in plan['landmarks'])
    effective = {**plan, 'background':background} if background is not None else plan
    background_active = any(active_point(effective, p) and p.get('group') == 'background'
                            for p in plan['landmarks'])
    if character_active and (plan['prompt'] != prompt or (requested is not None and plan['requested'] != requested)):
        raise ValueError('Character prompt changed; prepare points again')
    if character_active and analysis is not None and 'prepared_prompt' in plan.get('analysis', {}) and (
            plan['analysis'].get('preparation') != analysis.get('preparation') or
            plan['analysis'].get('model_path') != analysis.get('model_path')):
        raise ValueError('Character preparation settings changed; prepare points again')
    if background_active and background is not None and plan.get('background', {}).get('enabled', False) != background.get('enabled', False):
        raise ValueError('Background settings changed; review points again')
    if background_active and background is not None and background.get('enabled') and (
            plan.get('background', {}).get('prompt') != background.get('prompt') or
            plan.get('background', {}).get('preparation') != background.get('preparation')):
        raise ValueError('Background settings changed; prepare background points again')
    if background_active and background is not None and background.get('enabled') and background.get('preparation') == 'model' and (
            plan.get('background', {}).get('prepared_model_path') is not None and
            plan['background']['prepared_model_path'] != (analysis or {}).get('model_path')):
        raise ValueError('Background model changed; prepare background points again')
    check_preparation(plan)
    review = plan.get('review', {})
    reference = review.get('strength_reference')
    if (review.get('state') != 'reviewed' or
            (reference is not None and (isinstance(reference, bool) or not isinstance(reference, (int, float))
                                        or not math.isfinite(reference) or not 0 <= reference <= .1))):
        raise ValueError('Points changed; renewed point review required')
    if reference is None:
        if review.get('fingerprint') != legacy_plan_fingerprint(plan):
            raise ValueError('Points changed; renewed point review required')
        review['strength_reference'] = plan['strength']
        review['fingerprint'] = plan_fingerprint(plan)
    elif review.get('fingerprint') != plan_fingerprint(plan):
        raise ValueError('Points changed; renewed point review required')
    check_motion_areas(plan)
    plan.update(source_id=identity, source_size=list(size), prompt=prompt,
                duration=float(duration), fps=int(fps), strength=float(strength),
                short_side=int(short_side), frames=frame_count(duration, fps),
                transform=canvas_transform(size, short_side))
    validate_plan(plan)
    return plan


def parse_landmarks(raw, requested, feedback=None, require_semantics=False):
    feedback = feedback if feedback is not None else []
    try:
        text = raw.strip()
        if text.startswith('```'):
            text = text.split('\n',1)[1].rsplit('```',1)[0]
        response = json.loads(text)
        points = response['landmarks']
        if not isinstance(points, list) or not points or len(points) > 64:
            raise ValueError('Missing landmarks')
        result = []
        for index, p in enumerate(points):
            try:
                if not isinstance(p['label'], str) or not p['label'].strip():
                    raise ValueError('Missing landmark label')
                for axis in ('x', 'y'):
                    coordinate(p[axis] if isinstance(p[axis], bool) else p[axis]/1000)
                point = {'label': p['label'].strip(), 'x': p['x']/1000, 'y': p['y']/1000}
                if require_semantics or any(field in p for field in ('motion_role', 'body_part', 'reason')):
                    validate_semantics(p)
                    point.update({field:p[field].strip() for field in ('body_part', 'motion_role', 'reason')})
                if any(point['label'].casefold() == old['label'].casefold() or
                       (abs(point['x']-old['x']) < 1e-6 and abs(point['y']-old['y']) < 1e-6)
                       for old in result):
                    raise ValueError('Duplicate label or location')
                result.append(point)
            except (KeyError, TypeError, ValueError) as error:
                feedback.append(f'Skipped suggestion {index+1}: {error}')
        if not result:
            raise ValueError('No valid landmarks; place points manually or retry Prepare')
        missing = [name for name in requested if name.lower() != 'auto' and not any(
            name.lower() in p['label'].lower() or name.lower() in p.get('body_part','').lower() for p in result)]
        if missing:
            feedback.append('Missing requested landmarks: '+', '.join(missing)+'. Add visible points manually if needed.')
        omissions = response.get('omissions', [])
        if isinstance(omissions, list):
            feedback.extend('Omitted: '+note for note in omissions if isinstance(note, str) and note.strip())
        return result
    except (KeyError, TypeError, ZeroDivisionError, json.JSONDecodeError) as error:
        raise ValueError('Invalid vision response; place landmarks manually or retry Prepare') from error


def canvas_tracks(plan):
    validate_plan(plan)
    reference = plan.get('review', {}).get('strength_reference', plan['strength'])
    scale = plan['strength'] / reference if reference else 0
    ox, oy, width, height = plan['transform']['content']
    tracks = []
    for point in plan['landmarks']:
        if not active_point(plan, point):
            continue
        path, segment, track = point['path'], 0, []
        for index in range(plan['frames']):
            t = index/(plan['frames']-1)
            while segment < len(path)-2 and t > path[segment+1]['t']:
                segment += 1
            a, b = path[segment:segment+2]
            u = (t-a['t'])/(b['t']-a['t'])
            values = {axis: max(0, min(1, point[axis]+((a[axis]+(b[axis]-a[axis])*u)-point[axis])
                                       *point['strength']*scale))
                      for axis in ('x','y')}
            track.append({'x': ox+values['x']*(width-1), 'y': oy+values['y']*(height-1)})
        tracks.append(track)
    return tracks
