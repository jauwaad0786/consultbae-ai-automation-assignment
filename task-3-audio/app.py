"""
app.py — Task 3: Mini Audio Collection App (frontend)

Run with:
    streamlit run app.py

Requires (pip install):
    streamlit pymysql pydub numpy

Also requires ffmpeg installed on your system (pydub shells out to it):
    sudo apt install ffmpeg      # linux
    brew install ffmpeg          # mac
"""

import streamlit as st
import backend

st.set_page_config(page_title="ConsultBae Audio Collection", layout="centered")

# Make sure the submissions table exists before anything else runs.
backend.init_db()

st.title("🎙️ Audio Collection — Gig Worker Submissions")

tab_submit, tab_list = st.tabs(["Submit Audio", "All Submissions"])

# ---------------------------------------------------------------------------
# TAB 1 — Submission form
# ---------------------------------------------------------------------------
with tab_submit:
    st.subheader("Submit a recording")

    name = st.text_input("Full name")
    phone = st.text_input("Phone number", placeholder="e.g. 9000000254")

    st.caption("Record with your mic OR upload a file — either works.")
    recorded_audio = st.audio_input("Record audio")
    uploaded_file = st.file_uploader(
        "...or upload an audio file", type=["wav", "mp3", "m4a", "ogg", "webm"]
    )

    audio_source = recorded_audio or uploaded_file

    if audio_source is not None:
        st.audio(audio_source)

    if st.button("Submit", type="primary"):
        if not name.strip():
            st.error("Name is required.")
        elif not phone.strip():
            st.error("Phone number is required.")
        elif audio_source is None:
            st.error("Record or upload an audio file first.")
        else:
            with st.spinner("Saving and processing audio..."):
                audio_bytes = audio_source.getvalue()
                # st.audio_input returns a WAV-wrapped buffer; file_uploader keeps its name.
                original_filename = getattr(audio_source, "name", "recording.wav")
                try:
                    result = backend.process_submission(
                        name=name, phone=phone,
                        audio_bytes=audio_bytes, original_filename=original_filename,
                    )
                    st.success(f"Submitted! (submission_id={result['submission_id']})")
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("Duration (s)", result["duration_sec"])
                    c2.metric("Sample rate (Hz)", result["sample_rate_hz"])
                    c3.metric("Bitrate (kbps)", result["bitrate_kbps"])
                    c4.metric("Loudness (dB)", result["loudness_db"])
                    st.caption(
                        f"Rough quality estimate: **{result['noise_estimate']}** "
                        f"(SNR ≈ {result['snr_db']} dB)"
                    )
                except Exception as e:
                    st.error(f"Failed to process submission: {e}")

# ---------------------------------------------------------------------------
# TAB 2 — List view with play button
# ---------------------------------------------------------------------------
with tab_list:
    st.subheader("All submissions")
    if st.button("Refresh"):
        st.rerun()

    rows = backend.get_all_submissions()
    if not rows:
        st.info("No submissions yet.")
    else:
        for r in rows:
            with st.container(border=True):
                col_meta, col_play = st.columns([3, 2])
                with col_meta:
                    st.markdown(f"**{r['name']}** — {r['phone']}")
                    st.caption(
                        f"Duration: {r['duration_sec']}s · "
                        f"Sample rate: {r['sample_rate_hz']} Hz · "
                        f"Bitrate: {r['bitrate_kbps']} kbps · "
                        f"Loudness: {r['loudness_db']} dB · "
                        f"Quality: {r['noise_estimate']} (SNR {r['snr_db']} dB)"
                    )
                    st.caption(f"person_id: {r['person_id']} · submitted: {r['created_at']}")
                with col_play:
                    try:
                        st.audio(r["audio_path"])
                    except Exception:
                        st.warning("Audio file not found on disk.")
