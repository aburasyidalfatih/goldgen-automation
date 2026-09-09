import unittest
import json
import tempfile
from pathlib import Path
from core.topic_catalog import curate,allowed,remap_state
from core.topic_catalog import ADDITIONS
from core.hidden_gold_catalog import ADDITIONS as HIDDEN_ADDITIONS


class CatalogTests(unittest.TestCase):
    def topic(self, tid, title):
        return {'id':tid,'headline':title,'subtitle':'test','list_header':'points','list_points':['a']}

    def test_idempotent_revisions_keep_ids_and_history(self):
        original=[self.topic(83,'SLUICE BOXES'),self.topic(65,'FINE GOLD RECOVERY'),
                  self.topic(6,'GOLD VS PYRITE'),self.topic(76,'GOLD VS PYRITE'),
                  self.topic(95,'Crafting Viral Content That Strikes Paydirt')]
        output=curate(original)
        self.assertEqual(output,curate(output))
        self.assertEqual([83,65,6,95],[t['id'] for t in output[:4]])
        self.assertEqual('SLUICE BOXES',output[0]['headline'])
        self.assertNotEqual(['a'],output[0]['list_points'])
        self.assertNotIn(76, [t['id'] for t in output])
        self.assertFalse(allowed(output[3]))
        self.assertEqual(len(ADDITIONS) + len(HIDDEN_ADDITIONS),len([t for t in output if t.get('curation_key')]))
        self.assertEqual(['a'],original[0]['list_points'])

    def test_conflicting_reserved_id_not_overwritten(self):
        output=curate([self.topic(10001,'Existing distinct subject')])
        self.assertEqual(1 + len(ADDITIONS) + len(HIDDEN_ADDITIONS),len(set(t['id'] for t in output)))
        self.assertEqual('Existing distinct subject',output[0]['headline'])
        self.assertEqual(output,curate(output))

    def test_duplicate_cleanup_uses_identity_not_fixed_ids(self):
        original = [self.topic(800, 'GOLD VS PYRITE'),
                    self.topic(900, 'GOLD VS PYRITE'), self.topic(901, 'OTHER')]
        cleaned = curate(original)
        self.assertEqual([800, 901], [t['id'] for t in cleaned[:2]])
        state = remap_state({'current_topic_index': 2, 'recently_used': [0, 1, 2]}, original, cleaned)
        self.assertEqual(1, state['current_topic_index'])
        self.assertEqual([0, 1], state['recently_used'])
        self.assertEqual(3, len(original))

    def test_retired_orphan_is_preserved(self):
        orphan = dict(self.topic(900, 'UNIQUE'), retired=True, canonical_topic_id=800)
        self.assertEqual(orphan['id'], curate([orphan])[0]['id'])

    def test_old_position_state_remapped_by_identity(self):
        old=[self.topic(1,'A'),self.topic(2,'B'),self.topic(3,'C')]
        active=[old[0],old[2]]
        state=remap_state({'current_topic_index':2,'recently_used':[0,1,2]},old,active)
        self.assertEqual(1,state['current_topic_index'])
        self.assertEqual([0,1],state['recently_used'])
        self.assertEqual(state,remap_state(state,old,active))

    def test_catalog_id_collision_fails_visibly(self):
        with self.assertRaises(ValueError):
            curate([self.topic(1,'A'),self.topic(1,'B')])

    def test_persistent_migration_keeps_backup_and_does_not_repeat(self):
        from core.topic_catalog import load_catalog
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'topics.json'
            original=[self.topic(65,'FINE GOLD RECOVERY'),
                      self.topic(6,'GOLD VS PYRITE'), self.topic(76,'GOLD VS PYRITE')]
            path.write_text(json.dumps(original),encoding='utf-8')
            before,after=load_catalog(path)
            self.assertEqual(original,before)
            backups=list(path.parent.glob('topics.json.backup_*'))
            self.assertEqual(1,len(backups))
            self.assertEqual(original,json.loads(backups[0].read_text()))
            self.assertEqual(after,json.loads(path.read_text()))
            self.assertNotIn(76, [t['id'] for t in after])
            load_catalog(path)
            self.assertEqual(backups,list(path.parent.glob('topics.json.backup_*')))


if __name__=='__main__':
    unittest.main()
