import hashlib

OBSERVATION_DISCOVERIES = [
    {
        "id": "brass_key",
        "tags": ["desk"],
        "verbs": ["search"],
        "weight": 1.0,
        "reveal": {
            "type": "state",
            "text": "The brass key is in the {room_id}.",
        },
    },
    {
        "id": "letter_opener",
        "tags": ["desk"],
        "verbs": ["search"],
        "weight": 3.0,
        "reveal": {
            "type": "state",
            "text": "The letter opener is in the {room_id}.",
        },
    },
    {
        "id": "ink_bottle",
        "tags": ["desk"],
        "verbs": ["search"],
        "weight": 2.0,
        "reveal": {
            "type": "state",
            "text": "The ink bottle is in the {room_id}.",
        },
    },
    {
        "id": "disturbed_books",
        "tags": ["bookshelf"],
        "verbs": ["search"],
        "category": "historical_evidence",
        "cause": {
            "action": "search",
            "actor": "unknown",
            "time": "recent",
        },
        "reveal": {
            "type": "event",
            "text": "Someone searched these shelves recently.",
        },
    },
    {
        "id": "cold_fireplace",
        "tags": ["fireplace"],
        "verbs": ["search"],
        "category": "environmental_evidence",
        "cause": {
            "action": "disuse",
            "actor": None,
            "time": "long_term",
        },
        "reveal": {
            "type": "state",
            "text": "The fireplace has not been used in years.",
        },
    },

    {
        "id": "loose_stone",
        "tags": ["fireplace"],
        "verbs": ["inspect"],
        "weight": 1.0,
        "category": "structural_evidence",
        "reveal": {
            "type": "state",
            "text": "One of the fireplace stones feels slightly loose.",
        },
    },
    {
        "id": "misaligned_drawer",
        "tags": ["desk"],
        "verbs": ["inspect"],
        "weight": 1.0,
        "category": "structural_evidence",
        "reveal": {
            "type": "state",
            "text": "One of the desk drawers does not sit flush.",
        },
    },
    {
    "id": "missing_book_outline",
    "tags": ["bookshelf"],
    "verbs": ["inspect"],
    "weight": 1.0,
    "category": "visual_evidence",
    "reveal": {
        "type": "state",
        "text": "A clean rectangular outline in the dust shows that one book is missing.",
    },
},
]

def candidate_matches(candidate, constraints, verb=None):
    tags = candidate.get("tags", [])
    required_tags = constraints.get("required_tags", [])
    supported_verbs = candidate.get("verbs", [])

    if verb is not None and verb not in supported_verbs:
        return False

    return all(
        tag in tags
        for tag in required_tags
    )

def select_candidate(
    candidates,
    room_id,
    observation_space,
    verb="search",
):

    seed_text = "|".join([
        observation_space.get("id", room_id),
        verb,
        str(observation_space.get("constraints", {})),
    ])

    digest = hashlib.sha256(seed_text.encode("utf-8")).hexdigest()

    total_weight = sum(
        max(float(candidate.get("weight", 1.0)), 0.0)
        for candidate in candidates
    )

    if total_weight <= 0:
        return None

    roll = (
        int(digest, 16)
        / ((1 << 256) - 1)
    ) * total_weight

    cumulative_weight = 0.0

    for candidate in candidates:
        weight = max(float(candidate.get("weight", 1.0)), 0.0)
        cumulative_weight += weight

        if roll < cumulative_weight:
            return candidate

    return candidates[-1]

def is_observation_collapsed(
    facts,
    observation_id,
    verb="search",
):
    if not observation_id:
        return False

    marker = (
        f"The search space "
        f"{observation_id}:{verb} "
        f"collapsed."
    )

    return any(
        fact.get("status", "active") == "active"
        and fact.get("text", "").lower().strip().rstrip(".")
        == marker.lower().strip().rstrip(".")
        for fact in facts
    )

def build_discovery_packet(candidate, room_id):
    reveal = candidate.get("reveal", {})

    fact_type = reveal.get("type", "state")
    text_template = reveal.get("text", "")

    if not text_template:
        return None

    result = {
        "type": fact_type,
        "text": text_template.format(room_id=room_id),
        "discovery_id": candidate.get("id"),
    }

    if candidate.get("category") is not None:
        result["category"] = candidate["category"]

    if candidate.get("cause") is not None:
        result["cause"] = candidate["cause"]

    return result

def preview_observation(
    room_id,
    observation_space,
    facts,
    verb="search",
):

    if not observation_space:
        return None

    observation_id = observation_space.get("id")

    if is_observation_collapsed(
        facts,
        observation_id,
        verb,
    ):
        return None

    constraints = observation_space.get("constraints", {})

    discoveries = [
        discovery
        for discovery in OBSERVATION_DISCOVERIES
        if candidate_matches(discovery, constraints, verb)
    ]

    available_discoveries = []

    for discovery in discoveries:
        packet = build_discovery_packet(discovery, room_id)

        if packet is None:
            continue

        already_present = any(
            fact.get("status", "active") == "active"
            and fact.get("text") == packet["text"]
            for fact in facts
        )

        if not already_present:
            available_discoveries.append(discovery)

    if not available_discoveries:
        return None

    selected = select_candidate(
        available_discoveries,
        room_id,
        observation_space,
        verb,
    )

    if selected is None:
        return None

    return build_discovery_packet(selected, room_id)

def collapse_observation(
    room_id,
    observation_space,
    facts,
    verb="search",
):

    if not observation_space:
        return []

    collapse_id = observation_space.get("id")
    marker = None

    if collapse_id:
        marker = (
            f"The search space "
            f"{collapse_id}:{verb} "
            f"collapsed."
        )

        if is_observation_collapsed(
            facts,
            collapse_id,
            verb,
        ):
            return []

    constraints = observation_space.get("constraints", {})

    candidates = [
        candidate
        for candidate in OBSERVATION_DISCOVERIES
        if candidate_matches(candidate, constraints, verb)
    ]

    available_candidates = []

    for candidate in candidates:
        reveal = build_discovery_packet(candidate, room_id)

        if reveal is None:
            continue

        candidate_fact = reveal["text"]

        already_present = any(
            fact.get("status", "active") == "active"
            and fact.get("text") == candidate_fact
            for fact in facts
        )

        if not already_present:
            available_candidates.append(candidate)

    if not available_candidates:
        return []

    selected = select_candidate(
        available_candidates,
        room_id,
        observation_space,
        verb,
    )

    if selected is None:
        return []

    reveal = build_discovery_packet(selected, room_id)

    if not reveal:
        return []

    results = [reveal]

    if marker:
        results.append(
            {
                "type": "collapse",
                "text": marker,
            }
        )

    return results