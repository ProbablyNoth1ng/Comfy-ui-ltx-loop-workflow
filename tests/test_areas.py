import unittest

import numpy as np

from comfy_ltx_loop.areas import area_fingerprint, complete_area, propose_area


class AreaTests(unittest.TestCase):
    def test_proposal_uses_foreground_prompt_best_mask_and_trajectory(self):
        calls = []
        class Predictor:
            def set_image(self, image):
                calls.append(('image', image.shape))
            def predict(self, **kwargs):
                calls.append(('predict', kwargs))
                masks = np.zeros((3, 6, 8), dtype=bool)
                masks[0, 1, 1] = True
                masks[2, 2, 3] = True
                return masks, np.array([.1, .2, .9]), None
        point = {'id':'hair','x':.25,'y':.5,'strength':1,
                 'path':[{'t':0,'x':.25,'y':.5},{'t':.5,'x':.75,'y':.5},{'t':1,'x':.25,'y':.5}]}
        area = propose_area(Predictor(), np.zeros((6,8,3),dtype=np.uint8), point, [8,6])
        self.assertEqual(calls[1][1]['point_coords'].tolist(), [[2.,3.]])
        self.assertEqual(calls[1][1]['point_labels'].tolist(), [1])
        self.assertTrue(calls[1][1]['multimask_output'])
        self.assertEqual(area['mask'][2][3], 255)
        self.assertEqual(area['mask'][3][6], 255)
        self.assertEqual(area['freshness']['point'], area_fingerprint(point))

    def test_current_area_requires_matching_point_geometry(self):
        point = {'id':'hair','x':.2,'y':.3,'strength':1,'path':[{'t':0,'x':.2,'y':.3},{'t':1,'x':.2,'y':.3}]}
        area = {'point_id':'hair','mask':[[255]],'freshness':{'source':'source','point':area_fingerprint(point)}}
        self.assertTrue(complete_area(area, point, 'source'))
        point['path'][0]['x'] = .21
        self.assertFalse(complete_area(area, point, 'source'))
