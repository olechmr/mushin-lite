"""Isolated NPC foundation; never installed by loading a save or an object reset."""


def build_npc_fixture():
    """Return fresh data. Windows are ordered fixture units, not an engine clock.

    Allowed places are exhaustive permissions throughout the window, not visits
    or exact whereabouts. Empty/missing permissions are unresolved, not absence.
    Irritability is an established disposition in [0, 1], not evidence of a fight.
    Episode IDs uniquely identify a fixed pair and window. Future resolutions
    map those IDs to {"outcome": <outcome ID>} and represent objective truth.
    """
    return {
        "version": 1,
        "entities": {
            "heidi": {"display_name": "Heidi", "irritability": 0.25},
            "chris": {"display_name": "Chris", "irritability": 0.25},
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
