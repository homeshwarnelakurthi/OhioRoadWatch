import streamlit as st

import db
from agent import build_agent
from config import Config

st.set_page_config(page_title="OhioRoadWatch", layout="wide")
st.title("OhioRoadWatch — live Ohio highway conditions")
st.caption("Data via ODOT's OHGO public API. Snapshot conditions labeled by an NVIDIA NIM vision model.")

cfg = Config()
db.init_db(cfg.db_path)

col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("Camera conditions")
    cameras = db.all_cameras()
    if not cameras:
        st.info("No cameras yet — run `python ingest.py` first.")
    for cam in cameras:
        snap = db.latest_snapshot_for_camera(cam["id"])
        label = f"{cam['location']} — {cam['main_route'] or ''}"
        with st.expander(label):
            if snap and snap.get("image_path"):
                st.image(snap["image_path"], width=400)
            if snap:
                st.write(f"**Condition:** {snap['label']} (confidence {snap['confidence']:.2f})")
                st.caption(snap["notes"])
                st.caption(f"Captured: {snap['captured_at']}")
            else:
                st.write("No snapshot yet for this camera.")

with col2:
    st.subheader("Ask OhioRoadWatch")
    if "agent" not in st.session_state:
        st.session_state.agent = build_agent()
    if "history" not in st.session_state:
        st.session_state.history = []

    question = st.text_input(
        "Ask about current conditions",
        placeholder="Is I-76 near Kent clear right now?",
    )
    if st.button("Ask") and question:
        with st.spinner("Checking live conditions..."):
            result = st.session_state.agent.invoke({"messages": [("user", question)]})
            answer = result["messages"][-1].content
        st.session_state.history.append((question, answer))

    for q, a in reversed(st.session_state.history):
        st.markdown(f"**You:** {q}")
        st.markdown(f"**OhioRoadWatch:** {a}")
