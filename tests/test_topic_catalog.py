import unittest
import json
import tempfile
from pathlib import Path
from core.topic_catalog import curate,allowed,remap_state


class CatalogTests(unittest.TestCase):
    def topic(self, tid, title):
        return {'id':tid,'headline':title,'subtitle':'test','list_header':'points','list_points':['a']}

    def test_idempotent_revisions_keep_ids_and_history(self):
        original=[self.topic(83,'SLUICE BOXES'),self.topic(65,'FINE GOLD RECOVERY'),
                  self.topic(6,'GOLD VS PYRITE'),self.topic(76,'GOLD VS PYRITE'),
                  self.topic(95,'Crafting Viral Content That Strikes Paydirt')]
        output=curate(original)
        self.assertEqual(output,curate(output))
        self.assertEqual([83,65,6,76,95],[t['id'] for t in output[:5]])
        self.assertEqual('SLUICE BOXES',output[0]['headline'])
        self.assertNotEqual(['a'],output[0]['list_points'])
        self.assertEqual(6,output[3]['canonical_topic_id'])
        self.assertFalse(allowed(output[4]))
        self.assertEqual(2,len([t for t in output if t.get('curation_key')]))
        self.assertEqual(['a'],original[0]['list_points'])

    def test_conflicting_reserved_id_not_overwritten(self):
        output=curate([self.topic(10001,'Existing distinct subject')])
        self.assertEqual(3,len(set(t['id'] for t in output)))
        self.assertEqual('Existing distinct subject',output[0]['headline'])
        self.assertEqual(output,curate(output))

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
            original=[self.topic(65,'FINE GOLD RECOVERY')]
            path.write_text(json.dumps(original),encoding='utf-8')
            before,after=load_catalog(path)
            self.assertEqual(original,before)
            backups=list(path.parent.glob('topics.json.backup_*'))
            self.assertEqual(1,len(backups))
            self.assertEqual(original,json.loads(backups[0].read_text()))
            self.assertEqual(after,json.loads(path.read_text()))
            load_catalog(path)
            self.assertEqual(backups,list(path.parent.glob('topics.json.backup_*')))


if __name__=='__main__':
    unittest.main()
