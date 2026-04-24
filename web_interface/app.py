"""
Streamlit web interface for the NL2BT-Verify pipeline.
Run with: streamlit run web_interface/app.py
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
from pipeline import run_pipeline

st.set_page_config(page_title="NL2BT Compiler", page_icon="🤖", layout="wide")

st.title("NL2BT-Verify: Natural Language → Robot Behavior Tree")
st.caption("Neuro-Symbolic compiler with SMT-based formal verification")

col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("Input")
    nl_input = st.text_area(
        "Natural Language Command",
        placeholder="e.g. Pick up the box from shelf 3 and deliver it to the loading dock",
        height=100,
    )
    provider = st.selectbox("LLM Provider", ["anthropic", "openai"])

    if st.button("Compile & Verify", type="primary"):
        if not nl_input.strip():
            st.warning("Please enter a command.")
        else:
            with st.spinner("Running pipeline..."):
                result = run_pipeline(nl_input, execute=False)
            st.session_state["result"] = result

with col2:
    st.subheader("Output")
    result = st.session_state.get("result")

    if result:
        if result["status"] == "success":
            st.success("Verified — safe to execute")

            st.subheader("Safety Check Results")
            for check in result.get("checks", []):
                icon = "✅" if check["passed"] else "❌"
                st.write(f"{icon} **{check['name'].replace('_', ' ').title()}** — {check['detail']}")

            st.subheader("Generated XML Behavior Tree")
            st.code(result["xml"], language="xml")

        elif result["status"] == "rejected":
            st.error("Rejected by SMT Verifier")
            st.subheader("Violations")
            for err in result.get("errors", []):
                st.write(f"- {err}")

            st.subheader("Rejected XML")
            st.code(result.get("xml", ""), language="xml")

        else:
            st.error(f"Pipeline error: {result.get('message')}")
