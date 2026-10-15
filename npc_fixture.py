"""Isolated NPC foundation; never installed by loading a save or an object reset."""


# Exact interface bindings only; importing this table does not install state.
NPC_INQUIRIES = {
    "ask heidi about chris": {
        "respondent": "heidi",
        "other": "chris",
        "episode_id": "fixture_morning",
    },
    "ask chris about heidi this afternoon": {
        "respondent": "chris",
        "other": "heidi",
        "episode_id": "fixture_afternoon",
    },
}


SUPPORTED_DISPOSITIONS = ("irritability", "sociability")


# Simulation authorization only; no causal claim or historical whereabouts.
NPC_TRANSITION_POLICIES = (
    {
        "policy_id": "heidi_morning_irritability_v1",
        "entity_id": "heidi",
        "episode_id": "fixture_morning",
        "required_outcome": "disagreement",
        "attribute": "irritability",
        "value": 0.50,
    },
    {
        "policy_id": "chris_morning_irritability_v1",
        "entity_id": "chris",
        "episode_id": "fixture_morning",
        "required_outcome": "disagreement",
        "attribute": "irritability",
        "value": 0.50,
    },
    {
        "policy_id": "heidi_morning_sociability_v1",
        "entity_id": "heidi",
        "episode_id": "fixture_morning",
        "required_outcome": "disagreement",
        "attribute": "sociability",
        "value": 0.50,
    },
)


def build_npc_fixture():
    """Return fresh data. Windows are ordered fixture units, not an engine clock.

    Allowed places are exhaustive permissions throughout the window, not visits
    or exact whereabouts. Empty/missing permissions are unresolved, not absence.
    Irritability is an established disposition in [0, 1], not evidence of a fight.
    current_room is present availability, never evidence of historical presence.
    Episode IDs uniquely identify a fixed pair and window. Future resolutions
    map those IDs to {"outcome": <outcome ID>} and represent objective truth.
    """
    return {
        "version": 1,
        "entities": {
            "heidi": {"display_name": "Heidi", "irritability": 0.25, "sociability": 0.75, "current_room": "foyer"},
            "chris": {"display_name": "Chris", "irritability": 0.75, "sociability": 0.25, "current_room": "foyer"},
        },
        "episodes": {
            "fixture_morning": {
                "display_name": "fixture morning",
                "participants": ["heidi", "chris"],
                "window": [0, 1],
                "allowed_places": {
                    "heidi": ["study", "foyer"],
                    "chris": ["study", "hallway"],
                },
            },
            "fixture_afternoon": {
                "display_name": "fixture afternoon",
                "participants": ["heidi", "chris"],
                "window": [1, 2],
                "allowed_places": {
                    "heidi": ["study", "foyer"],
                    "chris": ["study", "hallway"],
                },
            },
        },
        "resolutions": {},
    }
