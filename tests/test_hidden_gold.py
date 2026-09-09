import json
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from core.hidden_gold_catalog import ADDITIONS, LAYOUT
from core.layout_policy import compatible, curate_layouts
from core.topic_catalog import curate
from goldgen_service import GoldGenService, MAX_EXTRA_LABELS


class HiddenGoldTests(unittest.TestCase):
    def setUp(self):
        self.layouts = json.loads(Path('data/layouts.json').read_text(encoding='utf-8'))
        self.service = GoldGenService.__new__(GoldGenService)
        self.service.active_layouts = [item for item in self.layouts if not item.get('retired')]
        self.service._get_layout_performance = Mock(return_value={})
        self.service._get_page_engagement_stats = Mock(return_value=(1.0, 0.5))
        self.service._get_latest_insights = Mock(return_value={})

    def test_all_briefs_have_an_active_compatible_layout_and_unique_identity(self):
        self.assertEqual(22, len(ADDITIONS))
        self.assertEqual(22, len({t['curation_key'] for t in ADDITIONS}))
        self.assertEqual(22, len({t['headline'] for t in ADDITIONS}))
        for topic in ADDITIONS:
            self.assertEqual([LAYOUT], [l['name'] for l in self.layouts if compatible(topic, l)])

    def test_older_volume_gets_new_layout_without_changing_existing_settings(self):
        old = [l for l in self.layouts if l['name'] != LAYOUT]
        projected = curate_layouts(old)
        self.assertEqual(old, projected[:-1])
        self.assertEqual(next(l for l in self.layouts if l['name'] == LAYOUT), projected[-1])
        self.assertEqual(projected, curate_layouts(projected))
        projected[-1]['retired'] = True
        self.assertEqual(projected, curate_layouts(projected))

    def test_selection_with_and_without_learning_cannot_escape_topic_policy(self):
        for performance in ({}, {'GAMIFICATION_QUIZ': {'avg': 1000, 'n': 100}}):
            self.service._get_layout_performance.return_value = performance
            for topic in ADDITIONS:
                self.assertEqual(LAYOUT, self.service._choose_layout(1, 7, topic)[0]['name'])
            for index in range(len(self.layouts) * 2):
                self.assertNotEqual(LAYOUT, self.service._choose_layout(1, index, {'headline': 'TOOLS'})[0]['name'])

    def test_retired_only_option_is_not_resurrected(self):
        self.service.active_layouts = [dict(l, retired=True) for l in self.layouts]
        self.assertIsNone(self.service._choose_layout(1, 0, ADDITIONS[0])[0])

    def test_persistent_catalog_collision_keeps_existing_record_and_rotation_identity(self):
        existing = {'id': 11001, 'headline': 'EXISTING TOPIC', 'list_points': ['original']}
        result = curate([existing])
        self.assertEqual('EXISTING TOPIC', result[0]['headline'])
        self.assertEqual(len(result), len({t['id'] for t in result}))
        self.assertEqual(result, curate(result))

    def test_existing_unkeyed_headline_is_not_duplicated_or_revived(self):
        for retired in (False, True):
            existing = dict(ADDITIONS[0], id=42, retired=retired)
            del existing['curation_key']
            result = curate([existing])
            matching = [t for t in result if t['headline'] == existing['headline']]
            self.assertEqual(1, len(matching))
            self.assertEqual(42, matching[0]['id'])
            self.assertEqual(retired, matching[0]['retired'])
            self.assertEqual(result, curate(result))

    def test_service_excludes_topics_whose_only_layout_is_retired(self):
        import io
        layouts = [dict(l, retired=True) if l['name'] == LAYOUT else l for l in self.layouts]
        catalog = curate([{'id': 1, 'headline': 'TOOLS'}])
        with patch('goldgen_service.genai.Client'), \
             patch('builtins.open', return_value=io.StringIO(json.dumps(layouts))), \
             patch('core.topic_catalog.load_catalog', return_value=(catalog, catalog)):
            service = GoldGenService('test')
        self.assertFalse(any(t.get('series') for t in service.topics))
        self.assertTrue(any(t['id'] == 1 for t in service.topics))
        self.assertTrue(any(t.get('series') for t in service.catalog_topics))

    def test_each_mode_generates_prompt_with_shared_text_budget(self):
        layout = next(l for l in self.layouts if l['name'] == LAYOUT)
        expected = {'micro': 'Make one mineral specimen', 'cutaway': 'surface in the upper fifth',
                    'journey': 'source-to-slope-to-valley'}
        with patch('core.content_feedback.feedback_prompt', return_value=''):
            for brief in ADDITIONS:
                topic = dict(brief, layout=LAYOUT, composition=layout['composition'])
                prompt = self.service.generate_image_prompt(topic)
                self.assertIn(expected[brief['visual_mode']], prompt)
                self.assertIn(f'At most {MAX_EXTRA_LABELS} additional labels', prompt)
                self.assertIn('Do not invent numerical depths', prompt)

    def test_experiments_do_not_pair_an_unrelated_topic_with_series_layout(self):
        from core.layout_experiments import enroll
        topic = {'id': 1, 'headline': 'TOOLS', 'caption_approved': True, 'layout': 'TOOLKIT FLATLAY'}
        layouts = [l for l in self.layouts if l['name'] in (LAYOUT, 'TOOLKIT FLATLAY')]
        with patch('core.layout_experiments.get_db_connection') as connection:
            self.assertEqual(topic, enroll(1, topic, 'caption', layouts))
            connection.assert_not_called()

    def test_dashboard_remaps_saved_identity_and_shows_compatible_layout(self):
        import tempfile
        from flask import Flask
        from controllers import routes
        topic = ADDITIONS[0]
        old = {'id': 1, 'headline': 'TOOLS', 'subtitle': 'Tools'}
        self.service.topics = [old, topic]
        self.service.source_topics = [old, topic]
        app = Flask(__name__)
        app.secret_key = 'test'
        app.register_blueprint(routes.bp)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            # The saved index belongs to a previous ordering of the catalog.
            (path / 'topic_state.json').write_text(json.dumps({
                'current_topic_index': 0, 'catalog_ids': [topic['id'], old['id']]}))
            with patch('controllers.routes.DATA_DIR', path), \
                 patch('goldgen_service.GoldGenService', return_value=self.service):
                client = app.test_client()
                with client.session_transaction() as session:
                    session['authenticated'] = True
                response = client.get('/api/topic-info')
                self.assertEqual(200, response.status_code)
                self.assertEqual(topic['id'], response.json['current']['id'])
                self.assertEqual(LAYOUT, response.json['current']['layout'])
                self.assertNotEqual(LAYOUT, response.json['next']['layout'])
                self.service.active_layouts = []
                response = client.get('/api/topic-info')
                self.assertEqual(200, response.status_code)
                self.assertIsNone(response.json['current']['layout'])


if __name__ == '__main__':
    unittest.main()
