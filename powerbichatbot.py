# Web implementation of chatbot with RAG and SQL analytical features
import os
import vertexai
from vertexai import agent_engines
import streamlit as st
from dotenv import load_dotenv
import time
from helpersv2 import *
import re
import streamlit_highcharts as hct

load_dotenv(override=True)
# Setting up Vertex Agent
vertexai.init(
    project=os.environ.get("GOOGLE_CLOUD_PROJECT"),
    location=os.environ.get("GOOGLE_CLOUD_LOCATION"),
    staging_bucket=os.environ.get("GOOGLE_CLOUD_STAGING_BUCKET"),
)
remote_app = agent_engines.get(os.environ.get("AGENT_RESOURCE_ID"))
user_id = "user"
 
# Global Constants
INPUT_COST_PER_TOKEN = 0.30 / 1_000_000
OUTPUT_COST_PER_TOKEN = 2.50 / 1_000_000

# ---- Helper Functions for Chatbot Application ----
def query_bot(message):
    final_response = None
    total_prompt_tokens = 0
    total_output_tokens = 0

    for event in remote_app.stream_query(
        user_id=user_id,
        session_id=st.session_state.current_session,
        message=message
    ):
        # Store event
        st.session_state.sessions[st.session_state.current_session]["events"].append(event)
        print(event)
        final_response = event

        usage = event.get("usage_metadata", {})
        total_prompt_tokens += usage.get("prompt_token_count", 0)
        total_output_tokens += usage.get("candidates_token_count", 0)

    # Calculate token cost
    cost = total_prompt_tokens * INPUT_COST_PER_TOKEN + total_output_tokens * OUTPUT_COST_PER_TOKEN
    session = st.session_state.sessions[st.session_state.current_session]
    session["cost"] = session.get("cost", 0.0) + cost

    if "content" in final_response and "parts" in final_response["content"] and "text" in final_response["content"]["parts"][0]:
        return final_response["content"]["parts"][0]["text"], cost
    else:
        return "No response from AI Engine.", cost

# Create new session
def new_session():
    session = remote_app.create_session(user_id=user_id)
    st.session_state.current_session = session['id']
    st.session_state.sessions[session['id']] = {"name":f"New Session", "messages":[], "events": []}

# Delete current session
def delete_session():
    remote_app.delete_session(user_id=user_id, session_id=st.session_state.current_session)
    del st.session_state.sessions[st.session_state.current_session]
    if st.session_state.sessions:
        st.session_state.current_session = list(st.session_state.sessions.keys())[-1]
    else:
        new_session()

# Clear current chat without deleting session
def clear_chat():
    st.session_state.sessions[st.session_state.current_session]["messages"] = []

# Function to display chat history with graphs
def display_chat_history():
    st.title("🧠 Chat with Analytics Agent")
    for msg in st.session_state.sessions[st.session_state.current_session]["messages"]:
        # Display user message
        if msg["role"] == "user":
            with st.chat_message("user"):
                st.write(msg["content"])
        # Display bot response
        elif msg["role"] == "assistant":
            with st.chat_message("assistant"):
                # Time and cost info
                st.markdown(f"""
                  <div style="display: flex; justify-content: flex-start; font-size: 12px; color: gray; margin-bottom: 10px;">
                      <span style="margin-right: 2em;">Time elapsed: {msg["time"]:.2f}s</span>
                      <span>Cost accrued: {msg["cost"]:.4f}</span>
                  </div> """, unsafe_allow_html=True)
                # Textual Response
                st.write(msg["content"])
                if msg["graphs"]:
                    for graph, table in msg.get("graphs", []):
                        # Display graph
                        hct.streamlit_highcharts(graph,500)
                        st.dataframe(table)

# Sidebar module for session manager
def sidebar():
    st.sidebar.title("🗂️ Session Manager")
    with st.sidebar.expander("Manager", expanded=True):
        # Buttons to manage session
        st.markdown(f""":gray[🔑 **Session Name:**]  
                      *{st.session_state.sessions[st.session_state.current_session]['name']}*
                      """)
        st.markdown(f""":green[💲 **Session Cost:**]
                    *{round(st.session_state.sessions[st.session_state.current_session].get("cost", 0), 5)}*
                    """)
        if st.button("➕ New Session", key="top_new"):
            new_session()
        if st.button("🗑️ Delete Session", key="top_delete", type='primary'):
            delete_session()
        if st.button("♻️ Clear Chat", key="top_clear", type='primary'):
            clear_chat()

    st.sidebar.markdown("### 🗒️ Session List")
    # Rename current session
    if st.session_state.sessions:
        new_name = st.sidebar.text_input("New Name", st.session_state.sessions[st.session_state.current_session]["name"])
        if st.sidebar.button("Rename Session", type='primary', key='rename_session'):
            st.session_state.sessions[st.session_state.current_session]["name"] = new_name
            st.rerun()

  # List all sessions
    for sid in list(st.session_state.sessions.keys()):
        if sid != st.session_state.current_session:
            if st.sidebar.button(st.session_state.sessions[sid]["name"], key=sid, type='tertiary'):
                st.session_state.current_session = sid
                st.rerun()

    st.sidebar.markdown(f""":red[**Click session name to switch.**]""")
    st.sidebar.markdown("---")

    # Log agent events
    with st.sidebar.expander("📝 Event Logger", expanded=True):
        events = st.session_state.sessions[st.session_state.current_session]["events"]
        if events:
            for idx, event in enumerate(events):
                # Log events based on their type
                if 'function_call' in event['content']['parts'][0]:
                    with st.expander(f"**{idx}**: {event['content']['parts'][0].get('function_call').get('name', 'N/A')}"):
                        st.json(event)
                # Check if the event contains a function response
                elif 'function_response' in event['content']['parts'][0]:
                    with st.expander(f"**{idx}**: {event['content']['parts'][0].get('function_response').get('name', 'N/A')}"):
                        st.json(event)
                # For textual events
                elif 'text' in event['content']['parts'][0]:
                    text_output = event['content']['parts'][0].get('text')
                    with st.expander(f"**{idx}**: {text_output[:30] if len(text_output) > 30 else text_output}"):
                        st.json(event)
        else:
            st.markdown(f":blue[***Logged Session Events Appear Here***]")

# Persistent data
if "sessions" not in st.session_state:
    st.session_state.sessions = {}
if "current_session" not in st.session_state:
    st.session_state.current_session = 0
    new_session()

# Display history and sidebar
sidebar()
display_chat_history()

# Ask for user query
prompt = st.chat_input("Type your query here...")
if prompt:
    # Display User message
    with st.chat_message("user"):
        st.write(prompt)
        st.session_state.sessions[st.session_state.current_session]["messages"].append({"role": "user", "content": prompt})

    # Query chatbot with user prompt and display response
    with st.chat_message("assistant"):
        t = time.time()
        with st.spinner("Thinking...", show_time=True):
            response, cost = query_bot(prompt)
            tt = time.time() - t
            # Extract response and add to chat history
            text, graphs = split_response(response)
            text = re.sub(r'(?<!\\)\$', r'\$', text)
            st.markdown(f"""
              <div style="display: flex; justify-content: flex-start; font-size: 12px; color: gray; margin-bottom: 10px;">
                  <span style="margin-right: 2em;">Time elapsed: {tt:.2f}s</span>
                  <span>Cost accrued: {cost:.4f}</span>
              </div> """, unsafe_allow_html=True)
            st.write(text)
            if graphs:
                for graph, table in graphs:
                    # Display graph
                    hct.streamlit_highcharts(graph,500)
                    st.dataframe(table)
            st.session_state.sessions[st.session_state.current_session]["messages"].append({"role": "assistant", 
                                                        "content": text, "graphs": graphs, "cost": cost, "time": tt})

