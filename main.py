import npc_activation
from canon import commit_disagreement_initiator, commit_npc_transition, set_npc_disposition, reset_npc_test_fixture, load_state, add_fact, forget_fact, forget_all, resolve_fact, fact_slot
import llm_adapter
from llm_adapter import chat, EXTRACTION_MODE
from packet_interpreter import facts_from_packet, normalize_packet
from rules import apply_rules
from world import slot_value, build_entity_state, build_world_state, entities_in_room, get_entity_data, interaction_supported, resolve_entity_reference
import map_data
from map_data import load_map, reset_map
from collapse import (
    collapse_observation,
    collapse_disagreement_initiator,
    preview_observation,
)
import textwrap
import json
import rules
from behavior import evaluate_episode, evaluate_transition
from renderer import (
    render_npc_inquiry,
    render_response,
    narrate_state,
    build_presentation_context,
    render_room,
    render_inventory,
    render_place,
    format_presentation,
    render_presentation_sentences,
)
from test_fixture import TEST_FACTS
from npc_fixture import NPC_INQUIRIES, SUPPORTED_DISPOSITIONS

load_map()

state = load_state()

SETTINGS = {
    "narration": False,
}

NARRATION_ENABLED = False
pending_npc_transition = None

def normalize_command(user_input):
    text = user_input.lower().strip()

    aliases = {
        "/all facts": "/allfacts",
    }

    directions = {
        "n": "north",
        "north": "north",
        "s": "south",
        "south": "south",
        "e": "east",
        "east": "east",
        "w": "west",
        "west": "west",
    }

    if text in directions:
        return f"go {directions[text]}"

    return aliases.get(text, user_input)

HELP_SECTIONS = {
    "Player Commands": [
        ("ask heidi about chris", "ask about the fixture morning"),
        ("ask chris about heidi this afternoon", "ask about the fixture afternoon"),
        ("look", "examine the current room"),
        ("listen", "listen to your surroundings"),
        ("search", "search the current room"),
        ("north/south/east/west", "move between rooms"),
        ("n/s/e/w", "short movement aliases"),
    ],

    "Canon": [
        ("/remember <fact>", "store canon"),
        ("/facts", "show active canon"),
        ("/allfacts", "show canon, including superseded facts"),
        ("/canon", "show active canon grouped by type"),
        ("/slots", "show active state slots"),
        ("/forget <id>", "remove canon"),
        ("/forgetall", "clear all canon"),
        ("/resolve <id>", "mark a fact resolved"),
    ],

    "World": [
        ("/room", "show rendered room state"),
        ("/place", "show current room descriptor"),
        ("/objects", "show known objects"),
        ("/inventory", "show held entities"),
        ("/world", "show entity state model"),
        ("/worldstate", "show world state"),
        ("/worldjson", "show entity state as JSON"),
        ("/worldsave", "save entity state JSON"),
    ],

    "Observations": [
        ("/observations", "show observation spaces in the current room"),
        ("/discovery <name>", "preview a discovery packet"),
    ],

    "Entities": [
        ("/inspect <name>", "inspect an entity"),
        ("/entity <name>", "show entity descriptor"),
        ("/actions", "show room interactions"),
        ("/actions <name>", "show entity interactions"),
    ],

    "Map": [
        ("/map", "show current room graph"),
        ("/mapreset", "reset room graph"),
    ],

    "Pipeline": [
        ("/mode", "show extraction mode"),
        ("/narration on|off", "toggle scene narration"),
        ("/packet", "show last oracle packet"),
        ("/trace", "show local packet trace"),
        ("/traceclear", "clear trace log"),
        ("/rule", "show last rule fired"),
    ],

    "Testing": [
        ("/setup", "paste session setup"),
        ("/testreset", "reset canon and map to test fixture"),
        ("/npctestreset", "reset the isolated NPC fixture"),
        ("/npctransitionpreview heidi_morning_irritability_v1", "preview Heidi transition"),
        ("/npctransitionpreview chris_morning_irritability_v1", "preview Chris transition"),
        ("/npctransitionpreview heidi_morning_sociability_v1", "preview Heidi sociability transition"),
        ("/npctransitioncommit", "commit the pending NPC transition"),
        ("/npcset <entity_id> irritability <value>", "set NPC irritability (developer)"),
        ("/npcset <entity_id> sociability <value>", "set NPC sociability (developer)"),
        ("/npcevaluate <episode_id>", "evaluate NPC possibilities without collapse"),
        ("/npcresolve <episode_id>", "resolve an installed NPC episode (developer)"),
    ],

    "General": [
        ("/help", "show commands"),
        ("/quit", "exit"),
    ],
}

def show_help():
    for heading, commands in HELP_SECTIONS.items():
        print(f"{heading}:")

        for command, description in commands:
            print(f"  {command:<22} {description}")

        print()

def process_npc_transitions_for_episode(state, episode_id):
    """Compatibility wrapper for the existing explicit transition dispatcher."""
    return npc_activation.process_npc_transitions_for_episode(state, episode_id)


def resolve_npc_episode(state, episode_id, rng=None):
    """Preserve the existing CLI diagnostic shape over host activation."""
    diagnostic = npc_activation.activate_npc_episode(state, episode_id, rng=rng)
    diagnostic.pop("activation_status")
    return diagnostic


def handle_npc_resolve(state, episode_id, rng=None):
    """Developer diagnostics only; never installs a fixture or invokes the model."""
    diagnostic = resolve_npc_episode(state, episode_id, rng=rng)
    print(json.dumps(diagnostic, indent=2, sort_keys=True))
    return diagnostic


def handle_npc_refine(state, rng=None):
    """Developer-only request; diagnostics disclose only committed actor truth."""
    proposal = collapse_disagreement_initiator(state.get("npc"), "fixture_morning", rng=rng)
    diagnostic = {k: v for k, v in proposal.items() if k not in ("basis", "disagreement_initiator")}
    diagnostic["committed"] = False
    if proposal["status"] == "proposed":
        try:
            result = commit_disagreement_initiator(state, proposal)
            diagnostic.update(result, status="resolved")
        except (ValueError, OSError) as error:
            diagnostic.update(status="unresolved", error=str(error), error_type=type(error).__name__)
    elif proposal["reused"]:
        diagnostic["disagreement_initiator"] = proposal["disagreement_initiator"]
    print(json.dumps(diagnostic, indent=2, sort_keys=True))
    return diagnostic


def handle_npc_inquiry(state, inquiry, rng=None):
    """Execute an explicit binding; validate identity and availability before collapse."""
    def valid_text(value):
        return isinstance(value, str) and bool(value.strip()) and value.lower().strip() not in ("none", "unknown")

    unresolved = "The requested interaction cannot be established."
    if not isinstance(inquiry, dict):
        print(unresolved)
        return
    respondent_id, other_id, episode_id = (inquiry.get(k) for k in ("respondent", "other", "episode_id"))
    if not all(valid_text(v) for v in (respondent_id, other_id, episode_id)) or respondent_id == other_id:
        print(unresolved)
        return
    npc = state.get("npc", {})
    entities = npc.get("entities", {}) if isinstance(npc, dict) else {}
    episodes = npc.get("episodes", {}) if isinstance(npc, dict) else {}
    if not isinstance(entities, dict) or not isinstance(episodes, dict):
        print(unresolved)
        return
    respondent, other, episode = entities.get(respondent_id), entities.get(other_id), episodes.get(episode_id)
    if not all(isinstance(v, dict) for v in (respondent, other, episode)):
        print(unresolved)
        return
    participants = episode.get("participants")
    if (
        not isinstance(participants, list) or len(participants) != 2
        or not all(valid_text(p) for p in participants)
        or set(participants) != {respondent_id, other_id}
    ):
        print(unresolved)
        return
    respondent_name, other_name, episode_name = (v.get("display_name") for v in (respondent, other, episode))
    if not all(valid_text(v) for v in (respondent_name, other_name, episode_name)):
        print(unresolved)
        return
    room = respondent.get("current_room")
    player_locations = {
        slot_value("whereabouts:player", f["text"])
        for f in state["facts"]
        if f.get("status", "active") == "active"
        and fact_slot(f["text"], f.get("type", "state")) == "whereabouts:player"
    }
    if not valid_text(room) or player_locations != {f"in the {room}"}:
        print(f"{respondent_name} is not available here to answer.")
        return
    result = resolve_npc_episode(state, episode_id, rng=rng)
    outcome = None
    if result["committed"] or result["reused"]:
        outcome = state["npc"]["resolutions"][episode_id]["outcome"]
    print(render_npc_inquiry(outcome, respondent_name, other_name, episode_name))
    for transition in result.get("transitions", []):
        print(f"[NPC transition: {json.dumps(transition, sort_keys=True)}]")


def handle_observation_command(
    state,
    user_input,
    verb,
    target,
):
    pass

def current_context(state):
    return build_presentation_context(
        user_input="",
        packet={},
        facts=state["facts"],
    )

def handle_observation_command(
    state,
    user_input,
    verb,
    target,
):
    ctx = build_presentation_context(
        user_input=user_input,
        packet={
            "action": verb,
            "target": target,
        },
        facts=state["facts"],
    )

    room_id = ctx.get("room_id")
    room = ctx.get("room") or {}
    observation_spaces = room.get("observations", [])

    if not observation_spaces:
        print()
        print(f"{CYAN}You don't find anything of interest.{RESET}")
        print()
        return

    if not target:
        available_targets = [
            space.get("display_name", space.get("id", "unknown"))
            for space in observation_spaces
            if verb in space.get("verbs", [])
        ]

        print()

        if available_targets:
            print(
                f"{CYAN}What do you want to {verb}? "
                f"{', '.join(available_targets)}{RESET}"
            )
        else:
            print(
                f"{CYAN}There is nothing here you can {verb}.{RESET}"
            )

        print()
        return

    observation_space = next(
        (
            space
            for space in observation_spaces
            if target.lower()
            == space.get("display_name", "").lower()
        ),
        None,
    )

    if observation_space is None:
        print()
        print(
            f"{CYAN}There is no {target} here to {verb}.{RESET}"
        )
        print()
        return

    if verb not in observation_space.get("verbs", []):
        print()
        print(f"{CYAN}You can't {verb} the {target}.{RESET}")
        print()
        return

    reveals = collapse_observation(
        room_id,
        observation_space,
        state["facts"],
        verb=verb,
    )

    found = []

    for reveal in reveals:
        added = add_fact(
            state,
            reveal["text"],
            reveal.get("type", "state"),
        )

        if added and reveal.get("type", "state") != "collapse":
            found.append(reveal["text"])

    print()

    if found:
        for fact_text in found:
            print(f"{CYAN}You find something: {fact_text}{RESET}")
    else:
        print(f"{CYAN}You find nothing new.{RESET}")

    print()

print()
print("Mushin Lite Engine v0.3")
print("Copyright (c) 2026 Matt Olech")
print("MIT License")
print()
show_help()

try:

    while True:

        RED = "\033[91m"
        GREEN = "\033[92m"
        YELLOW = "\033[93m"
        BLUE = "\033[94m"
        MAGENTA = "\033[95m"
        CYAN = "\033[96m"
        RESET = "\033[0m"

        print()
        user_input = input(f"{GREEN}> {RESET}").strip()
        user_input = normalize_command(user_input)
        print()

        if not user_input.strip():
            continue

        if user_input == "/help":

            print()
            show_help()
            continue

        if user_input == "/npctestreset":
            reset_npc_test_fixture(state)
            print("[NPC fixture reset]")
            continue

        inquiry = NPC_INQUIRIES.get(user_input.lower().strip())
        if inquiry is not None:
            handle_npc_inquiry(state, inquiry)
            continue

        if user_input == "/npcrefine" or user_input.startswith("/npcrefine "):
            if user_input != "/npcrefine fixture_morning":
                print("Usage: /npcrefine fixture_morning")
            else:
                handle_npc_refine(state)
            continue

        if user_input == "/npcresolve" or user_input.startswith("/npcresolve "):
            parts = user_input.split()
            if len(parts) != 2:
                print("Usage: /npcresolve <episode_id>")
            else:
                handle_npc_resolve(state, parts[1])
            continue

        if user_input == "/npctransitionpreview" or user_input.startswith("/npctransitionpreview "):
            pending_npc_transition = None
            parts = user_input.split()
            if len(parts) != 2:
                print("Usage: /npctransitionpreview <policy_id> (heidi_morning_irritability_v1, chris_morning_irritability_v1, or heidi_morning_sociability_v1)")
            else:
                result = evaluate_transition(state.get("npc"), parts[1])
                if result["status"] == "proposed":
                    pending_npc_transition = result
                print(json.dumps({k: v for k, v in result.items() if k != "basis"}, indent=2, sort_keys=True))
            continue

        if user_input == "/npctransitioncommit" or user_input.startswith("/npctransitioncommit "):
            if user_input != "/npctransitioncommit":
                print("Usage: /npctransitioncommit")
            elif pending_npc_transition is None:
                print("[NPC transition: no pending proposal]")
            else:
                try:
                    result = commit_npc_transition(state, pending_npc_transition)
                    pending_npc_transition = None
                    print(json.dumps(result, indent=2, sort_keys=True))
                except ValueError as error:
                    pending_npc_transition = None
                    print(f"[NPC transition rejected] {error}")
                except OSError as error:
                    print(f"[NPC transition save failed] {error}")
            continue

        if user_input == "/npcset" or user_input.startswith("/npcset "):
            parts = user_input.split()
            if len(parts) != 4 or parts[2] not in SUPPORTED_DISPOSITIONS:
                print("Usage: /npcset <entity_id> <irritability|sociability> <value>")
            else:
                try:
                    result = set_npc_disposition(state, parts[1], parts[2], float(parts[3]))
                    print(json.dumps(result, indent=2, sort_keys=True))
                except (ValueError, OSError) as error:
                    print(f"[npcset error] {error}")
            continue

        if user_input == "/npcevaluate" or user_input.startswith("/npcevaluate "):
            parts = user_input.split()
            if len(parts) != 2:
                print("Usage: /npcevaluate <episode_id>")
            else:
                result = evaluate_episode(state.get("npc"), parts[1])
                print(json.dumps({"episode_id": parts[1], **result}, indent=2, sort_keys=True))
            continue

        if user_input == "/setup":

            print("[setup mode]")
            print("Paste setup text. Type /done on its own line when finished.")

            setup_lines = []

            while True:
                line = input()

                if line.strip() == "/done":
                    break

                setup_lines.append(line)

            added_count = 0

            for line in setup_lines:

                line = line.strip()

                if not line:
                    continue

                added = add_fact(state, line, "state")

                if added:
                    added_count += 1

            print(f"[setup saved: {added_count} facts]")
            
            continue        

        if user_input == "/quit":
            break

        if user_input == "/facts":

            print()

            for fact in state["facts"]:
                if fact.get("status", "active") != "active":
                    continue

                print(f'{fact["id"]}. [{fact.get("type", "state")}] {fact["text"]}')

            print()

            continue

        if user_input == "/allfacts":

            print()

            for fact in state["facts"]:
                print(
                    f'{fact["id"]}. '
                    f'[{fact.get("status", "active")}] '
                    f'[{fact.get("type", "state")}] '
                    f'{fact["text"]}'
                )

            print()

            continue

        if user_input == "/trace":

            try:
                with open("local_packets.log", "r") as f:
                    print()
                    print(f.read())
                    print()

            except FileNotFoundError:
                print("[no trace log yet]")

            continue

        if user_input == "/traceclear":

            with open("local_packets.log", "w") as f:
                pass

            print("[trace log cleared]")
            continue

        if user_input == "/rule":

            print()

            if rules.LAST_RULE:
                print(f"[{rules.LAST_RULE_TYPE}]")
                print(rules.LAST_RULE)
            else:
                print("none")

            print()

            continue

        if user_input == "/canon":

            print()

            for fact_type in ["state", "event", "collapse", "trait"]:
                print(f"{fact_type.upper()}:")

                found = False

                for fact in state["facts"]:
                    if fact.get("status", "active") != "active":
                        continue

                    if fact.get("type", "state") != fact_type:
                        continue

                    print(f'  {fact["id"]}. {fact["text"]}')
                    found = True

                if not found:
                    print("  none")

                print()

            continue

        if user_input == "/slots":

            print()

            for fact in state["facts"]:

                if fact.get("status", "active") != "active":
                    continue

                if fact.get("type", "state") != "state":
                    continue

                slot = fact_slot(
                    fact["text"],
                    fact.get("type", "state")
                )

                print(f'{fact["id"]}. {slot} | {fact["text"]}')

            print()

            continue

        if user_input == "/objects":

            objects = build_entity_state(state["facts"])

            print()
            print("OBJECTS:")

            if objects:
                for obj in sorted(objects.keys()):
                    print(f"  {obj}")
            else:
                print("  none")

            print()

            continue

        if user_input == "/actions":

            ctx = current_context(state)

            room = ctx.get("room")

            print()

            if not room:
                print("Actions: none")
                print()
                continue

            icon = room.get("icon") or ""
            print(f"Actions for {room['display_name']} {icon}:".rstrip())

            interactions = room.get("interactions", [])

            if interactions:
                for interaction in interactions:
                    print(f"  {interaction}")
            else:
                print("  none")

            print()

            continue

        if user_input.startswith("/actions "):

            entity_name = user_input[len("/actions "):].strip().lower()

            if not entity_name:
                print("[error] Use /actions followed by an entity name.")
                continue

            entities = build_entity_state(state["facts"])
            entity_state = entities.get(entity_name, {})
            entity_data = get_entity_data(entity_name, entity_state)

            print()

            icon = entity_data.get("icon") or ""
            print(f"Actions for {entity_data['display_name']} {icon}:".rstrip())

            interactions = entity_data.get("interactions", [])

            if interactions:
                for interaction in interactions:
                    print(f"  {interaction}")
            else:
                print("  none")

            print()

            continue

        if user_input.startswith("/inspect "):

            obj_name = user_input[len("/inspect "):].strip().lower()

            if not obj_name:
                print("[error] Use /inspect followed by an entity name.")
                continue

            entities = build_entity_state(state["facts"])
            entity_state = entities.get(obj_name, {})
            entity_data = get_entity_data(obj_name, entity_state)

            print()

            icon = entity_data.get("icon") or ""
            print(f"ENTITY: {entity_data['display_name']} {icon}".rstrip())
            print(f"id: {entity_data['id']}")

            tags = entity_data.get("tags", [])
            interactions = entity_data.get("interactions", [])

            if tags:
                print(f"tags: {', '.join(tags)}")

            if interactions:
                print(f"interactions: {', '.join(interactions)}")

            print()
            print("State:")

            if not entity_state:
                print("  no active state facts found")
            else:
                for category in sorted(entity_state.keys()):
                    print(f"  {category} = {entity_state[category]}")

            print()

            continue

        if user_input.startswith("/entity "):

            entity_name = user_input[len("/entity "):].strip().lower()

            if not entity_name:
                print("[error] Use /entity followed by an entity name.")
                continue

            entities = build_entity_state(state["facts"])
            entity_state = entities.get(entity_name, {})
            entity_data = get_entity_data(entity_name, entity_state)

            print()
            print(json.dumps(entity_data, indent=2, sort_keys=True, ensure_ascii=False))
            print()

            continue

        if user_input == "/world":

            objects = build_entity_state(state["facts"])

            print()
            print("WORLD:")

            if not objects:
                print("  none")
            else:
                for obj in sorted(objects.keys()):
                    print(f"  {obj}:")

                    for category in sorted(objects[obj].keys()):
                        print(f"    {category} = {objects[obj][category]}")

            print()

            continue

        if user_input == "/worldjson":

            objects = build_entity_state(state["facts"])

            print()
            print(json.dumps(objects, indent=2, sort_keys=True))
            print()

            continue

        if user_input == "/worldsave":

            objects = build_entity_state(state["facts"])

            with open("world_state.json", "w") as f:
                json.dump(objects, f, indent=2, sort_keys=True)

            print("[world state saved to world_state.json]")
            continue

        if user_input == "/worldstate":

            world_state = build_world_state(state["facts"])

            print()
            print("WORLD STATE:")

            if not world_state:
                print("  none")
            else:
                for name in sorted(world_state.keys()):
                    print(f"  {name} = {world_state[name]}")

            print()

            continue

        if user_input == "/mode":

            print(f"[extraction mode: {EXTRACTION_MODE}]")
            continue

        if user_input.startswith("/remember "):
            fact = user_input[len("/remember "):]
            add_fact(state, fact)
            print(f"[canon added] {fact}")
            continue

        if user_input.startswith("/forget "):

            try:
                number = int(user_input[len("/forget "):])
            except ValueError:
                print("[error] Use /forget followed by a number.")
                continue

            removed = forget_fact(state, number)

            if removed is None:
                print("[error] No fact with that number.")
            else:
                print(f"[canon removed] {removed}")

            continue

        if user_input == "/forgetall":

            confirm = input("Really delete all canon? (y/n): ")

            if confirm.lower() == "y":

                forget_all(state)

                print("[all canon cleared]")

            continue

        if user_input.startswith("/resolve "):

            try:
                number = int(user_input[len("/resolve "):])

            except ValueError:

                print("[error] Use /resolve followed by a number.")
                continue

            resolved = resolve_fact(state, number)

            if resolved is None:
                print("[error] No fact with that number.")
            else:
                print(f"[resolved] {resolved}")

            continue

        if user_input == "/packet":

            print()
            print(llm_adapter.LAST_PACKET)
            print()

            continue

        if user_input == "/place":

            ctx = current_context(state)

            print()
            print(render_place(ctx.get("room")))
            print()

            continue

        if user_input == "/observations":

            ctx = current_context(state)

            room_id = ctx.get("room_id")
            room = ctx.get("room") or {}
            observation_spaces = room.get("observations", [])

            print()

            if not observation_spaces:
                print("No observation spaces are defined for this room.")
            else:
                for space in observation_spaces:
                    icon = space.get("icon", "")
                    display_name = space.get(
                        "display_name",
                        space.get("id", "unknown"),
                    )
                    verbs = ", ".join(space.get("verbs", []))
                    description = space.get("description", "")

                    heading = f"{icon} {display_name}".strip()
                    print(heading)

                    if description:
                        print(f"  {description}")

                    if verbs:
                        print(f"  verbs: {verbs}")

                    print()

            continue

        if user_input.startswith("/discovery "):

            parts = user_input[len("/discovery "):].strip().lower().split()

            target = parts[0] if parts else ""
            verb = parts[1] if len(parts) > 1 else "search"

            ctx = current_context(state)

            room_id = ctx.get("room_id")
            room = ctx.get("room") or {}
            observation_spaces = room.get("observations", [])

            observation_space = next(
                (
                    space
                    for space in observation_spaces
                    if space.get("display_name", "").lower() == target
                ),
                None,
            )

            print()

            if observation_space is None:
                print("No such observation.")
            else:
                packet = preview_observation(
                    room_id,
                    observation_space,
                    state["facts"],
                    verb=verb,
                )
                if packet is None:
                    print("No discovery available.")
                else:
                    print(json.dumps(packet, indent=2))

            print()

            continue

        if user_input == "/room":

            ctx = current_context(state)

            print(render_room(ctx))
            print()
            continue

        if user_input == "/inventory":

            entities = build_entity_state(state["facts"])

            print(render_inventory(entities))
            print()

            continue

        if user_input == "/map":

            print()
            print("MAP:")

            for room, exits in map_data.EXITS.items():
                print(f"  {room}:")

                if exits:
                    for direction, destination in exits.items():
                        print(f"    {direction} -> {destination}")
                else:
                    print("    no exits")

            print()
            continue

        if user_input == "/mapreset":

            reset_map()
            print()
            print("[map reset]")
            print("Warning: canon may still reference generated rooms.")
            print("Use /forgetall for a full world reset.")
            print()
            continue

        if user_input == "/testreset":

            forget_all(state)
            reset_map()

            for fact in TEST_FACTS:
                add_fact(
                    state,
                    fact["text"],
                    fact.get("type", "state")
                )

            print()
            print("[test fixture reset]")
            print()
            continue

        if user_input == "/narration on":

            SETTINGS["narration"] = True

            print()
            print("[narration enabled]")
            print()

            continue

        if user_input == "/narration off":

            SETTINGS["narration"] = False

            print()
            print("[narration disabled]")
            print()

            continue

        if user_input in ["look", "look around"]:

            ctx = build_presentation_context(
                user_input="look",
                packet={"action": "look", "target": ""},
                facts=state["facts"],
            )

            room = ctx.get("room")
            room_name = room.get("display_name", ctx.get("room_id")) if room else "Somewhere"

            presentation = format_presentation(ctx)
            presentation["movement"] = room_name

            if room and room.get("description"):
                presentation["description"] = room["description"]

            scene = render_presentation_sentences(presentation)

            print()
            print(f"{CYAN}{scene}{RESET}")
            print()

            continue

        if user_input == "listen":

            ctx = build_presentation_context(
                user_input="listen",
                packet={"action": "listen", "target": ""},
                facts=state["facts"],
            )

            room = ctx.get("room")

            print()

            if room and room.get("ambience"):
                print(f"{CYAN}{room['ambience']}{RESET}")
            elif room:
                print(f"{CYAN}You listen carefully in the {room['display_name']}.{RESET}")
            else:
                print(f"{CYAN}You listen carefully.{RESET}")

            print()

            continue

        if user_input == "search" or user_input.startswith("search "):

            search_target = user_input[7:].strip()

            handle_observation_command(
                state,
                user_input,
                "search",
                search_target,
            )

            continue

        if user_input == "inspect" or user_input.startswith("inspect "):

            inspect_target = user_input[8:].strip()

            handle_observation_command(
                state,
                user_input,
                "inspect",
                inspect_target,
            )

            continue

        packet = chat(user_input, state["facts"])
        
        packet = normalize_packet(packet)

        action = packet.get("action", "")
        target = packet.get("target", "")

        if action in ("take", "drop", "open", "close", "light", "extinguish"):
            entities = build_entity_state(state["facts"])
            resolved_target = resolve_entity_reference(
                target,
                entities,
                entities.get("player", {}).get("whereabouts")
            )

            if resolved_target is None:
                entity_data = get_entity_data(target, {})
                display_name = entity_data.get("display_name", target)

                print()
                print(f"You can't {action} the {display_name}.")
                print()
                continue

            packet = dict(packet)
            packet["target"] = resolved_target
            target = resolved_target

        movement_actions = ["go", "move", "walk", "enter"]
        system_actions = ["none"]

        if (
            action == "unknown"
            and target not in ["none", "unknown", ""]
        ):
            entity_data = get_entity_data(target, {})
            display_name = entity_data.get("display_name", target)

            print()
            print(f"You can't do that with the {display_name}.")
            print()
            continue

        if (
            action not in movement_actions
            and action not in system_actions
            and not interaction_supported(
                target,
                action,
                build_entity_state(state["facts"]).get(target, {}),
                build_entity_state(state["facts"]).get("player", {}).get("whereabouts")
            )
        ):
            entity_data = get_entity_data(target, {})
            display_name = entity_data.get("display_name", target)

            print()
            print(f"You can't {action} the {display_name}.")
            print()
            continue

        packet_candidates = facts_from_packet(packet, state["facts"])

        world = build_entity_state(state["facts"])
        world_state = build_world_state(state["facts"])

        packet_candidates = apply_rules(
            packet,
            packet_candidates,
            world,
            world_state
        )

        rule_block_text = None

        if rules.LAST_RULE_TYPE == "block":
            rule_block_text = " ".join(
                candidate["text"]
                for candidate in packet_candidates
                if candidate["type"] == "event"
            )

        if rules.LAST_RULE:
            print(
                f"[rule {rules.LAST_RULE_TYPE}] "
                f"{rules.LAST_RULE}"
            )

        committed_states = []

        for candidate in packet_candidates:

            if add_fact(
                state,
                candidate["text"],
                candidate["type"]
            ):
                if candidate["type"] == "state":
                    committed_states.append(state["facts"][-1])

                print(f'[debug saved] [{candidate["type"]}] {candidate["text"]}')

        ctx = build_presentation_context(
            user_input,
            packet,
            state["facts"]
        )

        ctx["committed_states"] = [
            fact["text"] for fact in committed_states
            if fact.get("status", "active") == "active"
        ]

        ctx["rule_block_text"] = rule_block_text

        presentation = format_presentation(ctx)
        scene = render_presentation_sentences(presentation)

        if SETTINGS["narration"]:
            response = narrate_state(ctx, scene, presentation)
        else:
            response = scene

        print()
        print(f"{CYAN}{response}{RESET}")
        print()
            
        from llm_adapter import log_final_state

        log_final_state(state["facts"])

except KeyboardInterrupt:

    print("\n")
    print("[ctrl-c detected]")
    print("Exiting Mushin Lite.")