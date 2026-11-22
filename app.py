import os, json, hmac
from pathlib import Path
from datetime import datetime, date, time, timedelta
from zoneinfo import ZoneInfo
import streamlit as st
import pandas as pd
from src.core import YouTube, LocalWriter, LocalASR, data_dir

st.set_page_config(page_title="Shorts AI Scheduler", page_icon="▶️", layout="wide")
st.title("▶️ Shorts AI Scheduler")
st.caption("Cloud dashboard · self-hosted Hugging Face AI · Arabic metadata · YouTube publishing")

# Single-owner password gate
password = os.getenv("APP_PASSWORD", "")
if not password:
    st.error("Set APP_PASSWORD in your hosting provider before using this app.")
    st.stop()
if not st.session_state.get("ok"):
    with st.form("login"):
        pw = st.text_input("App password", type="password")
        go = st.form_submit_button("Sign in")
    if go and hmac.compare_digest(pw, password):
        st.session_state.ok = True
        st.rerun()
    elif go:
        st.error("Incorrect password.")
    st.stop()

DB = data_dir() / "workspace.json"
def load():
    if DB.exists():
        try: return json.loads(DB.read_text(encoding="utf-8"))
        except Exception: pass
    return {"videos": [], "metadata": {}, "queue": [], "settings": {}}
def save(x): DB.write_text(json.dumps(x, ensure_ascii=False, indent=2), encoding="utf-8")
state = load()

page = st.sidebar.radio("Workspace", ["Overview", "Video Library", "AI Metadata", "Publishing Queue", "Settings"])
st.sidebar.caption("Single-owner app. Keep its URL and password private.")
if st.sidebar.button("Sign out"):
    st.session_state.ok = False
    st.rerun()

# OAuth callback
if "code" in st.query_params and "state" in st.query_params:
    try:
        YouTube.finish(str(st.query_params["code"]), str(st.query_params["state"]))
        st.query_params.clear()
        st.success("YouTube connected.")
        st.rerun()
    except Exception as e:
        st.error(f"OAuth failed: {e}")

if page == "Overview":
    a,b,c = st.columns(3)
    a.metric("Imported uploads", len(state["videos"]))
    b.metric("Metadata records", len(state["metadata"]))
    c.metric("Queued", len(state["queue"]))
    st.markdown("### Workflow")
    st.markdown("1. Settings: upload Google OAuth **Web application** JSON.\n2. Connect your YouTube channel.\n3. Import existing uploads.\n4. Generate Arabic metadata in batches.\n5. Review and approve the batch.\n6. Build and test the daily publishing queue.")
    st.info("The Hugging Face models run on your hosting server. No Ollama or paid AI inference API is used.")
    st.warning("The YouTube API does not provide general video-file downloads. Caption access may be unavailable for some uploads. Local ASR requires a local media file uploaded to your hosted app. Visual frame understanding is not included in this version.")

elif page == "Settings":
    st.subheader("Settings & integrations")
    redirect = os.getenv("GOOGLE_REDIRECT_URI", "")
    st.markdown("### Google OAuth")
    st.write("Create an OAuth client of type **Web application** and add this exact URI to Authorized redirect URIs:")
    st.code(redirect or "Set GOOGLE_REDIRECT_URI in the hosting environment.")
    uploaded = st.file_uploader("Upload Google OAuth Web application JSON", type=["json"])
    if uploaded and st.button("Save Google credentials"):
        try:
            obj = json.loads(uploaded.getvalue())
            if "web" not in obj: raise ValueError("Use a Web application OAuth JSON, not Desktop app.")
            (data_dir() / "client_secret.json").write_text(json.dumps(obj), encoding="utf-8")
            st.success("Credentials saved on the server's persistent disk.")
        except Exception as e: st.error(str(e))
    if st.button("Connect / authorize YouTube", type="primary"):
        try:
            url, oauth_state = YouTube.start()
            st.session_state.oauth_state = oauth_state
            st.link_button("Continue to Google", url)
        except Exception as e: st.error(str(e))
    st.divider()
    st.markdown("### Local AI models")
    cfg = state["settings"]
    text_model = st.text_input("Arabic text model", cfg.get("text_model", "RightNowAI/RightNow-Arabic-0.5B-Turbo"))
    asr_model = st.text_input("Arabic ASR model", cfg.get("asr_model", "lemuralabs/lemura-arabic-asr-lite"))
    if st.button("Save model settings"):
        cfg.update(text_model=text_model.strip(), asr_model=asr_model.strip()); save(state); st.success("Saved.")
    st.caption("Models download to persistent server storage and run using server CPU/RAM. Check host resources before loading them.")
    st.divider()
    st.markdown("### Publishing defaults")
    pub = st.time_input("Daily publishing time (Morocco)", value=time(19,0))
    per_day = st.number_input("Videos per day", 1, 10, int(cfg.get("per_day",1)))
    start = st.date_input("First publishing date", value=date.fromisoformat(cfg.get("start_date") or (date.today()+timedelta(days=1)).isoformat()))
    if st.button("Save publishing defaults"):
        cfg.update(publish_time=pub.strftime("%H:%M"), per_day=int(per_day), start_date=start.isoformat()); save(state); st.success("Saved.")
    st.caption(f"Persistent data directory: {data_dir()}")

elif page == "Video Library":
    st.subheader("Existing YouTube uploads")
    if st.button("Import / refresh uploads", type="primary"):
        try:
            with st.spinner("Reading your channel uploads..."):
                state["videos"] = YouTube().uploads()
                save(state)
            st.success(f"Imported {len(state['videos'])} uploads.")
        except Exception as e: st.error(str(e))
    if state["videos"]:
        st.dataframe(pd.DataFrame(state["videos"]), use_container_width=True, hide_index=True)
        st.caption("Unfinished Studio upload drafts may not appear in the channel uploads playlist.")
    else: st.info("Connect YouTube first, then import.")

elif page == "AI Metadata":
    st.subheader("Generate and review Arabic metadata")
    if not state["videos"]:
        st.info("Import uploads first.")
    else:
        n = st.number_input("Batch size", 1, min(100,len(state["videos"])), min(5,len(state["videos"])))
        if st.button("Generate metadata", type="primary"):
            try:
                writer = LocalWriter(state["settings"].get("text_model","RightNowAI/RightNow-Arabic-0.5B-Turbo"))
                progress = st.progress(0)
                for i,v in enumerate(state["videos"][:int(n)]):
                    transcript = ""
                    try: transcript = YouTube().captions(v["id"])
                    except Exception: pass
                    if not transcript:
                        transcript = "[لا تتوفر ترجمة قابلة للوصول. لا تخترع محتوى الفيديو أو مراجع دينية. اعتمد على العنوان والوصف فقط واطلب المراجعة.]"
                    result = writer.make(v.get("title",""),v.get("description",""),transcript)
                    result.update(video_id=v["id"], approved=False, transcript_available=bool(transcript and not transcript.startswith("[")))
                    state["metadata"][v["id"]] = result
                    save(state); progress.progress((i+1)/int(n))
                st.success("Batch generated. Review below.")
            except Exception as e: st.error(f"Local model error: {e}")
        st.markdown("### Review")
        if state["metadata"]:
            rows=[{"Approve":x.get("approved",False),"Video ID":vid,"Arabic title":x.get("title",""),"Description":x.get("description",""),"Transcript available":x.get("transcript_available",False)} for vid,x in state["metadata"].items()]
            edited=st.data_editor(pd.DataFrame(rows),use_container_width=True,hide_index=True,num_rows="fixed")
            if st.button("Save review"):
                for _,r in edited.iterrows():
                    vid=r["Video ID"]; state["metadata"][vid].update(approved=bool(r["Approve"]),title=str(r["Arabic title"])[:100],description=str(r["Description"])[:5000])
                save(state); st.success("Review saved.")
        st.divider()
        st.markdown("### Optional local media transcription")
        st.caption("If captions are unavailable, upload a media copy. It is sent to your own cloud server for local transcription.")
        vid=st.selectbox("Video", [v["id"] for v in state["videos"]])
        media=st.file_uploader("Video/audio file",type=["mp4","mov","mkv","webm","mp3","wav","m4a"])
        if media and st.button("Transcribe media"):
            try:
                p=data_dir()/"uploads"; p.mkdir(exist_ok=True)
                f=p/media.name; f.write_bytes(media.getvalue())
                transcript=LocalASR(state["settings"].get("asr_model","lemuralabs/lemura-arabic-asr-lite")).run(f)
                state.setdefault("transcripts",{})[vid]=transcript; save(state)
                st.text_area("Transcript",transcript,height=180)
            except Exception as e: st.error(str(e))

elif page == "Publishing Queue":
    st.subheader("Daily publishing queue")
    cfg=state["settings"]
    if st.button("Build queue from approved videos",type="primary"):
        approved=[x for x in state["metadata"].values() if x.get("approved")]
        if not approved: st.warning("Approve metadata first.")
        else:
            start=date.fromisoformat(cfg.get("start_date") or (date.today()+timedelta(days=1)).isoformat())
            hh,mm=map(int,cfg.get("publish_time","19:00").split(":"))
            q=[]
            for i,x in enumerate(approved):
                day=start+timedelta(days=i//int(cfg.get("per_day",1)))
                dt=datetime.combine(day,time(hh,mm),tzinfo=ZoneInfo("Africa/Casablanca"))
                q.append({"video_id":x["video_id"],"title":x["title"],"publish_at":dt.isoformat(),"status":"Pending"})
            state["queue"]=q; save(state); st.success(f"Prepared {len(q)} slots.")
    if state["queue"]:
        st.dataframe(pd.DataFrame(state["queue"]),use_container_width=True,hide_index=True)
        st.warning("Test one eligible private video first. YouTube's scheduling API has restrictions.")
        test=st.checkbox("Test mode — do not change YouTube",value=True)
        confirm=st.checkbox("I reviewed this queue and authorize scheduling.")
        if st.button("Schedule queue",type="primary",disabled=not confirm):
            if test: st.success("Test only: no YouTube changes made.")
            else:
                success=0
                for q in state["queue"]:
                    try:
                        x=state["metadata"][q["video_id"]]
                        YouTube().schedule(q["video_id"],x["title"],x["description"],q["publish_at"])
                        q["status"]="Scheduled"; success+=1
                    except Exception as e: q["status"]="Error: "+str(e)
                save(state); st.success(f"Scheduled {success} videos."); st.dataframe(pd.DataFrame(state["queue"]),use_container_width=True,hide_index=True)

st.divider()
st.caption("Single-owner prototype. Review religious quotations and claims before publishing.")
