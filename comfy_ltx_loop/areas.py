"""Source-coordinate motion areas and the isolated SAM image adapter."""
import hashlib
import json

import numpy as np


def area_fingerprint(point):
    """Only geometry/strength changes stale an automatically proposed area."""
    data = {key: point[key] for key in ('id', 'x', 'y', 'strength', 'path')}
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def complete_area(area, point, source_id):
    if not isinstance(area, dict) or area.get('point_id') != point.get('id'):
        return False
    freshness = area.get('freshness')
    geometry = {key: point[key] for key in ('id', 'x', 'y', 'strength', 'path')}
    return (isinstance(freshness, dict) and freshness.get('source') == source_id and
            (freshness.get('point') == area_fingerprint(point) or freshness.get('geometry') == geometry) and
            any(value for row in area.get('mask', []) for value in row))


def _trajectory_mask(mask, point):
    height, width = mask.shape
    for key in point['path']:
        x = round((point['x'] + (key['x'] - point['x']) * point['strength']) * width)
        y = round((point['y'] + (key['y'] - point['y']) * point['strength']) * height)
        mask[max(0, min(height - 1, y)), max(0, min(width - 1, x))] = True
    return mask


def propose_area(predictor, image, point, size, source_id=''):
    """Ask SAM with one foreground point and extend its best mask along its path."""
    width, height = size
    if tuple(image.shape[:2]) != (height, width):
        raise ValueError('SAM source image dimensions do not match the motion plan')
    predictor.set_image(image)
    coords = np.array([[min(width - 1, point['x'] * width),
                        min(height - 1, point['y'] * height)]], dtype=np.float32)
    masks, scores, _ = predictor.predict(point_coords=coords, point_labels=np.array([1], dtype=np.int32),
                                         multimask_output=True)
    masks, scores = np.asarray(masks), np.asarray(scores)
    if masks.ndim != 3 or masks.shape[1:] != (height, width) or not len(scores):
        raise ValueError('SAM returned no valid source-size motion area')
    mask = masks[int(np.argmax(scores))].astype(bool)
    mask = _trajectory_mask(mask, point)
    return {'point_id':point['id'], 'mask':(mask.astype(np.uint8) * 255).tolist(),
            'freshness':{'source':source_id, 'point':area_fingerprint(point), 'kind':'sam2.1-small'}}


def release_predictor(predictor):
    """Drop image embeddings even when the caller's model load/prediction failed."""
    if predictor is not None:
        for name in ('reset_predictor', 'reset_image'):
            method = getattr(predictor, name, None)
            if callable(method):
                method()
                break


def propose_motion_areas(image, plan, checkpoint='models/sam2.1_hiera_small.pt'):
    """Load SAM only for this preparation call, preserving usable existing areas."""
    from .vision import snapshot_path
    path = snapshot_path(checkpoint)
    if not path.is_file():
        raise ValueError('Install the SAM 2.1 Small checkpoint at '+str(path))
    predictor = model = None
    try:
        import torch
        from sam2.build_sam import build_sam2
        from sam2.sam2_image_predictor import SAM2ImagePredictor
        model = build_sam2('configs/sam2.1/sam2.1_hiera_s.yaml', str(path), device='cuda')
        predictor = SAM2ImagePredictor(model)
        source = np.asarray(image.convert('RGB'))
        areas = {area['point_id']:area for area in plan.get('motion_areas', [])}
        for point in plan['landmarks']:
            if point.get('motion_role') == 'anchor' or not point.get('enabled', True):
                continue
            if complete_area(areas.get(point['id']), point, plan['source_id']):
                continue
            areas[point['id']] = propose_area(predictor, source, point, plan['source_size'], plan['source_id'])
        plan['motion_areas'] = list(areas.values())
        return plan
    finally:
        release_predictor(predictor)
        del predictor, model
        try:
            import gc, torch
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.ipc_collect()
        except (ImportError, AttributeError):
            pass
