"""Player acquisition authorization and complete observation snapshot tests."""
from copy import deepcopy
import hashlib
import json
import os
import unittest
from unittest.mock import patch

import canon
import disclosure_rules as d
import test_observation as observation_tests
from test_disclosure import fixture


class ObservationAcquisitionTests(unittest.TestCase):
    setUp = observation_tests.ObservationTests.setUp
    proposal = observation_tests.ObservationTests.proposal
    activate = observation_tests.ObservationTests.activate
    reject = observation_tests.ObservationTests.reject

    def record(self):
        return self.state['disclosure']['records'][-1]

    def test_atomic_snapshot_and_exact_bindings(self):
        before = deepcopy(self.state)
        save = canon._save_npc_commit
        def check(pending):
            self.assertEqual(self.state, before)
            self.assertEqual(d.inspect_disclosure(pending)['status'], 'valid')
            self.assertEqual(len(pending['disclosure']['records']), 1)
            save(pending)
            self.assertEqual(self.state, before)
        with patch.object(canon, '_save_npc_commit', side_effect=check) as writer:
            result = self.activate()
        self.assertEqual(result['status'], 'committed')
        writer.assert_called_once()
        record = self.record()
        self.assertEqual(set(record), {'version','audience','scope','policy','reference','source'})
        self.assertEqual(record['audience'], 'player')
        self.assertEqual(record['policy'], 'player_observation_v1')
        self.assertEqual(record['source'], {
            'kind':'player_observation','room_id':'study','observation_id':'study_desk',
            'verb':'search','discovery_id':'brass_key','observation_policy':'observation_v1',
            'configuration_sha256':hashlib.sha256(json.dumps(self.config, sort_keys=True,
                separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()).hexdigest()})
        self.assertEqual(record['reference']['world_generation'], self.state['disclosure']['world_generation'])
        self.assertEqual(record['reference']['reveal_fact_id'], 2)
        self.assertEqual(record['reference']['collapse_fact_id'], 3)
        payload = {k:record[k] for k in ('version','audience','scope','policy','source')}
        payload.update(world_generation=record['reference']['world_generation'],
            reveal={k:result['facts'][0][k] for k in ('id','type','text')},
            collapse={k:result['facts'][1][k] for k in ('id','type','text')})
        self.assertEqual(record['reference']['content_sha256'], hashlib.sha256(json.dumps(payload,
            sort_keys=True,separators=(',', ':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest())
        self.assertEqual(canon.load_state(), self.state)
        self.rng.random.assert_called_once()

    def test_existing_generations_and_npc_acquisition_preserved(self):
        previous = fixture()
        self.state['facts'].append(previous['facts'][0] | {'id': 4})
        self.state['next_fact_id'] = 5
        self.state['npc'] = previous['npc']
        self.state['npc']['resolutions']['morning']['event_id'] = 4
        npc = previous['disclosure']['records'][0]
        npc['reference']['event_id'] = 4
        npc['reference']['content_sha256'] = d.npc_content_sha256('morning',
            {k:self.state['facts'][1][k] for k in ('id','type','text')}, 'conversation')
        self.state['disclosure'] = previous['disclosure'] | {'records':[npc]}
        before = deepcopy(self.state['disclosure'])
        with patch.object(canon.uuid, 'uuid4', side_effect=AssertionError('generation rotated')):
            self.assertEqual(self.activate()['status'], 'committed')
        self.assertEqual(self.state['disclosure']['records'][0], before['records'][0])
        self.assertEqual(self.state['disclosure']['world_generation'], before['world_generation'])
        self.assertEqual(self.state['disclosure']['npc_generation'], before['npc_generation'])

    def test_caller_provenance_and_stale_bases_reject(self):
        for key in ('source','audience','reference','acquisition'):
            proposal = self.proposal(); proposal[key] = {'forged':True}
            self.reject(proposal)
        proposal = self.proposal(); self.config['discoveries'][0]['weight'] += 1
        self.reject(proposal)
        proposal = self.proposal(); self.state['next_fact_id'] += 1
        self.reject(proposal)
        self.assertNotIn('disclosure', self.state)

    def test_matching_basis_still_requires_player_presence(self):
        self.state['facts'][0]['text'] = 'The player is in the foyer.'
        self.reject(self.proposal())

    def test_acquisition_authorization_rejects_forged_pending_facts(self):
        proposal = self.proposal()
        effects = observation_tests.validate_observation(self.state, proposal, self.config)
        facts = [dict(effect, id=2+i, status='active') for i,effect in enumerate(effects)]
        for key, value in [('id',1),('text','A fabricated discovery.'),('status','resolved')]:
            forged = deepcopy(facts); forged[0][key] = value
            with self.assertRaises(ValueError):
                d.authorize_observation_acquisition(self.state,proposal,self.config,*forged,'world')
        before = deepcopy((self.state,proposal,self.config,facts))
        record = d.authorize_observation_acquisition(self.state,proposal,self.config,*facts,'world')
        self.assertEqual(record['source']['discovery_id'], 'brass_key')
        self.assertEqual((self.state,proposal,self.config,facts), before)

    def test_acquisition_authorization_failure_leaves_no_partial_truth(self):
        before, disk = deepcopy(self.state), self.path.read_bytes()
        with patch.object(d, 'authorize_observation_acquisition', side_effect=ValueError('not authorized')), \
                patch.object(canon, '_save_npc_commit') as writer:
            result = self.activate()
        self.assertEqual(result['status'], 'rejected')
        self.assertEqual(result['facts'], [])
        writer.assert_not_called()
        self.assertEqual(self.state, before)
        self.assertEqual(self.path.read_bytes(), disk)

    def test_pending_snapshot_validation_rejects_broken_record(self):
        authorize = d.authorize_observation_acquisition
        def corrupt(*args):
            record = authorize(*args)
            record['reference']['content_sha256'] = '0' * 64
            return record
        before, disk = deepcopy(self.state), self.path.read_bytes()
        with patch.object(d, 'authorize_observation_acquisition', side_effect=corrupt), \
                patch.object(canon, '_save_npc_commit') as writer:
            result = self.activate()
        self.assertEqual(result['status'], 'rejected')
        writer.assert_not_called()
        self.assertEqual(self.state, before)
        self.assertEqual(self.path.read_bytes(), disk)

    def test_corrupt_disclosure_rejects_before_sampling(self):
        for envelope in (None, {'version':2}, {'version':1,'world_generation':'w','npc_generation':'n',
                                                'records':[{'scope':'unknown'}]}):
            self.state['disclosure'] = envelope
            before = deepcopy(self.state)
            with patch.object(canon, '_save_npc_commit') as writer:
                self.assertEqual(self.activate()['status'], 'rejected')
            writer.assert_not_called()
            self.rng.random.assert_not_called()
            self.assertEqual(self.state, before)
            self.reject(self.proposal())

    def test_damaged_modern_marker_cannot_reroll(self):
        self.activate()
        self.state['facts'] = [f for f in self.state['facts'] if f['id'] != 3]
        before = deepcopy(self.state); self.rng.random.reset_mock()
        self.assertEqual(self.activate()['status'], 'rejected')
        self.rng.random.assert_not_called()
        self.assertEqual(self.state, before)

    def test_duplicate_records_reject_without_sampling(self):
        self.activate(); self.rng.random.reset_mock()
        self.state['disclosure']['records'].append(deepcopy(self.record()))
        self.assertEqual(self.activate()['status'], 'rejected')
        self.rng.random.assert_not_called()

    def test_null_and_legacy_marker_do_not_create_generations(self):
        for obj in ('brass key', 'letter opener', 'ink bottle'):
            canon.add_fact(self.state, f'The {obj} is in the foyer.')
        with patch.object(canon.uuid, 'uuid4', side_effect=AssertionError('created identity')):
            self.assertEqual(self.activate()['status'], 'no_change')
            canon.add_fact(self.state, 'The search space study_desk:search collapsed.', 'collapse')
            self.assertEqual(self.activate()['status'], 'no_change')
        self.assertNotIn('disclosure', self.state)
        self.rng.random.assert_not_called()

    def test_repeat_reload_retains_one_record_without_redraw(self):
        self.activate(); self.state = canon.load_state()
        before = deepcopy(self.state); self.rng.random.reset_mock()
        self.assertEqual(self.activate()['status'], 'no_change')
        self.assertEqual(self.state, before)
        self.assertEqual(len(self.state['disclosure']['records']), 1)
        self.rng.random.assert_not_called()

    def test_historical_validation_after_configuration_removal_and_status_changes(self):
        self.activate(); record = deepcopy(self.record())
        self.config.clear()
        canon.add_fact(self.state, 'The brass key is in the foyer.', 'state')
        self.assertEqual(self.state['facts'][1]['status'], 'superseded')
        self.assertEqual(d.inspect_disclosure(canon.load_state())['status'], 'valid')
        canon.resolve_fact(self.state, 2)
        self.assertEqual(d.inspect_disclosure(canon.load_state())['status'], 'valid')
        self.assertEqual(self.record(), record)
        self.assertEqual(self.state['facts'][1]['text'], 'The brass key is in the study.')

    def test_failure_never_exposes_or_retains_partial_unit(self):
        for target in ('canon.json.dump','canon.os.fsync','canon.os.replace'):
            before, disk = deepcopy(self.state), self.path.read_bytes()
            with patch(target, side_effect=OSError('failed')):
                result = self.activate()
            self.assertEqual(result['status'], 'failed')
            self.assertEqual(result['facts'], [])
            self.assertEqual(self.state, before)
            self.assertEqual(self.path.read_bytes(), disk)
            self.assertNotIn('disclosure', self.state)

    def test_uncertain_write_reconciles_complete_unit_without_retry(self):
        original = os.replace; before = deepcopy(self.state)
        def uncertain(source, target):
            original(source,target)
            raise OSError('lost acknowledgment')
        with patch.object(canon.os,'replace',side_effect=uncertain) as writer:
            result = self.activate()
            writer.assert_called_once()
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(result['facts'], [])
        self.assertEqual(self.state, before)
        self.assertIn('reconcile', result['reason'])
        self.state = canon.load_state()
        self.assertEqual(d.inspect_disclosure(self.state)['status'], 'valid')
        self.assertEqual(len(self.state['disclosure']['records']), 1)
        self.rng.random.reset_mock()
        self.assertEqual(self.activate()['status'], 'no_change')
        self.rng.random.assert_not_called()


if __name__ == '__main__':
    unittest.main()
