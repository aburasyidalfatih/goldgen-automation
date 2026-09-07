import ast
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path


class RetryTests(unittest.TestCase):
    def test_feedback_is_page_scoped_and_database_failure_does_not_block(self):
        tree=ast.parse(Path('core/content_feedback.py').read_text(encoding='utf-8'))
        definitions=[n for n in tree.body if isinstance(n,ast.FunctionDef)]
        with tempfile.TemporaryDirectory() as tmp:
            def connect():
                c=sqlite3.connect(Path(tmp)/'feedback.db');c.row_factory=sqlite3.Row
                return c
            ns={'get_db_connection':connect,'json':json,'redact':str}
            exec(compile(ast.Module(body=definitions,type_ignores=[]),'feedback','exec'),ns)
            self.assertEqual('',ns['feedback_prompt']('a'))
            ns['save_feedback']('a',{'headline':'River'},'image',5,'Use readable labels')
            self.assertIn('Use readable labels',ns['feedback_prompt']('a'))
            self.assertNotIn('Use readable labels',ns['feedback_prompt']('b'))
            def fail(): raise OSError('unavailable')
            ns['get_db_connection']=fail
            ns['save_feedback']('a',{},'image',None,'test')
            self.assertEqual('',ns['feedback_prompt']('a'))

    def test_atomic_claim_blocks_second_send_and_uncertain_retry(self):
        tree=ast.parse(Path('auto_poster.py').read_text(encoding='utf-8'))
        cls=next(n for n in tree.body if isinstance(n,ast.ClassDef))
        method=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='retry_existing_post')
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'test.db'
            def connect(): return sqlite3.connect(path)
            c=connect();c.execute('CREATE TABLE posts(id INTEGER,status TEXT,fb_post_id TEXT,error_message TEXT)')
            c.execute("INSERT INTO posts VALUES(1,'failed',NULL,NULL)");c.commit();c.close()
            ns={'get_db_connection':connect,'redact':str}
            exec(compile(ast.Module(body=[method],type_ignores=[]),'retry','exec'),ns)
            class Poster: pass
            Poster.retry_existing_post=ns['retry_existing_post']
            poster=Poster()
            def send(pid):
                self.assertFalse(poster.retry_existing_post(pid)[0])
                raise TimeoutError('uncertain')
            poster._retry_claimed_post=send
            self.assertFalse(poster.retry_existing_post(1)[0])
            self.assertFalse(poster.retry_existing_post(1)[0])
            c=connect();self.assertEqual('retrying',c.execute('SELECT status FROM posts').fetchone()[0]);c.close()
