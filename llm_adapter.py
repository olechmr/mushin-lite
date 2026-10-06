from openai import OpenAI
from dotenv import load_dotenv
from packet_interpreter import recover_embedded_packet
import os
import requests
import json
import rules

load_dotenv()

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)

MODEL = "gpt-5"

EXTRACT_CANON = True
EXTRACTION_MODE = "local"  # "cloud" or "local"

LOCAL_CONDITIONING_ENABLED = True
LOCAL_MODEL = "mistral:latest"
LOCAL_URL = "http://192.168.0.18:11434/api/generate"

DEBUG_LOCAL_PACKETS = True
LOCAL_PACKET_LOG = "local_packets.log"

LAST_PACKET = None

def format_conditioning_packet(packet):

    if not packet:
        return ""

    if isinstance(packet, str):
        return packet

    if not isinstance(packet, dict):
        return str(packet)

    return (
        f'ACTION: {packet.get("action", "unknown")}\n'
        f'TARGET: {packet.get("target", "none")}\n'
        f'CONFIDENCE: {packet.get("confidence", "medium")}\n'
        f'INTENT: {packet.get("intent", "")}'
    )

def log_local_packet(user_input, packet):

    if not DEBUG_LOCAL_PACKETS:
        return

    with open(LOCAL_PACKET_LOG, "a") as f:

        f.write("\n")
        f.write("=" * 60 + "\n")
        f.write(f"INPUT: {user_input}\n")
        f.write(f"PACKET: {packet}\n")

def log_extraction_result(user_input, candidates):

    if not DEBUG_LOCAL_PACKETS:
        return

    with open(LOCAL_PACKET_LOG, "a") as f:

        f.write(f"CANDIDATES: {candidates}\n")

def log_final_state(facts):

    if not DEBUG_LOCAL_PACKETS:
        return

    from canon import fact_slot

    with open(LOCAL_PACKET_LOG, "a") as f:

        active_facts = [
            fact["text"]
            for fact in facts
            if fact.get("status", "active") == "active"
        ]

        active_slots = []

        for fact in facts:

            if fact.get("status", "active") != "active":
                continue

            if fact.get("type", "state") != "state":
                continue

            slot = fact_slot(
                fact["text"],
                fact.get("type", "state")
            )

            active_slots.append(slot)

        f.write(f"RULE: {rules.LAST_RULE}\n")
        f.write(f"FINAL STATE: {active_facts}\n")
        f.write(f"SLOTS: {active_slots}\n")

def normalize_conditioning_packet(packet):

    if not isinstance(packet, dict):
        return packet

    return {
        "action": str(packet.get("action", "unknown")).strip().lower(),
        "target": str(packet.get("target", "none")).strip().lower(),
        "intent": str(packet.get("intent", "")).strip(),
        "confidence": str(packet.get("confidence", "medium")).strip().lower()
    }

def get_local_conditioning(user_input, facts):
    """
    Optional local LLM interpretation layer.

    It never writes canon directly.
    It only provides a small hint to the extraction prompt.
    """
    if not LOCAL_CONDITIONING_ENABLED:
        packet = normalize_conditioning_packet({
            "action": parsed.get("action", "unknown"),
            "target": parsed.get("target", "none"),
            "intent": parsed.get("intent", ""),
            "confidence": parsed.get("confidence", "medium")
        })

        return packet
    canon_block = "\n".join(
        f'- {fact["text"]}'
        for fact in facts
        if fact.get("status", "active") == "active"
    )

    prompt = f"""
You are a tiny command interpreter for Mushin Lite.

Return ONLY a compact interpretation of the user command.

Do not write prose.
Do not invent story.
Do not create canon.
Do not explain.

ACTIVE CANON:
{canon_block}

USER COMMAND:
{user_input}

Return ONLY valid JSON.

Schema:
{{
  "action": "short verb",
  "target": "main object or none",
  "intent": "one short phrase"
}}
"""

    try:
        response = requests.post(
            LOCAL_URL,
            json={
                "model": LOCAL_MODEL,
                "prompt": prompt,
                "stream": False,
            },
            timeout=90,
        )

        response.raise_for_status()

        data = response.json()

        raw_text = data.get("response", "").strip()

        try:
            parsed = json.loads(raw_text)

            return normalize_conditioning_packet({
                "action": parsed.get("action", "unknown"),
                "target": parsed.get("target", "none"),
                "intent": parsed.get("intent", ""),
                "confidence": parsed.get("confidence", "medium")
            })

        except json.JSONDecodeError:
            packet = {
                "action": "unknown",
                "target": "none",
                "intent": raw_text,
                "confidence": "low"
            }

            return normalize_conditioning_packet(
                recover_embedded_packet(packet)
            )
            
    except Exception as e:
        return normalize_conditioning_packet({
            "action": "unknown",
            "target": "none",
            "intent": "local conditioning unavailable",
            "confidence": "low"
        })

def extract_with_cloud(extraction_prompt, user_input, assistant_text):

    extraction = client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": extraction_prompt
            },
            {
                "role": "user",
                "content": f"""
USER:
{user_input}

ASSISTANT:
{assistant_text}
"""
            }
        ]
    )

    return extraction.choices[0].message.content

# TODO:
# move extraction rules from prompt hacks
# to packet-driven extraction

def extract_with_local(extraction_prompt, user_input, assistant_text):

    prompt = f"""
Extract canon facts from this command.

Return ONLY lines in this format:
type | fact

Allowed types:
state
event
trait

Rules:
- Use event for actions that happened.
- Use state for current object state.
- If nothing important changed, return NONE.
- Do not explain.
- Do not copy "The action occurred..." as a fact.
- Interpret the USER command directly.
- For "close <object>", return:
  event | The player closed the <object>.
  state | The <object> is closed.
- For "open <object>", return:
  event | The player opened the <object>.
  state | The <object> is open.
- For "take <object>", "pick up <object>", or "grab <object>", return:
  event | The player picked up the <object>.
  state | The player is holding the <object>.
- For "drop <object>", return:
  event | The player dropped the <object>.
  state | The <object> is on the ground.
- For "break <object>", return:
  event | The player broke the <object>.
  state | The <object> is broken.
- For "turn <object> inside out", return:
  event | The player turned the <object> inside out.
  state | The <object> is inside out.


USER:
{user_input}

ASSISTANT:
{assistant_text}
"""

    try:
        response = requests.post(
            LOCAL_URL,
            json={
                "model": LOCAL_MODEL,
                "prompt": prompt,
                "stream": False,
            },
            timeout=90,
        )

        response.raise_for_status()

        data = response.json()

        return data.get("response", "").strip()

    except Exception as e:
        print(f"[local extraction failed: {e}]")
        return "NONE"

def narrate_scene(scene):
    import json

    if isinstance(scene, dict):
        rendered_text = scene.get("rendered_text", "")
        ctx = scene.get("presentation_context", {})
        scene_for_prompt = json.dumps(scene, indent=2)
    else:
        rendered_text = scene
        ctx = {}
        scene_for_prompt = scene

    prompt = f"""
You are a deterministic text renderer, not a storyteller.

Your job is to rewrite RENDERED_TEXT into one short second-person paragraph.

Hard rules:
- Do not add any fact that is not explicitly present.
- Do not infer possession.
- If an object is listed under objects, say it is present or visible, not carried.
- Do not add scenery.
- Do not add furniture.
- Do not add atmosphere.
- Do not add characters.
- Do not add choices.
- Do not add exits beyond the listed exits.
- Do not rename rooms unless a room_name is provided.
- Preserve direction and destination accurately.

Allowed facts are only these:
{scene_for_prompt}

RENDERED_TEXT:
{rendered_text}

Return only the rewritten paragraph.
"""

    try:
        import requests

        response = requests.post(
            "http://192.168.0.18:11434/api/generate",
            json={
                "model": "mistral:latest",
                "prompt": prompt,
                "stream": False,
            },
            timeout=120,
        )

        response.raise_for_status()
        data = response.json()

        return data.get("response", rendered_text).strip() or rendered_text

    except Exception as e:
        return f"[narration failed: {e}]\n\n{rendered_text}"

def chat(user_input, facts):

    canon_block = "\n".join(
        f'- {fact["text"]}'
        for fact in facts
        if fact.get("status", "active") == "active"
    )

    conditioning_packet = get_local_conditioning(user_input, facts)

    global LAST_PACKET
    LAST_PACKET = conditioning_packet
    
    log_local_packet(user_input, conditioning_packet)

    conditioning_text = format_conditioning_packet(
        conditioning_packet
    )

    if LOCAL_CONDITIONING_ENABLED:
        print(f"[raw local packet: {conditioning_packet}]")
        print(f"[raw local conditioning:\n{conditioning_text}]")
    else:
        print("[local conditioning: bypassed]")

    system_prompt = f"""
    You are a natural interactive storyteller and assistant.

    The following facts are CANON.
    They are external truth maintained by Mushin Lite.
    Do not contradict them.

    CANON:
    {canon_block}

    STYLE RULES:
    - Continue the scene directly.
    - Do not confirm canon.
    - Do not say "confirmed."
    - Do not offer help.
    - Do not ask what the user wants next.
    - Do not make bullet lists.
    - Do not explain options.
    - If the user writes a character action or line, respond with the next beat of the scene.
    - Keep responses short: 1 to 4 paragraphs.
    """

#    response = client.chat.completions.create(
#        model=MODEL,
#        messages=[
#            {
#                "role": "system",
#                "content": system_prompt
#            },
#            {
#                "role": "user",
#                "content": user_input
#            }
#        ]
#    )
#
#    assistant_text = response.choices[0].message.content

    assistant_text = f"The action occurred: {user_input}"

    return conditioning_packet
