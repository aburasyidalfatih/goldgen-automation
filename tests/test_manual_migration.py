import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from core import database


class ManualMigrationTest(unittest.TestCase):
    def test_duplicate_archive_and_repeat_migration(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(database, 'DB_PATH', Path(folder) / 'test.db'):
                database.init_db()
                c = database.get_db_connection()
                c.execute('DROP INDEX ux_posts_fb_post_id')
                for source in ('manual', 'goldgen', 'manual'):
                    c.execute("INSERT INTO posts(fb_post_id,source,timestamp,content,status) VALUES('1_2',?,'2026-09-11T03:00:00+0000','Gold topic','success')", (source,))
                c.commit()
                c.close()
                database.init_db()
                database.init_db()
                c = database.get_db_connection()
                self.assertEqual(c.execute('SELECT count(*) FROM posts').fetchone()[0], 1)
                self.assertEqual(c.execute('SELECT count(*) FROM posts_duplicate_archive').fetchone()[0], 2)
                self.assertEqual(c.execute('SELECT source FROM posts').fetchone()[0], 'goldgen')
                self.assertIsNotNone(c.execute('SELECT julianday(timestamp) FROM posts').fetchone()[0])
                with self.assertRaises(sqlite3.IntegrityError):
                    c.execute("INSERT INTO posts(fb_post_id) VALUES('1_2')")
                c.close()
