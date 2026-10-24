"""Regression coverage for pure, canon-owned disclosure history validation."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import canon
import disclosure_rules as d


def fixture():
    state = {'facts': [
        {'id': 1, 'type': 'event', 'text': 'Heidi and Chris talked during the morning.', 'status': 'active'},
        {'id': 2, 'type': 'state', 'text': 'The brass key is in the study.', 'status': 'active'},
        {'id': 3, 'type': 'collapse', 'text': 'The search space study_desk:search collapsed.', 'status': 'active'}],
        'next_fact_id': 4,
        'npc': {'version': 1, 'entities': {}, 'episodes': {},
                'resolutions': {'morning': {'outcome': 'conversation', 'event_id': 1}}},
        'disclosure': {'version': 1, 'world_generation': 'world-1', 'npc_generation': 'npc-1', 'records': []}}
    payloads = [{k: f[k] for k in ('id', 'type', 'text')} for f in state['facts']]
    npc = {'version': 1, 'audience': 'player', 'scope': 'episode_outcome', 'policy': 'truthful_npc_inquiry_v1',
           'reference': {'world_generation': 'world-1', 'npc_generation': 'npc-1', 'episode_id': 'morning',
                         'event_id': 1, 'content_sha256': d.npc_content_sha256('morning', payloads[0], 'conversation')},
           'source': {'inquiry_binding': 'ask heidi about chris', 'respondent_id': 'heidi'}}
    observation = {'version': 1, 'audience': 'player', 'scope': 'observation_discovery', 'policy': 'player_observation_v1',
                   'reference': {'world_generation': 'world-1', 'reveal_fact_id': 2, 'collapse_fact_id': 3},
                   'source': {'kind': 'player_observation', 'room_id': 'study', 'observation_id': 'study_desk',
                              'verb': 'search', 'discovery_id': 'brass_key', 'observation_policy': 'observation_v1',
                              'configuration_sha256': d.content_sha256({'policy': 'observation_v1'})}}
    observation['reference']['content_sha256'] = d.observation_content_sha256(observation, payloads[1], payloads[2])
    state['disclosure']['records'] = [npc, observation]
    return state


class DisclosureTests(unittest.TestCase):
    def setUp(self):
        self.state = fixture()

    def check(self, status, state=None):
        state = self.state if state is None else state
        before = deepcopy(state)
        result = d.inspect_disclosure(state)
        self.assertEqual(result['status'], status, result)
        self.assertEqual(state, before)
        return result

    def test_valid_variants_and_mixed_envelope(self):
        self.assertEqual(self.check('valid')['valid_indices'], [0, 1])
        for record in self.state['disclosure']['records']:
            state = deepcopy(self.state); state['disclosure']['records'] = [record]
            self.check('valid', state)

    def test_canonical_encoding_and_known_hash(self):
        self.assertEqual(d.canonical_json({'z': 1.0, 'a': ['é', 1, True, None]}),
                         '{"a":["é",1,true,null],"z":1.0}'.encode())
        self.assertEqual(d.content_sha256({}), '44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a')
        self.assertNotEqual(d.content_sha256(1), d.content_sha256(1.0))
        self.assertNotEqual(d.content_sha256('é'), d.content_sha256('e\u0301'))

    def test_exact_digest_payloads(self):
        npc, obs = self.state['disclosure']['records']
        facts = [{k: f[k] for k in ('id', 'type', 'text')} for f in self.state['facts']]
        expected = {'episode_id': 'morning', 'event': facts[0], 'outcome': 'conversation'}
        raw = json.dumps(expected, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()
        self.assertEqual(npc['reference']['content_sha256'], hashlib.sha256(raw).hexdigest())
        expected = {k: obs[k] for k in ('version', 'audience', 'scope', 'policy', 'source')}
        expected.update(world_generation='world-1', reveal=facts[1], collapse=facts[2])
        raw = json.dumps(expected, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()
        self.assertEqual(obs['reference']['content_sha256'], hashlib.sha256(raw).hexdigest())

    def test_non_json_and_nonfinite_values(self):
        for value in [float('nan'), float('inf'), {1: 'x'}, (1, 2), object()]:
            with self.assertRaises(ValueError):
                d.canonical_json(value)
        cycle = []; cycle.append(cycle)
        self.state['disclosure']['records'] = cycle
        self.assertEqual(d.inspect_disclosure(self.state)['status'], 'malformed')

    def test_missing_extension_is_not_initialized(self):
        del self.state['disclosure']
        self.check('absent')
        self.assertNotIn('disclosure', self.state)

    def test_exact_fields(self):
        for path in [(), ('records', 0), ('records', 0, 'source'), ('records', 1, 'reference')]:
            state = deepcopy(self.state); target = state['disclosure']
            for key in path: target = target[key]
            target['extra'] = True
            self.check('malformed', state)
        self.state['disclosure'] = None
        self.check('malformed')

    def test_unsupported_versions_and_variants(self):
        for key, value in [('version', 2), ('audience', 'npc'), ('scope', 'belief'), ('policy', 'other')]:
            state = deepcopy(self.state); state['disclosure']['records'][0][key] = value
            self.check('unsupported', state)
        self.state['disclosure']['version'] = 2
        self.check('unsupported')

    def test_version_and_id_booleans_are_malformed(self):
        self.state['disclosure']['version'] = True
        self.check('malformed')
        self.state = fixture(); self.state['disclosure']['records'][0]['reference']['event_id'] = True
        self.check('malformed')

    def test_npc_source_identity(self):
        for key in ('inquiry_binding', 'respondent_id'):
            for value in ('', ' ', ' heidi', 'heidi ', 'UNKNOWN', None, 1):
                state = deepcopy(self.state); state['disclosure']['records'][0]['source'][key] = value
                self.check('malformed', state)
        self.state['disclosure']['records'][0]['source'].pop('respondent_id')
        self.check('malformed')

    def test_observation_source_and_digest_encoding(self):
        for key, value, status in [('verb', 'look', 'unsupported'), ('kind', 'llm', 'unsupported'),
                                    ('observation_policy', 'v2', 'unsupported'), ('room_id', '', 'malformed'),
                                    ('configuration_sha256', 'F' * 64, 'malformed')]:
            state = deepcopy(self.state); state['disclosure']['records'][1]['source'][key] = value
            self.check(status, state)

    def test_missing_and_duplicate_referenced_facts(self):
        for index in range(3):
            state = deepcopy(self.state); state['facts'].pop(index)
            self.check('invalid_reference', state)
            state = deepcopy(self.state); state['facts'].append(deepcopy(state['facts'][index]))
            self.check('invalid_reference', state)

    def test_changed_content_and_source(self):
        for index in range(3):
            state = deepcopy(self.state); state['facts'][index]['text'] += ' forged'
            self.check('invalid_reference', state)
        self.state['disclosure']['records'][1]['source']['discovery_id'] = 'other'
        self.check('invalid_reference')

    def test_generation_mismatch(self):
        for key in ('world_generation', 'npc_generation'):
            state = deepcopy(self.state); state['disclosure'][key] = 'reset-generation'
            self.check('invalid_reference', state)

    def test_all_historical_reveal_and_npc_statuses(self):
        for status in ('active', 'superseded', 'resolved'):
            self.state['facts'][0]['status'] = status
            self.state['facts'][1]['status'] = status
            self.check('valid')

    def test_invalid_and_missing_statuses(self):
        for index in range(3):
            for status in (None, '', 'deleted', [], 1):
                state = deepcopy(self.state); state['facts'][index]['status'] = status
                self.check('invalid_reference', state)
            state = deepcopy(self.state); del state['facts'][index]['status']
            self.check('invalid_reference', state)
        for status in ('superseded', 'resolved'):
            self.state['facts'][2]['status'] = status
            self.check('invalid_reference')

    def test_resolution_consistency_and_shared_events(self):
        for change in ({'event_id': 2}, {'outcome': 'disagreement'}, {'outcome': 'invented'}):
            state = deepcopy(self.state); state['npc']['resolutions']['morning'].update(change)
            self.check('invalid_reference', state)
        self.state['npc']['resolutions']['other'] = {'event_id': 1, 'outcome': 'conversation'}
        self.check('invalid_reference')

    def test_no_current_provider_or_configuration_required(self):
        self.state['npc'].pop('entities'); self.state['npc'].pop('episodes')
        self.state['npc']['resolutions']['morning']['disagreement_initiator'] = 'later-refinement'
        self.state['current_configuration'] = {'removed': True}
        self.check('valid')

    def test_superseding_fact_does_not_transfer_reference(self):
        self.state['facts'][1]['status'] = 'superseded'
        self.state['facts'].append({'id': 4, 'type': 'state', 'text': 'The brass key is in the foyer.', 'status': 'active'})
        self.check('valid')
        self.state['disclosure']['records'][1]['reference']['reveal_fact_id'] = 4
        self.check('invalid_reference')

    def test_duplicate_records_rejected(self):
        for index in (0, 1):
            state = deepcopy(self.state)
            state['disclosure']['records'].append(deepcopy(state['disclosure']['records'][index]))
            self.assertEqual(self.check('malformed', state)['valid_indices'], [])
        duplicate = deepcopy(self.state['disclosure']['records'][1]); duplicate['source']['room_id'] = 'other'
        self.state['disclosure']['records'].append(duplicate)
        self.check('malformed')

    def test_idempotent_recognition_and_conflict(self):
        before = deepcopy(self.state); record = self.state['disclosure']['records'][1]
        self.assertEqual(d.recognize_acquisition(self.state, deepcopy(record)), {'status': 'reused', 'index': 1})
        forged = deepcopy(record); forged['reference']['content_sha256'] = '0' * 64
        self.assertEqual(d.recognize_acquisition(self.state, forged)['status'], 'conflict')
        self.assertEqual(d.recognize_acquisition({}, record)['status'], 'not_found')
        self.assertEqual(self.state, before)

    def test_broken_reference_retains_valid_indices_but_blocks_reuse(self):
        self.state['facts'][1]['text'] = 'changed'
        result = self.check('invalid_reference')
        self.assertEqual(result['valid_indices'], [0])
        self.assertEqual(d.recognize_acquisition(self.state, self.state['disclosure']['records'][0])['status'], 'rejected')

    def test_unknown_variant_suppresses_all_history(self):
        self.state['disclosure']['records'][1]['scope'] = 'unknown'
        self.assertEqual(self.check('unsupported')['valid_indices'], [])

    def test_decode_duplicate_json_keys(self):
        raw = json.dumps(self.state).replace('"world_generation": "world-1"',
                                            '"world_generation": "world-1", "world_generation": "world-1"', 1)
        with self.assertRaises(ValueError): d.decode_disclosure_state(raw)
        self.assertEqual(d.decode_disclosure_state(json.dumps(self.state)), self.state)

    def test_load_preserves_legacy_and_valid_history_without_writes(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(canon, 'STATE_FILE', str(Path(tmp) / 'state.json')):
            for state in (self.state, {k: v for k, v in self.state.items() if k != 'disclosure'}):
                path = Path(canon.STATE_FILE); path.write_text(json.dumps(state)); before = path.read_bytes()
                self.assertEqual(canon.load_state(), state)
                self.assertEqual(path.read_bytes(), before)

    def test_load_rejects_corruption_before_legacy_defaults(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(canon, 'STATE_FILE', str(Path(tmp) / 'state.json')):
            cases = []
            state = deepcopy(self.state); del state['facts'][0]['status']; cases.append(state)
            state = deepcopy(self.state); state['disclosure']['version'] = 2; cases.append(state)
            state = deepcopy(self.state); state['disclosure'] = None; cases.append(state)
            for state in cases:
                path = Path(canon.STATE_FILE); path.write_text(json.dumps(state)); before = path.read_bytes()
                with self.assertRaises(ValueError): canon.load_state()
                self.assertEqual(path.read_bytes(), before)

    def test_import_and_validation_without_producers_or_sampling(self):
        code = '''
import sys
for name in ('canon', 'collapse', 'behavior', 'npc_fixture', 'renderer', 'llm_adapter', 'random', 'observation_activation'):
    sys.modules[name] = None
import disclosure_rules as d
assert d.inspect_disclosure({})['status'] == 'absent'
assert d.inspect_disclosure(STATE)['status'] == 'valid'
'''.replace('STATE', repr(self.state))
        subprocess.run([sys.executable, '-c', code], cwd=Path(__file__).parent, check=True, capture_output=True)


if __name__ == '__main__':
    unittest.main()
