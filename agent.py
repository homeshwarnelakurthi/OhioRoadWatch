"""LangGraph agent over the local DB and vector store, powered by an
NVIDIA NIM-hosted tool-calling model via the official langchain-nvidia-ai-endpoints
integration (ChatNVIDIA supports bind_tools, which create_react_agent needs).
"""
import os

from langchain_core.tools import tool
from langchain_nvidia_ai_endpoints import ChatNVIDIA
from langgraph.prebuilt import create_react_agent

import db as dbmod
from vector_store import search as vector_search

# Llama 3.1 70B is NVIDIA's confirmed tool-calling-capable model on the free
# tier. To see other tool-calling options, run:
#   from langchain_nvidia_ai_endpoints import ChatNVIDIA
#   [m.id for m in ChatNVIDIA.get_available_models() if m.supports_tools]
AGENT_MODEL = os.environ.get("NIM_AGENT_MODEL", "meta/llama-3.1-70b-instruct")


@tool
def list_cameras_near(location_query: str) -> str:
    """Find OHGO cameras whose location or route text matches the query,
    e.g. 'I-76', 'Akron', 'Kent'."""
    cameras = dbmod.find_cameras_by_text(location_query)
    if not cameras:
        return "No cameras found matching that location."
    lines = [f"- {c['id']}: {c['location']} ({c['main_route']})" for c in cameras[:10]]
    return "\n".join(lines)


@tool
def get_camera_condition(camera_id: str) -> str:
    """Get the latest classified condition (clear/wet/snow/fog/etc.) for a
    specific camera id, as returned by list_cameras_near."""
    snap = dbmod.latest_snapshot_for_camera(camera_id)
    if not snap:
        return f"No recent snapshot classification for camera {camera_id}."
    return (
        f"Camera {camera_id} as of {snap['captured_at']}: {snap['label']} "
        f"(confidence {snap['confidence']:.2f}) - {snap['notes']}"
    )


@tool
def search_conditions(query: str) -> str:
    """Semantic search over indexed incidents and camera conditions
    statewide. Use natural language, e.g. 'snow near Akron' or 'accidents on I-71'."""
    results = vector_search(query, n_results=5)
    docs = results.get("documents", [[]])[0]
    if not docs:
        return "No matching conditions found."
    return "\n".join(f"- {d}" for d in docs)


SYSTEM_PROMPT = (
    "You are OhioRoadWatch, an assistant that reports live Ohio highway "
    "conditions using OHGO traffic camera and incident data. Always ground "
    "answers in tool results rather than guessing. If data looks stale or "
    "is missing for the location asked about, say so plainly."
)


def build_agent():
    model = ChatNVIDIA(model=AGENT_MODEL, temperature=0)  # reads NVIDIA_API_KEY from env
    tools = [list_cameras_near, get_camera_condition, search_conditions]
    return create_react_agent(model, tools, prompt=SYSTEM_PROMPT)


if __name__ == "__main__":
    agent = build_agent()
    result = agent.invoke(
        {"messages": [("user", "What's the road condition like near Kent or Akron right now?")]}
    )
    print(result["messages"][-1].content)
