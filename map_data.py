import json

MAP_FILE = "map.json"

BASE_EXITS = {
    "foyer": {
        "north": "hallway",
    },
    "hallway": {
        "south": "foyer",
        "north": "study",
    },
    "study": {
        "south": "hallway",
    },
}

ROOMS = {
    "foyer": {
        "display_name": "Foyer",
        "description": "A small entry room that connects the house together.",
        "ambience": "The house is quiet near the entryway.",
        "lighting": "normal",
        "tags": ["indoors"],
        "interactions": ["look", "listen", "search"],
        "icon": "🚪",
    },
    "hallway": {
        "display_name": "Hallway",
        "description": "A narrow passage between rooms.",
        "ambience": "Sound carries faintly along the narrow passage.",
        "lighting": "normal",
        "tags": ["indoors", "passage"],
        "interactions": ["look", "listen", "search"],
        "icon": "↔",
    },
    "study": {
        "display_name": "Study",
        "description": "A quiet room set apart from the main passage.",
        "ambience": "The study is still and quiet.",
        "lighting": "normal",
        "tags": ["indoors", "quiet"],
        "interactions": ["look", "listen", "search"],
        "icon": "📚",
        "observations": [
            {
                "id": "study_desk",
                "display_name": "desk",
                "icon": "🪑",
                "description": "A heavy oak writing desk.",
                "collapsed_description":
                    "The desk's drawers hang open from your earlier search.",
                "verbs": [
                    "search",
                    "inspect",
                ],
                "constraints": {
                    "required_tags": ["desk"]
                },
            },
            {
                "id": "study_bookshelf",
                "display_name": "bookshelf",
                "icon": "📚",
                "description": "Tall shelves packed with old books.",
                "collapsed_description":
                    "The bookshelf's contents are in disarray from your earlier search.",
                "verbs": [
                    "search",
                    "inspect",
                ],
                "constraints": {
                    "required_tags": ["bookshelf"]
                },
            },
            {
                "id": "study_fireplace",
                "display_name": "fireplace",
                "icon": "🔥",
                "description": "A cold stone fireplace darkened with soot.",
                "collapsed_description":
                    "The floor in front of the fireplace is covered in soot from your earlier search.",
                "verbs": [
                    "search",
                    "inspect",
                ],
                "constraints": {
                    "required_tags": ["fireplace"]
                },
            },
        ],
    },
}

EXITS = {room: exits.copy() for room, exits in BASE_EXITS.items()}

OPPOSITE = {
    "north": "south",
    "south": "north",
    "east": "west",
    "west": "east",
}

def reset_map():
    global EXITS
    EXITS = {room: exits.copy() for room, exits in BASE_EXITS.items()}
    save_map()

def add_exit(room, direction, destination):
    EXITS.setdefault(room, {})[direction] = destination

    opposite = OPPOSITE.get(direction)
    if opposite:
        EXITS.setdefault(destination, {})[opposite] = room

    save_map()

def save_map():
    with open(MAP_FILE, "w") as f:
        json.dump(EXITS, f, indent=2)


def load_map():
    global EXITS

    try:
        with open(MAP_FILE, "r") as f:
            EXITS = json.load(f)

    except (FileNotFoundError, json.JSONDecodeError):
        save_map()

def get_room_data(room_id):
    data = ROOMS.get(room_id, {}).copy()

    data.setdefault("display_name", room_id.replace("_", " ").title())
    data.setdefault("description", None)
    data.setdefault("ambience", None)
    data.setdefault("lighting", "normal")
    data.setdefault("tags", [])
    data.setdefault("interactions", ["look"])
    data.setdefault("icon", None)
    data.setdefault("observations", [])

    data["id"] = room_id

    return data