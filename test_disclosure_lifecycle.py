"""Bounded reset and selective-history lifecycle regressions."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, Mock

import canon
import disclosure_rules as d
from test_disclosure import fixture
from test_fixture import TEST_FACTS
from npc_fixture import build_npc_fixture
import collapse
import map_data


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / 'state.json'
        redirect = patch.object(canon, 'STATE_FILE', str(self.path))
        redirect.start(); self.addCleanup(redirect.stop)
        self.state = fixture()
        self.save()

    def save(self):
        self.path.write_text(json.dumps(self.state))

    def reject(self, call):
        before, disk = deepcopy(self.state), self.path.read_bytes()
        with patch.object(canon, '_save_npc_commit') as writer:
            with self.assertRaises(ValueError):
                call()
            writer.assert_not_called()
        self.assertEqual(self.state, before)
        self.assertEqual(self.path.read_bytes(), disk)

    def test_legacy_marker_delete_and_resolve_rejected(self):
        del self.state['disclosure']; self.save()
        for operation in (canon.forget_fact, canon.resolve_fact):
            self.reject(lambda: operation(self.state, 3))
        self.assertNotIn('disclosure', self.state)

    def test_disclosed_references_protected(self):
        for number in (1, 2, 3):
            self.reject(lambda: canon.forget_fact(self.state, number))
        self.reject(lambda: canon.resolve_fact(self.state, 3))

    def test_historical_resolution_allowed_and_idempotent(self):
        records = deepcopy(self.state['disclosure'])
        for number in (1, 2):
            canon.resolve_fact(self.state, number)
        self.assertEqual(d.inspect_disclosure(self.state)['status'], 'valid')
        self.assertEqual(self.state['disclosure'], records)
        self.assertEqual(canon.load_state(), self.state)
        with patch.object(canon, '_save_npc_commit') as writer:
            canon.resolve_fact(self.state, 1)
            writer.assert_not_called()

    def test_ordinary_supersession_preserves_acquisition(self):
        before = deepcopy(self.state['disclosure'])
        canon.add_fact(self.state, 'The brass key is in the foyer.', 'state')
        self.assertEqual(self.state['facts'][1]['status'], 'superseded')
        self.assertEqual(self.state['disclosure'], before)
        self.assertEqual(d.inspect_disclosure(canon.load_state())['status'], 'valid')

    def test_unreferenced_delete_preserves_acquisitions(self):
        self.state['facts'].append({'id':4,'type':'event','text':'An unrelated event.','status':'active'})
        self.state['next_fact_id'] = 5
        self.save()
        before = deepcopy(self.state['disclosure'])
        self.assertEqual(canon.forget_fact(self.state, 4), 'An unrelated event.')
        self.assertEqual(self.state['disclosure'], before)
        self.assertEqual(canon.load_state(), self.state)

    def test_invalid_storage_blocks_edits_and_resets(self):
        for damaged in (None, {'version':2}, {'version':1}):
            self.state = fixture(); self.state['disclosure'] = damaged; self.save()
            for operation in (lambda: canon.forget_fact(self.state, 1),
                              lambda: canon.resolve_fact(self.state, 1),
                              lambda: canon.forget_all(self.state),
                              lambda: canon.reset_npc_state(self.state),
                              lambda: canon.reset_npc_test_fixture(self.state)):
                self.reject(operation)

    def test_stale_references_and_generations_reject_reset(self):
        for change in ('text', 'world_generation', 'npc_generation'):
            self.state = fixture()
            if change == 'text':
                self.state['facts'][0]['text'] = 'Changed event.'
            else:
                self.state['disclosure'][change] = 'other'
            self.save()
            self.reject(lambda: canon.forget_all(self.state))

    def test_legacy_load_does_not_create_generations(self):
        del self.state['disclosure']; self.save()
        with patch.object(canon.uuid, 'uuid4', side_effect=AssertionError('identity created')):
            self.assertNotIn('disclosure', canon.load_state())
            self.assertEqual(d.inspect_disclosure(self.state)['status'], 'absent')
            canon.resolve_fact(self.state, 2)
        self.assertNotIn('disclosure', self.state)

    def test_first_authorized_reset_creates_empty_envelope(self):
        for operation in (canon.forget_all, canon.reset_npc_state, canon.reset_npc_test_fixture):
            self.state = fixture(); del self.state['disclosure']; self.save()
            operation(self.state)
            self.assertEqual(self.state['disclosure']['records'], [])
            self.assertEqual(d.inspect_disclosure(self.state)['status'], 'valid')
            self.assertEqual(canon.load_state(), self.state)

    def test_world_reset_clears_and_rotates(self):
        previous = deepcopy(self.state['disclosure'])
        self.state['unrelated_extension'] = {'preserve': True}
        canon.forget_all(self.state)
        self.assertEqual(self.state['facts'], [])
        self.assertEqual(self.state['next_fact_id'], 1)
        self.assertEqual(self.state['npc'], canon.empty_npc_state())
        self.assertEqual(self.state['disclosure']['records'], [])
        self.assertNotEqual(self.state['disclosure']['world_generation'], previous['world_generation'])
        self.assertEqual(self.state['unrelated_extension'], {'preserve': True})
        self.assertEqual(canon.load_state(), self.state)

    def test_recreated_fact_ids_do_not_inherit_acquisitions(self):
        old = deepcopy(self.state['disclosure'])
        canon.forget_all(self.state)
        self.state['facts'] = fixture()['facts']; self.state['next_fact_id'] = 4
        self.state['npc'] = fixture()['npc']
        self.state['disclosure']['records'] = old['records']
        self.assertEqual(d.inspect_disclosure(self.state)['status'], 'invalid_reference')

    def test_npc_resets_keep_observation_history(self):
        for operation in (canon.reset_npc_state, canon.reset_npc_test_fixture):
            self.state = fixture(); self.save()
            previous = deepcopy(self.state)
            operation(self.state)
            envelope = self.state['disclosure']
            self.assertEqual(envelope['world_generation'], previous['disclosure']['world_generation'])
            self.assertNotEqual(envelope['npc_generation'], previous['disclosure']['npc_generation'])
            self.assertEqual(envelope['records'], previous['disclosure']['records'][1:])
            self.assertEqual(self.state['facts'][-2:], previous['facts'][-2:])
            self.assertEqual(canon.load_state(), self.state)
            self.assertEqual(d.inspect_disclosure(self.state)['status'], 'valid')
            if operation is canon.reset_npc_test_fixture:
                self.assertEqual(self.state['npc'], build_npc_fixture())
                self.assertNotIn(1, [f['id'] for f in self.state['facts']])
            else:
                self.assertEqual(self.state['facts'], previous['facts'])

    def test_generation_collision_rejected_without_retry(self):
        with patch.object(canon.uuid, 'uuid4', return_value='npc-1') as identity:
            self.reject(lambda: canon.reset_npc_state(self.state))
            self.assertEqual(identity.call_count, 1)

    def test_fixture_reset_is_one_complete_write(self):
        original = canon._save_npc_commit
        with patch.object(canon, '_save_npc_commit', wraps=original) as writer:
            canon.forget_all(self.state, foundation=TEST_FACTS)
            writer.assert_called_once()
        self.assertEqual([{k:f[k] for k in ('type','text')} for f in self.state['facts']], TEST_FACTS)
        self.assertEqual(self.state['disclosure']['records'], [])
        self.assertEqual(canon.load_state(), self.state)

    def test_invalid_fixture_rejected_before_write(self):
        self.reject(lambda: canon.forget_all(self.state, foundation=[{'text':'invented'}]))

    def test_persistence_failures_preserve_memory_and_disk(self):
        for operation in (canon.forget_all, canon.reset_npc_state, canon.reset_npc_test_fixture,
                          lambda s: canon.resolve_fact(s, 2),
                          lambda s: canon.forget_all(s, foundation=TEST_FACTS)):
            for target in ('canon.json.dump', 'canon.os.fsync', 'canon.os.replace'):
                self.state = fixture(); self.save()
                before, disk = deepcopy(self.state), self.path.read_bytes()
                with patch(target, side_effect=OSError('failed')):
                    with self.assertRaisesRegex(OSError, 'reconcile before retry'):
                        operation(self.state)
                self.assertEqual(self.state, before)
                self.assertEqual(self.path.read_bytes(), disk)

    def test_uncertain_replace_never_updates_memory_or_retries(self):
        original = canon.os.replace
        def replace_then_fail(source, target):
            original(source, target)
            raise OSError('uncertain')
        before = deepcopy(self.state)
        with patch.object(canon.os, 'replace', side_effect=replace_then_fail) as replace:
            with self.assertRaisesRegex(OSError, 'reconcile before retry'):
                canon.forget_all(self.state)
            replace.assert_called_once()
        self.assertEqual(self.state, before)
        persisted = canon.load_state()
        self.assertEqual(persisted['facts'], [])
        self.assertNotEqual(persisted['disclosure']['world_generation'], before['disclosure']['world_generation'])

    def test_selective_delete_failure_preserves_memory(self):
        del self.state['disclosure']; self.save()
        before = deepcopy(self.state)
        with patch.object(canon, '_save_npc_commit', side_effect=OSError('failed')):
            with self.assertRaisesRegex(OSError, 'reconcile'):
                canon.forget_fact(self.state, 2)
        self.assertEqual(self.state, before)
        self.assertEqual(canon.load_state(), before)

    def test_cli_rejections_and_atomic_fixture_reset(self):
        from test_observation import ObservationTests
        self.rng = Mock()
        _, output = ObservationTests.cli(self, ['/forget 3', '/resolve 3', '/forget 1', '/quit'])
        self.assertEqual(output.count('[rejected]'), 3)
        self.assertEqual(canon.load_state(), self.state)
        original = canon._save_npc_commit
        with patch.object(canon, '_save_npc_commit', wraps=original) as writer:
            namespace, output = ObservationTests.cli(self, ['/testreset', '/quit'])
            writer.assert_called_once()
        self.assertIn('[test fixture reset]', output)
        self.assertEqual(canon.load_state(), namespace['state'])
        self.assertEqual(len(namespace['state']['facts']), len(TEST_FACTS))

    def test_cli_uncertain_failure_stops_without_retry(self):
        from test_observation import ObservationTests
        self.rng = Mock()
        with patch.object(canon, '_save_npc_commit', side_effect=OSError('uncertain')) as writer:
            with self.assertRaisesRegex(OSError, 'reconcile'):
                ObservationTests.cli(self, ['/testreset', '/testreset'])
            writer.assert_called_once()

    def test_rejected_marker_edits_preserve_no_reroll_after_reload(self):
        del self.state['disclosure']
        self.state['facts'].append({'id':4,'type':'state','text':'The player is in the study.','status':'active'})
        self.state['next_fact_id'] = 5; self.save()
        for operation in (canon.forget_fact, canon.resolve_fact):
            self.reject(lambda: operation(self.state, 3))
        config={'policy':'observation_v1','rooms':deepcopy(map_data.ROOMS),
                'discoveries':deepcopy(collapse.OBSERVATION_DISCOVERIES)}
        from observation_activation import activate_observation
        rng = Mock(random=Mock(side_effect=AssertionError('reroll')))
        result = activate_observation(canon.load_state(), 'study','study_desk','search',config,rng)
        self.assertEqual(result['status'], 'no_change')
        rng.random.assert_not_called()


if __name__ == '__main__':
    unittest.main()
