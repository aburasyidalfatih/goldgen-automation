import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from core.visual_plan import parse_plan, render_plan, save_plan, design_report


class VisualPlanTests(unittest.TestCase):
    def plan(self):
        return dict(title='READ THE RIVER', labels=['Bedrock traps hold settled material'],
            question='Which location would you sample first based on these visible clues?',
            question_type='sampling_choice', density='detail', caption_consistent=True)

    def test_copy_budget_and_invalid_plans(self):
        plan = self.plan()
        self.assertIsNotNone(parse_plan(json.dumps(plan), {}))
        plan['density'] = 'light'
        self.assertIsNone(parse_plan(json.dumps(plan), {}))
        plan = self.plan(); plan['caption_consistent'] = False
        self.assertIsNone(parse_plan(json.dumps(plan), {}))
        self.assertIsNone(parse_plan('[]', {}))
        plan = self.plan(); plan['question'] = 'Share this with your friends and tell us what you think?'
        self.assertIsNone(parse_plan(json.dumps(plan), {}))

    def test_final_copy_replaces_conflicting_old_budget(self):
        prompt = 'TEXT ALLOWED IN THE IMAGE old limits\nLAYOUT STYLE: CUTAWAY\n- TEXT BUDGET: old restriction\n'
        rendered = render_plan(prompt, self.plan())
        self.assertNotIn('old limits', rendered)
        self.assertNotIn('old restriction', rendered)
        self.assertIn(self.plan()['question'], rendered)

    def test_report_is_page_scoped_and_excludes_unmeasured_posts(self):
        with tempfile.TemporaryDirectory() as tmp:
            def connect():
                c = sqlite3.connect(Path(tmp)/'test.db'); c.row_factory=sqlite3.Row; return c
            with patch('core.visual_plan.get_db_connection', side_effect=connect):
                c=connect()
                c.executescript('CREATE TABLE posts(page_id TEXT,image_path TEXT,fb_post_id TEXT,status TEXT,timestamp TEXT); CREATE TABLE post_views_current(fb_post_id TEXT,views_48h REAL);')
                for page, img, fb, views in [('a','one','1',100),('a','two','2',None),('b','three','3',900)]:
                    c.execute("INSERT INTO posts VALUES(?,?,?,'success',datetime('now'))",(page,img,fb))
                    c.execute('INSERT INTO post_views_current VALUES(?,?)',(fb,views))
                c.commit();c.close()
                for page,img in [('a','one'),('a','two'),('b','three')]:
                    save_plan(page,img,{'visual_plan':self.plan()})
                report=design_report('a')
                self.assertEqual(1,report['groups'][0]['samples'])
                self.assertEqual(100,report['groups'][0]['median_views_48h'])
            with patch('core.visual_plan.get_db_connection', side_effect=OSError):
                save_plan('a','one',{})  # Storage failure never blocks a post.
