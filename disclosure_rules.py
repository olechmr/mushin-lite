"""Pure validation of canon-owned acquisition history, never acquisition authority.

No configuration/provider lookup, I/O, sampling, generation creation, or writes.
Inspection returns indices and diagnostics, not player-facing content. Hashes are
consistency checks under the trusted-save boundary, not signatures.
"""
import hashlib
import json
import math

POLICIES = {'episode_outcome': 'truthful_npc_inquiry_v1',
            'observation_discovery': 'player_observation_v1'}
STATUSES = ('active', 'superseded', 'resolved')


def _require(condition, reason, status='malformed'):
    if not condition:
        raise ValueError(status + ':' + reason)


def _json_value(value):
    if value is None or type(value) in (str, bool, int):
        return
    if type(value) is float:
        _require(math.isfinite(value), 'nonfinite_number')
    elif type(value) is list:
        for item in value:
            _json_value(item)
    elif type(value) is dict:
        _require(all(type(k) is str for k in value), 'nonstring_key')
        for item in value.values():
            _json_value(item)
    else:
        raise ValueError('malformed:non_json_value')


def canonical_json(value):
    """Exact contract encoding. Already-decoded dicts cannot expose lost duplicates."""
    _json_value(value)
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=False, allow_nan=False).encode('utf-8')


def content_sha256(value):
    return hashlib.sha256(canonical_json(value)).hexdigest()


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result, 'duplicate_json_key')
        result[key] = value
    return result


def decode_disclosure_state(text):
    """Decode a save without mutation; strict JSON for disclosure-bearing saves.

    Retain legacy JSON loading behavior when the extension is absent. Call
    inspect_disclosure on the result before applying legacy load defaults.
    """
    state = json.loads(text)
    if isinstance(state, dict) and 'disclosure' in state:
        state = json.loads(text, object_pairs_hook=_unique_object)
        canonical_json(state)
    return state


def _fields(value, fields):
    _require(type(value) is dict and set(value) == set(fields), 'fields')


def _identity(value):
    _require(type(value) is str and bool(value) and value == value.strip()
             and value.lower() not in ('none', 'unknown'), 'identity')


def _id(value):
    _require(type(value) is int and value > 0, 'fact_id')


def _digest(value):
    _require(type(value) is str and len(value) == 64
             and all(c in '0123456789abcdef' for c in value), 'digest')


def _version(value):
    _require(type(value) is int, 'version_type')
    _require(value == 1, 'version', 'unsupported')


def _record_shape(record):
    _fields(record, ('version', 'audience', 'scope', 'policy', 'reference', 'source'))
    _version(record['version'])
    for key in ('audience', 'scope', 'policy'):
        _require(type(record[key]) is str, key + '_type')
    _require(record['audience'] == 'player', 'audience', 'unsupported')
    scope = record['scope']
    _require(scope in POLICIES, 'scope', 'unsupported')
    _require(record['policy'] == POLICIES[scope], 'policy', 'unsupported')
    ref, source = record['reference'], record['source']
    if scope == 'episode_outcome':
        _fields(ref, ('world_generation', 'npc_generation', 'episode_id', 'event_id', 'content_sha256'))
        _fields(source, ('inquiry_binding', 'respondent_id'))
        for value in source.values():
            _identity(value)
        _identity(ref['npc_generation']); _identity(ref['episode_id']); _id(ref['event_id'])
    else:
        _fields(ref, ('world_generation', 'reveal_fact_id', 'collapse_fact_id', 'content_sha256'))
        _fields(source, ('kind', 'room_id', 'observation_id', 'verb', 'discovery_id',
                         'observation_policy', 'configuration_sha256'))
        for key in ('room_id', 'observation_id', 'discovery_id'):
            _identity(source[key])
        _require(source['kind'] == 'player_observation', 'source_kind', 'unsupported')
        _require(source['observation_policy'] == 'observation_v1', 'observation_policy', 'unsupported')
        _require(source['verb'] in ('search', 'inspect'), 'verb', 'unsupported')
        _digest(source['configuration_sha256'])
        _id(ref['reveal_fact_id']); _id(ref['collapse_fact_id'])
        _require(ref['reveal_fact_id'] != ref['collapse_fact_id'], 'same_fact_reference')
    _identity(ref['world_generation']); _digest(ref['content_sha256'])


def _key(record):
    ref, source = record['reference'], record['source']
    prefix = (record['audience'], record['scope'], ref['world_generation'])
    if record['scope'] == 'observation_discovery':
        return prefix + (source['observation_id'], source['verb'])
    return prefix + (ref['npc_generation'], ref['episode_id'], canonical_json(source))


def _fact(state, fact_id, kinds, statuses=STATUSES):
    facts = state.get('facts')
    _require(type(facts) is list, 'facts', 'invalid_reference')
    matches = [f for f in facts if type(f) is dict and f.get('id') == fact_id]
    _require(len(matches) == 1, 'missing_or_duplicate_fact', 'invalid_reference')
    fact = matches[0]
    _require(type(fact.get('id')) is int and fact.get('type') in kinds
             and fact.get('status') in statuses and type(fact.get('text')) is str
             and bool(fact['text'].strip()), 'fact_content_or_status', 'invalid_reference')
    return {k: fact[k] for k in ('id', 'type', 'text')}


def npc_content_sha256(episode_id, event, outcome):
    return content_sha256({'episode_id': episode_id, 'event': event, 'outcome': outcome})


def observation_content_sha256(record, reveal, collapse):
    return content_sha256({**{k: record[k] for k in ('version', 'audience', 'scope', 'policy', 'source')},
                           'world_generation': record['reference']['world_generation'],
                           'reveal': reveal, 'collapse': collapse})


def _references(state, envelope, record):
    ref = record['reference']
    _require(ref['world_generation'] == envelope['world_generation'], 'world_generation', 'invalid_reference')
    if record['scope'] == 'episode_outcome':
        _require(ref['npc_generation'] == envelope['npc_generation'], 'npc_generation', 'invalid_reference')
        npc = state.get('npc')
        _require(type(npc) is dict and type(npc.get('version')) is int
                 and npc['version'] == 1 and type(npc.get('resolutions')) is dict,
                 'npc_history', 'invalid_reference')
        resolutions = npc['resolutions']
        resolution = resolutions.get(ref['episode_id'])
        _require(type(resolution) is dict and type(resolution.get('event_id')) is int
                 and resolution['event_id'] == ref['event_id']
                 and resolution.get('outcome') in ('no_interaction', 'conversation', 'disagreement'),
                 'resolution', 'invalid_reference')
        _require(sum(type(r) is dict and r.get('event_id') == ref['event_id']
                     for r in resolutions.values()) == 1, 'shared_episode_event', 'invalid_reference')
        event = _fact(state, ref['event_id'], ('event',))
        digest = npc_content_sha256(ref['episode_id'], event, resolution['outcome'])
    else:
        reveal = _fact(state, ref['reveal_fact_id'], ('state', 'event'))
        marker = _fact(state, ref['collapse_fact_id'], ('collapse',), ('active',))
        source = record['source']
        _require(marker['text'] == f"The search space {source['observation_id']}:{source['verb']} collapsed.",
                 'collapse_binding', 'invalid_reference')
        digest = observation_content_sha256(record, reveal, marker)
    _require(digest == ref['content_sha256'], 'content_digest', 'invalid_reference')


def _error(error):
    text = str(error)
    status, _, reason = text.partition(':')
    if status not in ('malformed', 'unsupported', 'invalid_reference'):
        return {'status': 'malformed', 'reason': 'invalid_input'}
    return {'status': status, 'reason': reason}


def inspect_disclosure(state):
    """Return status, per-record diagnostics and valid indices, without granting.

    Structural/unsupported/duplicate failures suppress all valid indices.
    Broken individual references retain other valid indices, but overall status
    remains invalid_reference, so a future writer must reject the entire write.
    """
    results = []
    try:
        _require(type(state) is dict, 'state')
        if 'disclosure' not in state:
            return {'status': 'absent', 'records': [], 'valid_indices': []}
        envelope = state['disclosure']
        canonical_json(envelope)
        _fields(envelope, ('version', 'world_generation', 'npc_generation', 'records'))
        _version(envelope['version'])
        _identity(envelope['world_generation']); _identity(envelope['npc_generation'])
        _require(type(envelope['records']) is list, 'records')
        keys = set()
        for record in envelope['records']:
            _record_shape(record)
            key = _key(record)
            _require(key not in keys, 'duplicate_record')
            keys.add(key)
        for record in envelope['records']:
            try:
                _references(state, envelope, record)
                results.append({'status': 'valid'})
            except (ValueError, TypeError, KeyError, RecursionError, UnicodeError) as error:
                results.append(_error(error))
        valid = [i for i, result in enumerate(results) if result['status'] == 'valid']
        return {'status': 'valid' if len(valid) == len(results) else 'invalid_reference',
                'records': results, 'valid_indices': valid}
    except (ValueError, TypeError, KeyError, RecursionError, UnicodeError) as error:
        return {**_error(error), 'records': [], 'valid_indices': []}


def recognize_acquisition(state, record):
    """Recognize only an identical stored valid acquisition; never authorize new ones."""
    inspection = inspect_disclosure(state)
    if inspection['status'] not in ('valid', 'absent'):
        return {'status': 'rejected', 'reason': inspection['status']}
    try:
        canonical_json(record)
        _record_shape(record)
        key = _key(record)
        for index, existing in enumerate(state.get('disclosure', {}).get('records', [])):
            if _key(existing) == key:
                if canonical_json(existing) == canonical_json(record):
                    return {'status': 'reused', 'index': index}
                return {'status': 'conflict'}
        return {'status': 'not_found'}
    except (ValueError, TypeError, KeyError, RecursionError, UnicodeError) as error:
        return {**_error(error)}
