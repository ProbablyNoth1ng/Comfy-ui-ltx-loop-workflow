import copy
import json
import unittest

from comfy_ltx_loop.motion import (new_plan, parse_landmarks, validate_plan,
                                 review_plan, require_review, canvas_transform,
                                 canvas_tracks, plan_fingerprint, legacy_plan_fingerprint)


class MotionTests(unittest.TestCase):
    def test_point_group_switches_filter_four_track_sets_and_preserve_points(self):
        plan = self.plan()
        plan['landmarks'].append({**copy.deepcopy(plan['landmarks'][0]),
                                  'label':'leaf','group':'background'})
        plan['background'] = {'enabled':True,'prompt':'Leaves sway','preparation':'manual',
                              'prepared_prompt':'Leaves sway','prepared_preparation':'manual'}
        for character, background, count in [(True,True,2),(True,False,1),
                                              (False,True,1),(False,False,0)]:
            with self.subTest(character=character, background=background):
                plan['use_character_points'] = character
                plan['use_background_points'] = background
                self.assertEqual(len(canvas_tracks(plan)),count)
                self.assertEqual(len(plan['landmarks']),2)
        del plan['use_character_points'], plan['use_background_points']
        self.assertEqual(len(canvas_tracks(plan)),2)

    def test_disabled_group_skips_stale_preparation_and_switch_invalidates_review(self):
        plan = self.plan()
        plan['analysis'] = {'preparation':'manual','model_path':'model',
                            'prepared_prompt':'old prompt','prepared_requested':['hair tip'],
                            'prepared_preparation':'manual','prepared_model_path':'model'}
        plan['use_character_points'] = False
        plan['use_background_points'] = False
        plan['review'] = {'state':'not_required'}
        self.assertEqual(canvas_tracks(plan),[])
        plan['use_character_points'] = True
        with self.assertRaisesRegex(ValueError,'Prepare character'):
            review_plan(plan)
        plan['analysis']['prepared_prompt'] = plan['prompt']
        reviewed = review_plan(plan)
        reviewed['use_character_points'] = False
        with self.assertRaisesRegex(ValueError,'review'):
            require_review(reviewed,'abc',(600,1000),reviewed['prompt'],6,24,.01,720)

    def test_reviewed_plan_cannot_activate_saved_background_points_with_new_text(self):
        plan = self.plan()
        plan['landmarks'].append({**copy.deepcopy(plan['landmarks'][0]),
                                  'label':'leaf','group':'background'})
        plan['background'] = {'enabled':False,'prompt':'','preparation':'manual'}
        reviewed = review_plan(plan)
        with self.assertRaisesRegex(ValueError,'review'):
            require_review(reviewed,'abc',(600,1000),reviewed['prompt'],6,24,.01,720,
                background={'enabled':True,'prompt':'Leaves sway','preparation':'manual'})

    def test_background_review_tracks_and_legacy_fingerprint(self):
        legacy = review_plan(self.plan())
        fingerprint = legacy['review']['fingerprint']
        require_review(legacy, 'abc', (600, 1000), legacy['prompt'], 6, 24, .01, 720)
        self.assertEqual(fingerprint, legacy['review']['fingerprint'])
        self.assertNotIn('background', legacy)
        plan = self.plan()
        background = new_plan('abc', (600, 1000), 'leaves', ['auto'], [
            {'label':'leaf','x':.2,'y':.3,'motion_role':'move','body_part':'foliage','reason':'sway'}])['landmarks'][0]
        background['group'] = 'background'
        plan['landmarks'].append(background)
        plan['background'] = {'enabled':True,'prompt':'Leaves sway','preparation':'model',
                              'prepared_prompt':'Leaves sway','prepared_preparation':'model'}
        reviewed = review_plan(plan)
        self.assertEqual(len(canvas_tracks(reviewed)), 2)
        reviewed['background']['enabled'] = False
        self.assertEqual(len(canvas_tracks(reviewed)), 1)
        with self.assertRaisesRegex(ValueError, 'review'):
            require_review(reviewed, 'abc', (600,1000), reviewed['prompt'], 6,24,.01,720)

    def test_background_requires_moving_point_and_current_prompt(self):
        plan = self.plan()
        plan['background'] = {'enabled':True,'prompt':'Leaves sway','preparation':'model',
                              'prepared_prompt':'Leaves sway','prepared_preparation':'model'}
        plan['landmarks'].append({**copy.deepcopy(plan['landmarks'][0]), 'group':'background',
                                  'motion_role':'anchor', 'body_part':'tree', 'reason':'stationary',
                                  'path':[{'t':0,'x':.5,'y':.5},{'t':1,'x':.5,'y':.5}]})
        with self.assertRaisesRegex(ValueError, 'moving background'):
            review_plan(plan)
        plan['landmarks'].append({**plan['landmarks'][0], 'group':'background'})
        plan['background']['prompt'] = 'Clouds drift'
        with self.assertRaisesRegex(ValueError, 'Prepare background'):
            review_plan(plan)

    def plan(self, size=(600, 1000)):
        return new_plan('abc', size, 'gentle hair motion', ['hair tip'],
                        [{'label': 'hair tip', 'x': .5, 'y': .5}], 6, 24, .01, 720)

    def test_portrait_and_landscape_alignment_survives_reopen(self):
        for size in [(600, 1000), (1600, 900)]:
            p = json.loads(json.dumps(self.plan(size)))
            p = review_plan(p)
            transform = canvas_transform(size, 720)
            tracks = canvas_tracks(p)
            self.assertEqual(len(tracks[0]), 145)
            self.assertEqual(tracks[0][0], tracks[0][-1])
            point = tracks[0][0]
            x, y, w, h = transform['content']
            self.assertAlmostEqual((point['x']-x)/(w-1), .5)
            self.assertAlmostEqual((point['y']-y)/(h-1), .5)
            require_review(p, 'abc', size, p['prompt'], 6, 24, .01, 720)

    def test_canvas_and_half_resolution_guide_are_aligned(self):
        cases = [
            ((1312, 736), 720, [1344, 768], [30, 24, 1283, 720]),
            ((736, 1312), 720, [768, 1344], [24, 30, 720, 1283]),
            ((1600, 900), 720, [1280, 768], [0, 24, 1280, 720]),
            ((1000, 1000), 720, [768, 768], [24, 24, 720, 720]),
            ((1280, 704), 704, [1280, 704], [0, 0, 1280, 704]),
        ]
        for size, short_side, canvas, content in cases:
            with self.subTest(size=size, short_side=short_side):
                transform = canvas_transform(size, short_side)
                self.assertEqual(transform['canvas'], canvas)
                self.assertEqual(transform['content'], content)
                self.assertTrue(all(dimension % 64 == 0 for dimension in canvas))
                self.assertTrue(all((dimension // 2) % 32 == 0 for dimension in canvas))

    def test_padded_canvas_keeps_normalized_tracks_and_returning_path(self):
        plan = self.plan((1312, 736))
        transform = plan['transform']
        self.assertEqual(plan['landmarks'][0]['x'], .5)
        self.assertEqual(plan['landmarks'][0]['y'], .5)
        tracks = canvas_tracks(plan)[0]
        self.assertEqual(tracks[0], tracks[-1])
        self.assertAlmostEqual(tracks[0]['x'], transform['content'][0] + (transform['content'][2]-1)/2)
        self.assertAlmostEqual(tracks[0]['y'], transform['content'][1] + (transform['content'][3]-1)/2)
        self.assertGreater(tracks[72]['x'], tracks[0]['x'])

    def test_old_reviewed_canvas_requires_new_preparation(self):
        plan = self.plan((1312, 736))
        plan['transform'] = {'source': [1312, 736], 'canvas': [1312, 736],
                             'content': [14, 8, 1283, 720]}
        plan['review'] = {'state': 'reviewed', 'fingerprint': plan_fingerprint(plan)}
        with self.assertRaisesRegex(ValueError, 'prepare and review again'):
            require_review(plan, 'abc', (1312, 736), plan['prompt'], 6, 24, .01, 720)

    def test_reuse_updates_timing_and_scales_strength_without_changing_points(self):
        p = review_plan(self.plan())
        points = copy.deepcopy(p['landmarks'])
        require_review(p, 'abc', (600, 1000), p['prompt'], 3, 24, .02, 800)
        self.assertEqual(p['landmarks'], points)
        self.assertEqual(p['source_id'], 'abc')
        self.assertEqual(p['prompt'], 'gentle hair motion')
        self.assertEqual(p['frames'], 73)
        self.assertEqual(p['transform'], canvas_transform((600, 1000), 800))
        track = canvas_tracks(p)[0]
        self.assertAlmostEqual((track[36]['x']-track[0]['x'])/(p['transform']['content'][2]-1), .02)
        self.assertEqual(track[0], track[-1])
        require_review(p, 'abc', (600, 1000), p['prompt'], 6, 24, .005, 720)
        track = canvas_tracks(p)[0]
        self.assertAlmostEqual((track[72]['x']-track[0]['x'])/(p['transform']['content'][2]-1), .005)
        self.assertEqual(p['landmarks'], points)

    def test_point_edits_and_altered_review_are_rejected(self):
        p = review_plan(self.plan())
        p['landmarks'][0]['path'][1]['x'] += .001
        self.assertNotEqual(p['review']['fingerprint'], plan_fingerprint(p))
        with self.assertRaisesRegex(ValueError, 'review'):
            require_review(p, 'abc', (600, 1000), p['prompt'], 6, 24, .01, 720)
        p = review_plan(self.plan())
        p['review']['strength_reference'] = .02
        with self.assertRaisesRegex(ValueError, 'review'):
            require_review(p, 'abc', (600, 1000), p['prompt'], 6, 24, .01, 720)

    def test_legacy_accepted_plan_is_upgraded_on_reuse(self):
        p = self.plan()
        p['review'] = {'state': 'reviewed', 'fingerprint': legacy_plan_fingerprint(p)}
        reopened = json.loads(json.dumps(p))
        require_review(reopened, 'abc', (600, 1000), reopened['prompt'], 3, 24, .02, 800)
        self.assertEqual(reopened['review']['strength_reference'], .01)
        self.assertEqual(reopened['review']['fingerprint'], plan_fingerprint(reopened))
        self.assertEqual(reopened['landmarks'], p['landmarks'])
        self.assertGreater(canvas_tracks(reopened)[0][36]['x'], canvas_tracks(reopened)[0][0]['x'])

    def test_anchor_stays_still_when_strength_changes(self):
        p = review_plan(new_plan('abc', (600, 1000), 'hair', ['auto'], [
            {'label': 'eye', 'x': .4, 'y': .3, 'body_part': 'face',
             'motion_role': 'anchor', 'reason': 'stay still'}]))
        require_review(p, 'abc', (600, 1000), p['prompt'], 3, 24, .05, 800)
        self.assertTrue(all(key == canvas_tracks(p)[0][0] for key in canvas_tracks(p)[0]))

    def test_strength_scaling_keeps_tracks_inside_image_near_edge(self):
        p = review_plan(new_plan('abc', (600, 1000), 'hair', ['auto'],
                                 [{'label': 'tip', 'x': .995, 'y': .4}]))
        require_review(p, 'abc', (600, 1000), p['prompt'], 6, 24, .1, 720)
        x, _, width, _ = p['transform']['content']
        self.assertTrue(all(x <= key['x'] <= x + width - 1 for key in canvas_tracks(p)[0]))

    def test_invalid_suggestions_and_paths_are_actionable(self):
        for raw in ['nonsense', '{"landmarks":[]}',
                    '{"landmarks":[{"label":"hair tip","x":1001,"y":500}]}']:
            with self.assertRaises(ValueError):
                parse_landmarks(raw, ['hair tip'])
        p = self.plan()
        p['landmarks'][0]['path'][1]['x'] = 2
        with self.assertRaisesRegex(ValueError, 'bounds'):
            validate_plan(p)

    def test_grounding_uses_explicit_thousand_coordinate_scale(self):
        points = parse_landmarks('{"landmarks":[{"label":"hair tip","x":1,"y":500}]}', ['hair tip'])
        self.assertEqual(points[0]['x'], .001)

    def test_timing_must_fit_ltx_and_playback_exactly(self):
        with self.assertRaises(ValueError):
            new_plan('abc', (600,1000), 'motion', ['tip'], [], 6.1,24,.01,720)


if __name__ == '__main__':
    unittest.main()
