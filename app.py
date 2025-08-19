# aut-flexibility-app/app.py

import sys 
import streamlit as st
import time
from datetime import datetime
import random
from concurrent.futures import ThreadPoolExecutor


# --- Required Imports ---
# These modules are assumed to exist in your project structure
from timer import start_timer, elapsed # Assumes functions for timing
from llm_client import map_to_category, evaluate_responses # Assumes functions for LLM interaction
from feedback_engine import SessionState, PHASES, CATEGORY_LIST, SUGGESTION_LIST # Use components from your feedback_engine.py
from logger import log # Assumes a logging function

# --- Get Prolific query params ---
params = st.query_params
participant = params.get("PROLIFIC_PID", "")
study_id = params.get("STUDY_ID", "")
# Provide a default Prolific URL for testing, use actual one if present
default_return_url = "https://app.prolific.com/submissions/complete?cc=YOUR_CODE"
return_url = params.get("return_url", default_return_url)

# ── 1.  Background executor lives for the whole app ───────────────────────
# Pick the best decorator available
singleton = getattr(st, "singleton",
            getattr(st, "experimental_singleton",
                    lambda **kw: (lambda f: f)))   # no-op fallback

@singleton(show_spinner=False)
def get_log_executor() -> ThreadPoolExecutor:
    return ThreadPoolExecutor(max_workers=1, thread_name_prefix="logger")


log_executor = get_log_executor()

def async_log(data: dict):
    """Queue logging on the executor so UI can refresh immediately."""
    def _safe_log(d):
        try:
            log(d)
        except Exception:
            import traceback
            traceback.print_exc(file=sys.stderr)

    log_executor.submit(_safe_log, data)
# ───────────────────────────────────────────────────────────────────────────

def simple_levenshtein(s1, s2):
    """Compute a simple Levenshtein distance between two strings."""
    if len(s1) < len(s2):
        return simple_levenshtein(s2, s1)

    if len(s2) == 0:
        return len(s1)

    previous_row = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row

    return previous_row[-1]


# -----------------------------------------
# Every time you need to show / update the list:
def show_responses(responses, disqualified):
    if not responses:
        return

    num_cols = min(3, len(responses))
    cols = st.columns(num_cols)

    for i, r in enumerate(responses):
        col = cols[i % num_cols]
        use_text = r['use_text']
        if r.get("category") == "Disqualified":
            display_text = f"- {use_text} _(flagged for review)_"
        else:
            display_text = f"- {use_text}"

        col.markdown(display_text)


# --- Group Assignment ---
# Assign group based on participant_id once
if "group_id" not in st.session_state:
    # Use a simple hash for demonstration if participant ID exists, else random
    # Ensure hash result is an integer before modulo
    try:
        p_hash = int(hash(participant))
        st.session_state.group_id = p_hash % 4 if participant else random.randint(0, 3)
    except Exception: # Fallback if hashing fails
         st.session_state.group_id = random.randint(0, 3)




group_id = st.session_state.group_id

# Group assignments determine object order and hint availability
# Object order: Groups 0, 1 get brick then newspaper; Groups 2, 3 get newspaper then brick
# Hint availability: Groups 0, 2 have hints enabled during the extension phase (phase 1)
if group_id in [0, 1]:
    # First object for phases 0, 1; Second object for phase 2 ('transfer')
    object_order = ["brick", "newspaper"]
else:
    object_order = ["newspaper", "brick"]

# Hint enabled for groups 0 and 2 (controlled within SessionState based on phase)
hint_enabled_for_group = group_id in [0, 2]

# --- Initialize Session State ---
if "session" not in st.session_state:
    # Initialize SessionState from feedback_engine.py
    # Pass hint availability based on group
    st.session_state.session = SessionState(objects=object_order, hints=hint_enabled_for_group)
    st.session_state.started = False
    # Store responses per phase block - cleared before the last phase
    st.session_state.responses = []
    st.session_state.recess_mode = False
    # Store disqualified responses if using evaluate_responses
    st.session_state.disqualified = []

session = st.session_state.session
# Ensure responses list exists in session state
if "responses" not in st.session_state:
     st.session_state.responses = []
# Ensure disqualified list exists
if "disqualified" not in st.session_state:
    st.session_state.disqualified = []
if "pending_futures" not in st.session_state:
    st.session_state.pending_futures = []

# --- App Flow ---

if not st.session_state.started:
    # --- Welcome Screen ---
    st.title("AUT Flexibility Study")
    st.write("Welcome! This study involves thinking of creative uses for common objects.")
    st.write("You will be presented with objects one at a time and asked to list as many different uses as you can within the time limit.")
    st.write(f"Participant ID: `{participant or 'TEST'}`")
    st.write(f"Study ID: `{study_id or 'TEST'}`")

    consent_box = st.container()       # <— wrap the whole consent area

    with consent_box:
        st.subheader("Before we begin, please confirm:")

        st.write("- I understand my responses and response times will be collected.")
        st.write("- My Prolific ID is used only for payment and will be stored separately from my responses.")
        st.write("- Data will be used for research in anonymized/aggregate form and may be shared as anonymized datasets.")
        st.write("- **Data storage and retention:** Data are stored securely on institutional or approved cloud servers and retained for up to **10 years**.")
        st.write("- **No sensitive data:** This study does not collect special-category data (e.g., race/ethnicity, religious or political beliefs, or health data).")
        st.write("- **Withdrawal:** I may stop at any time by returning the study on Prolific, and I may request deletion of my submitted data later by emailing the researcher with my Prolific ID.")
        st.write("- **Purpose of data use:** This study is conducted for **academic research purposes only**. Data will not be used for marketing or commercial purposes.")
        st.write("- **Legal framework:** Your data are handled in accordance with the UK GDPR / EU GDPR and the research ethics policies of Tel Aviv University.")
        consent_agreed = st.checkbox("I have read and consent to participate.")

    start_placeholder = st.empty()

    if not st.session_state.started:
        with start_placeholder.container():
            st.write("Please press Start when you are ready to begin.")
            if st.button("Start", disabled=not consent_agreed):
                st.session_state.started = True
                session.started = True
                consent_box.empty() 
                start_placeholder.empty()
                st.rerun()


else:
    # --- Study Phases ---

    # Check if study is complete
    if session.phase_index >= len(PHASES):
        st.success("🎉 You have completed the study!")
        st.balloons()
        
        # show answers straight away
        st.subheader("Your responses in this last phase:")
        show_responses(st.session_state.responses,
                       st.session_state.disqualified)

        # keep them on screen for ~10 s (blocking but simple)
        time.sleep(5)
        # Provide a clickable link to return to Prolific
        completion_code = "C6KNGZWE" # Replace with your actual Prolific completion code
        prolific_url = f"{return_url}?cc={completion_code}" if return_url != default_return_url else f"https://app.prolific.com/submissions/complete?cc={completion_code}"

        # Use st.link_button for a cleaner button link if Streamlit version supports it
        # st.link_button("Click here to complete the study on Prolific", prolific_url)
        # Fallback using markdown HTML for broader compatibility
        st.markdown(f"""
        <a href="{prolific_url}" target="_blank">
            <button style='padding: 10px 20px; background-color: #4CAF50; color: white; border: none; border-radius: 5px; cursor: pointer;'>
                Click here to complete the study on Prolific
            </button>
        </a>
        """, unsafe_allow_html=True)
        st.markdown(f"Or copy this code: `{completion_code}`")
        for fut in st.session_state.pending_futures:
            try:
                fut.result(timeout=5)   # 5 s should be plenty
            except Exception:
                pass                    # already printed inside _safe_log
            
        st.stop() # Stop script execution after completion

    # Check for recess mode
    elif st.session_state.recess_mode:
        st.header("🧘 Take a short break")
        st.write("You can rest for 20 seconds. The next phase will start automatically.")
        countdown = st.empty()
        recess_duration = 20 # Standard 30 second break
        for i in range(recess_duration, 0, -1):
            countdown.markdown(f"⏳ Resuming in **{i}** seconds...")
            time.sleep(1)
        st.session_state.recess_mode = False
        st.rerun()

    # --- Active Phase ---
    else:
        # Ensure phase has started if it hasn't (e.g., first run after 'Start' button)
        if session.phase_start is None:
             session.start_phase()

        # --- Setup or reset hints depending on phase ---
        if session.phase_index == 1 and hint_enabled_for_group:
            if st.session_state.get("hint_phase", -1) != 1:
                # Phase 2 entered, and hints group → generate hints
                st.session_state.current_hints = session.get_hint()
                st.session_state.hint_phase = 1
        else:
            if st.session_state.get("hint_phase", -1) != session.phase_index:
                # Different phase entered → clear hints
                st.session_state.current_hints = []
                st.session_state.hint_phase = session.phase_index

            

        obj = session.current_object # Get object from SessionState property
        phase_info = session.current_phase # Get phase info from SessionState property
        duration = phase_info["duration_sec"]


        st.subheader(f"{phase_info['name'].title()}: ")
        st.header(f"★★★  {obj.upper()}  ★★★")
        st.markdown(f"**Participant:** `{participant or 'TEST'}` | **Group:** `{group_id}` | **Phase:** `{session.phase_index + 1}/{len(PHASES)}`")

        timer_placeholder = st.empty()
        form_placeholder = st.empty() # Placeholder for the form

        with form_placeholder.form(key="use_form", clear_on_submit=True):
            use = st.text_input("Enter one use:", key=f"use_{session.phase_index}_{session.trial_count}")

            
            # --- Hint Logic ---
            hint_placeholder = st.empty()

            hints = st.session_state.get("current_hints", [])

            if hints:
                with hint_placeholder.container():
                    st.markdown("**Hint: You could try a use related to the following categories\n (but it is forbidden to use the category names) :**")
                    for h in hints:
                        st.markdown(f"- {h}")
            else:
                hint_placeholder.empty()
            # --- End Hint Logic ---


            submitted = st.form_submit_button("Submit use")

        if submitted and use.strip():
            standardized_use = use.strip().lower()

            existing_uses = [r["use_text"].strip().lower() for r in st.session_state.responses]

            # Check for exact duplicate
            if standardized_use in existing_uses:
                st.warning("⚠️ You already submitted that exact use! Try a different idea.")

            # Check for very close match (distance 1–2)
            elif any(simple_levenshtein(standardized_use, prev_use) <= 2 for prev_use in existing_uses):
                st.warning("⚠️ Your idea is very similar to a previous one! Try a more different idea.")

            else:
            
                # Record the use via SessionState method
                # This method handles timing relative to phase start and calls map_to_category
                response_record = session.record_use(use)

                # Append full record for potential evaluation and logging
                full_record = {
                    **response_record, # Includes trial, use_text, category, response_time_sec
                    "phase_index": session.phase_index,
                    "object": obj
                }
                st.session_state.responses.append(full_record)
                st.success("✅ Response recorded.")
                time.sleep(0.5) # Keep success message visible briefly                
                # Log the response
                log_data = {
                    "timestamp": datetime.utcnow().isoformat(),
                    "participant": participant,
                    "study_id": study_id,
                    "group_id": group_id,
                    "phase_name": phase_info["name"],
                    "phase_index": session.phase_index,
                    "object": obj,
                    "trial": response_record["trial"],
                    "use_text": use,
                    "category": response_record["category"],
                    "response_time_sec_phase": response_record["response_time_sec"], # Time since phase start
                    "hints_enabled_group": hint_enabled_for_group,
                    "shown_hints": hints # Log the hints that were actually shown
                }
                #log(log_data) # Call your logging function
                # **Non-blocking** logging
                future = async_log(log_data)
                st.session_state.pending_futures.append(future)   # optional
                
                st.rerun() # Rerun to update timer and clear form


        # --- Display Disqualified/Responses ---
        last_phase_index = len(PHASES) - 1


                
        responses_box = st.empty()

        if st.session_state.responses:
            with responses_box.container():
                st.subheader("Your responses so far:")
                show_responses(st.session_state.responses, st.session_state.disqualified)
        else:
            responses_box.empty()





        # --- Timer Logic ---
        if session.phase_start: # Ensure phase has started before calculating time
             elapsed_time = elapsed(session.phase_start) # Use elapsed from timer module
             remaining = duration - elapsed_time

             if remaining <= 0:
                 timer_placeholder.markdown("⏱️ Time remaining: **00:00**")

                 times_up_placeholder = st.empty()
                 with times_up_placeholder.container():
                    st.warning("⏰ Time's up for this phase!")
                 time.sleep(1.5)
                 times_up_placeholder.empty()


                # --- Evaluate at phase end ---
                 if st.session_state.responses:
                    eval_result = evaluate_responses(session.current_object, st.session_state.responses)
                    print(eval_result)
                    # Mark responses based on final batch disqualification
                    for r in st.session_state.responses:
                        if r["use_text"] in eval_result.get("disqualified", []):
                            r["category"] = "Disqualified"

                    # Store disqualified texts separately for easy UI
                    st.session_state.disqualified = [r["use_text"] for r in st.session_state.responses if r["category"] == "Disqualified"]




                 # --- Phase Transition ---
                 next_phase_index = session.phase_index + 1
                 #st.write("🔍 DEBUG › responses =", responses)  
                 # Clear responses before starting the *last* phase
                 if next_phase_index == last_phase_index:
                     if st.session_state.responses != []:
                        st.session_state.responses = []
                        st.session_state.disqualified = [] # Also clear disqualified list
                        disqualified = st.session_state.get("disqualified", [])   
                     

                 session.next_phase() # This increments phase_index

                 # Trigger recess between phases 0->1 and 1->2
                 # Check the index we are *moving to*
                 if next_phase_index in [1, 2] and next_phase_index < len(PHASES):
                      st.session_state.recess_mode = True

                 # Start the next phase (timer, etc.) - SessionState needs start_phase called explicitly
                 if next_phase_index < len(PHASES):
                      session.start_phase() # Reset timer and trial count for the new phase

                 st.rerun() # Rerun to show recess or next phase/completion screen
             else:
                 # Update timer display smoothly using a loop within the script run
                 # This avoids rerunning the entire script every second
                 update_interval = 0.5 # How often to update the display (in seconds)
                 display_secs = -1 # Force initial display update

                 while remaining > 0:
                     current_secs = int(remaining)
                     if current_secs != display_secs: # Only update markdown when seconds change
                          mins, secs = divmod(current_secs, 60)
                          timer_placeholder.markdown(f"⏱️ Time remaining: **{mins:02d}:{secs:02d}**")
                          display_secs = current_secs

                     time.sleep(update_interval)
                     elapsed_time = elapsed(session.phase_start)
                     remaining = duration - elapsed_time

                     # Check if form was submitted during sleep (Streamlit doesn't easily support this check here)
                     # A full rerun handles submissions correctly. This loop is just for smooth timer display.
                     # If precise sub-second accuracy linked to submission is needed, this approach might need adjustment.

                 # Ensure timer shows 00:00 when loop finishes due to time running out
                 timer_placeholder.markdown("⏱️ Time remaining: **00:00**")
                 st.rerun() # Rerun to trigger the phase transition logic above
        else:
             # Should not happen if start_phase is called correctly, but good failsafe
             st.warning("Waiting for phase to start...")
             time.sleep(1)
             st.rerun()






