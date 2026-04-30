"""
Streamlit web interface for the NL2BT-Verify pipeline.
Run with: python3 -m streamlit run web_interface/app.py
"""
import sys
import os
import time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
from verification.smt_verifier import SMTVerifier
from verification.config import ALLOWED_ACTIONS, MAP_WIDTH, MAP_HEIGHT, LOOP_THRESHOLD, KNOWN_LOCATIONS, MAP_GRAPH

st.set_page_config(
    page_title="NL2BT-Verify",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ──────────────────────────────────────────────────────────────
st.markdown("""
<style>
.big-title  { font-size: 2rem; font-weight: 700; }
.subtitle   { color: #888; font-size: 0.95rem; margin-top: -8px; }
.check-pass { background:#1e3a2f; border-left:4px solid #2ecc71;
              padding:8px 14px; border-radius:4px; margin:4px 0; }
.check-fail { background:#3a1e1e; border-left:4px solid #e74c3c;
              padding:8px 14px; border-radius:4px; margin:4px 0; }
.check-name   { font-weight:600; font-size:0.9rem; }
.check-detail { color:#aaa; font-size:0.82rem; }
</style>
""", unsafe_allow_html=True)

# ── Shared result renderer ───────────────────────────────────────────────────
def show_result(result, xml_bt, llm_ms, smt_ms, show_xml=True):
    c1, c2, c3 = st.columns(3)
    c1.metric("LLM Translation", f"{llm_ms:.0f} ms" if llm_ms is not None else "skipped")
    c2.metric("SMT Verification", f"{smt_ms:.2f} ms")
    c3.metric("BT Size", f"{len(xml_bt)} chars")

    st.divider()

    if result["passed"]:
        st.success("## ✅ SAFE — All 6 properties verified")
        st.caption("This behavior tree is mathematically proven safe to execute.")
    else:
        st.error("## ❌ REJECTED — Unsafe behavior tree blocked")
        st.caption("Z3 proved a safety violation. The robot will NOT execute this.")

    st.subheader("Safety Property Checks")
    for chk in result["checks"]:
        icon  = "✅" if chk["passed"] else "❌"
        css   = "check-pass" if chk["passed"] else "check-fail"
        label = chk["name"].replace("_", " ").title()
        st.markdown(
            f'<div class="{css}">'
            f'<span class="check-name">{icon} {label}</span><br>'
            f'<span class="check-detail">{chk["detail"]}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

    if show_xml:
        st.divider()
        lbl = "Verified XML Behavior Tree" if result["passed"] else "Rejected XML (not executed)"
        st.subheader(lbl)
        st.code(xml_bt, language="xml")


# ── Pre-built demo BTs (no LLM needed, instant) ──────────────────────────────
DEMO_BTS = {
    "✅ Pick up and deliver (safe)": (
        "Pick up the box from shelf 1 and deliver it to the loading dock",
        """<BehaviorTree>
  <Sequence name="DeliverBox">
    <Action name="move_to" location="shelf_1"/>
    <Action name="pick_up" item="box"/>
    <Action name="move_to" location="loading_dock"/>
    <Action name="deliver" item="box"/>
  </Sequence>
</BehaviorTree>""",
    ),
    "✅ Multi-room patrol (safe)": (
        "Patrol room A and room B three times, then go to charging station",
        """<BehaviorTree>
  <Sequence name="PatrolThenCharge">
    <Repeat name="patrol_loop" max_iterations="3">
      <Sequence name="patrol_rooms">
        <Action name="move_to" location="room_a"/>
        <Action name="patrol"/>
        <Action name="move_to" location="room_b"/>
        <Action name="patrol"/>
      </Sequence>
    </Repeat>
    <Action name="move_to" location="charging_station"/>
    <Action name="charge"/>
  </Sequence>
</BehaviorTree>""",
    ),
    "❌ Disallowed action — fire_laser": (
        "Move to room A and fire the laser at the wall",
        """<BehaviorTree>
  <Sequence name="root">
    <Action name="move_to" location="room_a"/>
    <Action name="fire_laser" target="wall"/>
  </Sequence>
</BehaviorTree>""",
    ),
    "❌ Unknown location — moon_base": (
        "Pick up the box and deliver it to the moon base",
        """<BehaviorTree>
  <Sequence name="root">
    <Action name="move_to" location="moon_base"/>
    <Action name="pick_up" item="box"/>
    <Action name="deliver" item="box"/>
  </Sequence>
</BehaviorTree>""",
    ),
    "❌ Task ordering — pick_up before move_to": (
        "Pick up the box immediately and then deliver it",
        """<BehaviorTree>
  <Sequence name="root">
    <Action name="pick_up" item="box"/>
    <Action name="move_to" location="loading_dock"/>
    <Action name="deliver" item="box"/>
  </Sequence>
</BehaviorTree>""",
    ),
    "❌ Infinite loop — no bound": (
        "Keep patrolling the warehouse forever",
        """<BehaviorTree>
  <Sequence name="root">
    <Repeat name="infinite_patrol">
      <Action name="patrol"/>
    </Repeat>
  </Sequence>
</BehaviorTree>""",
    ),
}

# ── Sidebar ──────────────────────────────────────────────────────────────────
EXAMPLES = {
    "✅ Pick up and deliver":   "Pick up the box from shelf 1 and deliver it to the loading dock",
    "✅ Multi-room patrol":     "Patrol room A, room B, and room C three times then go to charging station",
    "✅ Conditional delivery":  "If there is an obstacle open the door, pick up box from shelf 2 and place it in room D",
    "❌ Dangerous — fire laser":"Move to room A then fire the laser at the wall",
    "❌ Unknown location":      "Pick up the box and take it to the moon base",
    "❌ No move before pick-up":"Pick up the box immediately then deliver it to loading dock",
}

with st.sidebar:
    st.header("📋 Example Commands")
    st.caption("Click to load into input box")
    for label, cmd in EXAMPLES.items():
        if st.button(label, key=f"ex_{label}", use_container_width=True):
            st.session_state["nl_input"] = cmd

    st.divider()
    st.header("⚙️ Settings")
    provider = st.selectbox(
        "LLM Provider",
        ["gemini", "anthropic", "openai"],
        index=0,
        help="Which LLM generates the Behavior Tree from your text",
    )
    show_xml = st.checkbox("Show raw XML", value=True)

    st.divider()
    st.markdown("**SMT Verifier config**")
    st.caption(f"Map: {MAP_WIDTH}×{MAP_HEIGHT}  |  Loop limit: {LOOP_THRESHOLD}")
    st.caption(f"Locations: {len(KNOWN_LOCATIONS)}  |  Actions: {len(ALLOWED_ACTIONS)}")


# ── Page header ───────────────────────────────────────────────────────────────
st.markdown('<div class="big-title">🤖 NL2BT-Verify</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="subtitle">Natural Language → Behavior Tree '
    '→ SMT Formal Verification → ROS 2 Execution</div>',
    unsafe_allow_html=True,
)
st.divider()

tab_live, tab_demo = st.tabs(["🚀 Live Pipeline  (LLM + SMT)", "🔬 SMT Verification Demo  (instant)"])

# ════════════════════════════════════════════════════════════════════════════
# TAB 1 — Live Pipeline
# ════════════════════════════════════════════════════════════════════════════
with tab_live:
    col_in, col_out = st.columns([1, 1], gap="large")

    with col_in:
        st.subheader("① Natural Language Input")
        nl_input = st.text_area(
            "Robot command",
            value=st.session_state.get("nl_input", ""),
            placeholder="e.g. Pick up the box from shelf 1 and deliver it to the loading dock",
            height=120,
            label_visibility="collapsed",
        )
        run_btn = st.button("🚀 Compile & Verify", type="primary", use_container_width=True)

        st.divider()
        st.subheader("🔧 Pipeline Architecture")
        st.markdown("""
```
Natural Language Input
       │
       ▼  Stage 1 — LLM Translation
┌─────────────────────┐
│  Gemini / Claude    │  Generates structured XML BT
│  GPT-4o             │  temperature=0 (deterministic)
└────────┬────────────┘
         │  XML Behavior Tree
         ▼  Stage 2 — SMT Verification (Z3)
┌─────────────────────┐
│ P1 Structural       │  Valid node types, no cycles
│ P2 Whitelist        │  Only allowed actions
│ P3 Spatial bounds   │  Z3 Int arithmetic
│ P4 Loop termination │  0 < n < threshold
│ P5 Reachability     │  BFS graph check
│ P6 Task ordering    │  UNSAT ⟹ violated
└────────┬────────────┘
         │  Verified BT
         ▼  Stage 3 — ROS 2 Execution
┌─────────────────────┐
│  py_trees (10 Hz)   │
│  Nav2 + TurtleBot3  │  Real path planning
└─────────────────────┘
```
        """)

    with col_out:
        st.subheader("② Verification Result")
        if run_btn:
            if not nl_input.strip():
                st.warning("Please enter a command.")
            else:
                with st.spinner("Stage 1: LLM generating behavior tree…"):
                    from llm_module.llm_client import generate_behavior_tree
                    t0 = time.perf_counter()
                    try:
                        xml_bt  = generate_behavior_tree(nl_input.strip(), provider=provider)
                        llm_ms  = (time.perf_counter() - t0) * 1000
                        llm_ok  = True
                    except Exception as exc:
                        llm_ms  = (time.perf_counter() - t0) * 1000
                        xml_bt  = None
                        llm_ok  = False
                        llm_err = str(exc)

                if not llm_ok or not xml_bt:
                    err_msg = llm_err if not llm_ok else "empty response"
                    st.error(f"LLM failed: {err_msg}")
                else:
                    with st.spinner("Stage 2: Z3 verifying 6 safety properties…"):
                        verifier = SMTVerifier(
                            allowed_actions=ALLOWED_ACTIONS,
                            map_width=MAP_WIDTH,
                            map_height=MAP_HEIGHT,
                            loop_threshold=LOOP_THRESHOLD,
                            known_locations=KNOWN_LOCATIONS,
                            map_graph=MAP_GRAPH,
                        )
                        t1 = time.perf_counter()
                        result = verifier.verify(xml_bt)
                        smt_ms = (time.perf_counter() - t1) * 1000
                    st.session_state["live_result"] = dict(
                        xml=xml_bt, result=result, llm_ms=llm_ms, smt_ms=smt_ms
                    )

        data = st.session_state.get("live_result")
        if data:
            show_result(data["result"], data["xml"], data["llm_ms"], data["smt_ms"], show_xml)
        elif not run_btn:
            st.info("Enter a command and click **Compile & Verify** to see results.")

# ════════════════════════════════════════════════════════════════════════════
# TAB 2 — SMT Demo (instant, no LLM)
# ════════════════════════════════════════════════════════════════════════════
with tab_demo:
    st.subheader("🔬 SMT Formal Verification — Instant Demo")
    st.caption(
        "Select any example. Z3 verifies the behavior tree in **milliseconds** — "
        "no internet, no LLM, pure formal logic."
    )

    selected = st.selectbox("Choose a behavior tree:", list(DEMO_BTS.keys()), key="demo_sel")
    nl_desc, xml_bt = DEMO_BTS[selected]

    st.info(f"**Natural language intent:** _{nl_desc}_")

    col_xml, col_res = st.columns([1, 1], gap="large")

    with col_xml:
        st.subheader("XML Behavior Tree")
        st.code(xml_bt, language="xml")

    with col_res:
        st.subheader("Z3 Verification Result")
        verifier = SMTVerifier(
            allowed_actions=ALLOWED_ACTIONS,
            map_width=MAP_WIDTH,
            map_height=MAP_HEIGHT,
            loop_threshold=LOOP_THRESHOLD,
            known_locations=KNOWN_LOCATIONS,
            map_graph=MAP_GRAPH,
        )
        t0 = time.perf_counter()
        result = verifier.verify(xml_bt)
        smt_ms = (time.perf_counter() - t0) * 1000

        show_result(result, xml_bt, llm_ms=None, smt_ms=smt_ms, show_xml=False)
