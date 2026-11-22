import json
import re
import streamlit as st
from openai import OpenAI

STATE_FILE = "world_state.json"

def load_state():
    with open(STATE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)

def opening_message(player):
    return {
        "role": "assistant",
        "content": (
            f"Welcome to **{player['current_arc_name']}**, {player['nickname']}. "
            "The towering gates of UA High stand before you, humming with nervous examinees. "
            "You adjust the collar of your middle school uniform as Present Mic's voice booms from the auditorium. What do you do?"
        )
    }

def reset_playthrough(state):
    p = state["player"]
    p["age"] = 15
    p["stamina"] = 100
    p["localized_strain"] = {"arms": 0, "legs": 0, "core": 0}
    p["melancholic_override"] = False
    p["active_blueprints"] = []
    p["current_outfit"] = "middle_school_uniform"
    p["current_arc_order"] = 1
    p["current_arc_name"] = "UA Entrance Exam Arc (February)"
    state["relationships"] = {
        "Izuku Midoriya": 50,
        "Katsuki Bakugo": 30,
        "Ochaco Uraraka": 50,
        "Shota Aizawa": 50
    }
    state["canon_divergence_log"] = []
    save_state(state)
    st.session_state.messages = [opening_message(p)]
    st.session_state.editing_idx = None
    st.session_state.pending_generation = False

def generate_reply(api_key, model_name, state):
    player = state["player"]
    unlocked_lore = [
        entry for entry in state["lorebook"]
        if entry["arc_order"] <= player["current_arc_order"]
    ]

    system_prompt = f"""
You are the Game Master for an interactive My Hero Academia RPG.
PLAYER PROFILE & STATE: {json.dumps(player)}
RELATIONSHIPS: {json.dumps(state['relationships'])}
CANON DIVERGENCES SO FAR: {json.dumps(state['canon_divergence_log'])}
UNLOCKED LORE (DO NOT SPOIL FUTURE ARCS): {json.dumps(unlocked_lore)}

STRICT CHARACTER & QUIRK RULES FOR BEN SHINKAKU:
1. Second Sense pushes Ben's own human physiology up to 90%–100% of his ceiling via Biomechanical Translation and Kinetic Empathy. He CANNOT mimic Emitters or grow Mutant appendages. Green eyes glow faintly with no sparks/flashes.
2. Live Visual Scanning: Must witness targets live with his own eyes (no new scans in darkness, smoke, closed eyes, or from digital screens/goggles). His Digital Goggles only replay past live moments to steady his Confidence Check.
3. Homogenized Dual Blueprints: Max 2 blueprints; they must biomechanically homogenize or they clash and fail. Accelerated Natural Healing occupies 1 slot, burns massive calories (hypoglycemia risk), and cannot cure Delayed Lactic Rigor or realign displaced bones.
4. Confidence Check & Sensory Overload: Doubting his survival shatters the blueprint unless Melancholic Override is active. Optimized senses (like hearing) risk rupture from sudden loud stimuli.
5. Localized Granular Strain (per 10s): Track strain on arms, legs, and core separately (0–10% = 1:1; 11–60% = 2:1 above 10%; 61–100% = 5:1 above 60% causing micro-tears/fractures). Delayed Lactic Rigor locks taxed muscles hours later.
6. Respect current_outfit ({player['current_outfit']}: {player['wardrobe'][player['current_outfit']]}). Use middle_school_uniform only for the Entrance Exam, school_uniform for UA classes, and hero_costume only for training, internships, or combat.
7. Keep NPCs in-character, adapt canon realistically to any butterfly effect, and never let Ben win effortlessly.
8. Respond ONLY in valid JSON with this exact structure:
{{
  "narrative": "Your immersive scene description and NPC dialogue here.",
  "stamina_change": 0,
  "strain_delta": {{"arms": 0, "legs": 0, "core": 0}},
  "override_active": false,
  "active_blueprints": null,
  "new_divergence": null
}}
(Only set "active_blueprints" to a list of up to 2 strings if his active blueprints changed, otherwise null. Set "new_divergence" to a short string ONLY if canon meaningfully changed, otherwise null.)
"""

    client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)

    with st.chat_message("assistant"):
        with st.spinner("Simulating world..."):
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    *st.session_state.messages[-8:]
                ]
            )
            raw_text = response.choices[0].message.content or ""

            match = re.search(r"\{.*\}", raw_text, re.DOTALL)
            try:
                result = json.loads(match.group(0)) if match else {}
            except json.JSONDecodeError:
                result = {}

            if "narrative" not in result:
                result = {
                    "narrative": raw_text if raw_text.strip() else "*(Empty response from model—try clicking Regenerate or switching models.)*",
                    "stamina_change": 0,
                    "strain_delta": {"arms": 0, "legs": 0, "core": 0},
                    "override_active": player["melancholic_override"],
                    "active_blueprints": None,
                    "new_divergence": None,
                }

            player["stamina"] = max(0, min(100, player["stamina"] + result.get("stamina_change", 0)))
            delta = result.get("strain_delta") or {}
            for part in ("arms", "legs", "core"):
                player["localized_strain"][part] = max(0, player["localized_strain"].get(part, 0) + delta.get(part, 0))
            player["melancholic_override"] = bool(result.get("override_active", player["melancholic_override"]))
            if isinstance(result.get("active_blueprints"), list):
                player["active_blueprints"] = result["active_blueprints"][:2]
            if result.get("new_divergence"):
                state["canon_divergence_log"].append(result["new_divergence"])
            save_state(state)

            st.markdown(result["narrative"])
            st.session_state.messages.append({"role": "assistant", "content": result["narrative"]})

state = load_state()
player = state["player"]

st.set_page_config(page_title="MHA AI RPG — Arc", layout="wide")
st.title(f"My Hero Academia RPG — {player['hero_alias']}")

if "messages" not in st.session_state:
    st.session_state.messages = [opening_message(player)]
if "editing_idx" not in st.session_state:
    st.session_state.editing_idx = None
if "pending_generation" not in st.session_state:
    st.session_state.pending_generation = False

with st.sidebar:
    st.header("Setup")
    api_key = st.text_input("OpenRouter API Key", type="password")
    model_name = st.text_input("Model", value="anthropic/claude-sonnet-5.5")

    if st.button("Reset Playthrough", use_container_width=True):
        reset_playthrough(state)
        st.rerun()

    st.divider()
    st.header("Character Sheet")
    st.write(f"**Name:** {player['name']} (Age {player['age']} · Birthday: {player['birthday']})")
    st.write(f"**Alias:** {player['hero_alias']}")
    st.write(f"**Quirk:** {player['quirk']}")
    st.progress(max(0, min(100, player["stamina"])) / 100, text=f"Stamina: {player['stamina']}/100")

    strain = player["localized_strain"]
    st.write(f"**Localized Strain:** Arms {strain['arms']}% | Legs {strain['legs']}% | Core {strain['core']}%")
    st.write(f"**Melancholic Override:** {'ACTIVE' if player['melancholic_override'] else 'Inactive'}")

    arc_titles = [entry["title"] for entry in state["lorebook"]]
    arc_orders = [entry["arc_order"] for entry in state["lorebook"]]
    current_arc_idx = arc_orders.index(player["current_arc_order"]) if player["current_arc_order"] in arc_orders else 2
    selected_arc_title = st.selectbox("Current Arc", arc_titles, index=current_arc_idx)
    new_arc_order = arc_orders[arc_titles.index(selected_arc_title)]
    if new_arc_order != player["current_arc_order"]:
        player["current_arc_order"] = new_arc_order
        player["current_arc_name"] = selected_arc_title
        save_state(state)

    outfit_options = list(player["wardrobe"].keys())
    selected_outfit = st.selectbox(
        "Current Outfit",
        outfit_options,
        index=outfit_options.index(player["current_outfit"])
    )
    if selected_outfit != player["current_outfit"]:
        player["current_outfit"] = selected_outfit
        save_state(state)
    st.caption(player["wardrobe"][player["current_outfit"]])

    st.subheader("Active Blueprints (Max 2)")
    if player["active_blueprints"]:
        for bp in player["active_blueprints"]:
            st.write(f"- {bp}")
    else:
        st.caption("None scanned yet.")

    st.subheader("Relationships")
    for npc, score in state["relationships"].items():
        st.write(f"- {npc}: {score}/100")

    st.subheader("Canon Divergences")
    if state["canon_divergence_log"]:
        for item in state["canon_divergence_log"]:
            st.write(f"- {item}")
    else:
        st.caption("No canon changes recorded yet.")

for i, msg in enumerate(st.session_state.messages):
    with st.chat_message(msg["role"]):
        if st.session_state.editing_idx == i:
            edited_text = st.text_area("Edit your message:", value=msg["content"], key=f"textarea_{i}")
            col1, col2 = st.columns([1, 5])
            with col1:
                if st.button("Save & Regenerate", key=f"save_{i}"):
                    st.session_state.messages[i]["content"] = edited_text
                    st.session_state.messages = st.session_state.messages[: i + 1]
                    st.session_state.editing_idx = None
                    st.session_state.pending_generation = True
                    st.rerun()
            with col2:
                if st.button("Cancel", key=f"cancel_{i}"):
                    st.session_state.editing_idx = None
                    st.rerun()
        else:
            st.markdown(msg["content"])
            if msg["role"] == "user":
                if st.button("Edit", key=f"edit_{i}"):
                    st.session_state.editing_idx = i
                    st.rerun()
            elif i == len(st.session_state.messages) - 1 and i > 0:
                if st.button("Regenerate", key="regen_last"):
                    st.session_state.messages.pop()
                    st.session_state.pending_generation = True
                    st.rerun()

if st.session_state.pending_generation:
    st.session_state.pending_generation = False
    if not api_key:
        st.warning("Please enter your OpenRouter API key in the sidebar first.")
    else:
        generate_reply(api_key, model_name, state)
        st.rerun()

if prompt := st.chat_input("Describe Ben's action, observation, or dialogue..."):
    if not api_key:
        st.warning("Please enter your OpenRouter API key in the sidebar first.")
        st.stop()

    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    generate_reply(api_key, model_name, state)
    st.rerun()