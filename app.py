import os
import re
import time
from concurrent.futures import ThreadPoolExecutor
import requests
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

DEMO_MODE = os.getenv("DEMO_MODE", "False").lower() in ("true", "1", "t")
API_URL = os.getenv("API_URL", "http://127.0.0.1:8000/api/v1")

st.set_page_config(page_title="CVScouter", page_icon="🔍", layout="wide")

# Initialize Streamlit session state variables
if "page" not in st.session_state:
    st.session_state.page = "landing"
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "email" not in st.session_state:
    st.session_state.email = ""
if "tokens" not in st.session_state:
    st.session_state.tokens = 0
if "access_token" not in st.session_state:
    st.session_state.access_token = ""
if "current_search" not in st.session_state:
    st.session_state.current_search = None
if "is_searching" not in st.session_state:
    st.session_state.is_searching = False


def get_auth_headers() -> dict:
    """Returns the HTTP Authorization header with the user's JWT token."""
    return {"Authorization": f"Bearer {st.session_state.access_token}"}


def load_latest_history():
    """Loads the most recent search result cache into the session state upon login."""
    if st.session_state.current_search is None:
        try:
            res = requests.get(f"{API_URL}/history", headers=get_auth_headers(), timeout=15)
            if res.status_code == 200 and res.json().get("history"):
                latest = res.json()["history"][0]
                if latest.get("candidates_cache"):
                    st.session_state.current_search = latest["candidates_cache"]
        except requests.RequestException:
            pass


def execute_scout_with_progress(payload: dict):
    """
    Executes the backend scout request in a background thread while rendering
    a real-time progress bar on the Streamlit frontend.
    """
    progress_bar = st.progress(0)
    status_text = st.empty()
    headers = get_auth_headers()

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(
            requests.post,
            f"{API_URL}/scout",
            json=payload,
            headers=headers,
            timeout=120
        )
        pct = 0
        while not future.done():
            if pct < 95:
                pct += 1
            if pct < 25:
                stage_msg = "Extracting core JD requirements & keywords..."
            elif pct < 55:
                stage_msg = "Scanning cross-platform technical footprints (LinkedIn & GitHub)..."
            else:
                stage_msg = "Running 2-stage Dual Comparison LLM evaluation..."

            progress_bar.progress(pct)
            status_text.markdown(f"🤖 **AI Scouting: {stage_msg} ({pct}%)**")
            time.sleep(0.5)

        res = future.result()

    progress_bar.progress(100)
    status_text.markdown("✅ **Evaluation Complete!**")
    time.sleep(0.4)
    return res


def landing_page():
    """Renders the public landing page."""
    st.title("🚀 CVScouter – AI-Driven Candidate Sourcing Agent")
    st.markdown(
        "Automated RAG-based talent sourcing across LinkedIn and technical communities "
        "with a two-stage objective LLM evaluation pipeline."
    )
    st.divider()
    if st.button("👉 Login / Register", type="primary"):
        st.session_state.page = "auth"
        st.rerun()


def auth_page():
    """Renders the authentication (Login / Register) view."""
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("← Back"):
            st.session_state.page = "landing"
            st.rerun()

        st.title("🔒 Account Access")
        tab_login, tab_reg = st.tabs(["Login", "Register"])

        with tab_login:
            with st.form("login_form"):
                email = st.text_input("Email:", key="l_email")
                pwd = st.text_input("Password:", type="password", key="l_pwd")
                if st.form_submit_button("Login", use_container_width=True):
                    res = requests.post(f"{API_URL}/login", json={"email": email, "password": pwd})
                    if res.status_code == 200:
                        data = res.json()
                        st.session_state.logged_in = True
                        st.session_state.email = email
                        st.session_state.tokens = data["tokens_left"]
                        st.session_state.access_token = data["access_token"]
                        st.session_state.page = "app"
                        load_latest_history()
                        st.rerun()
                    else:
                        st.error("Login failed. Please check your credentials.")

        with tab_reg:
            with st.form("reg_form"):
                r_email = st.text_input("Email:", key="r_email")
                r_pwd = st.text_input("Password (min 6 chars):", type="password", key="r_pwd")
                if st.form_submit_button("Register", use_container_width=True):
                    res = requests.post(f"{API_URL}/register", json={"email": r_email, "password": r_pwd})
                    if res.status_code == 200:
                        st.success("Registration successful! Please switch to the Login tab.")
                    else:
                        st.error(res.json().get("detail", "Registration failed."))


def main_app():
    """Renders the primary authenticated application dashboard."""
    c1, c2, c3 = st.columns([1, 7, 2])
    with c1:
        if st.button("🏠 CVScouter"):
            st.session_state.current_search = None
            st.rerun()
    with c3:
        demo_badge = " (🎥 DEMO MODE)" if DEMO_MODE else ""
        st.markdown(f"👤 {st.session_state.email}{demo_badge} | 💰 **{st.session_state.tokens} Tokens**")
    st.divider()

    menu = st.sidebar.radio("Navigation", ["🏠 Search", "📜 History", "👤 Account"])
    if st.sidebar.button("Logout"):
        st.session_state.clear()
        st.rerun()

    if menu == "📜 History":
        st.header("Search History")
        res = requests.get(f"{API_URL}/history", headers=get_auth_headers())
        if res.status_code == 200:
            for h in res.json().get("history", []):
                raw_time = h["created_at"][:16].replace("T", " ")

                if h["search_mode"] == "jd":
                    query_text = h.get("extracted_keywords") or "Processing..."
                    title = f"[JD] {query_text[:30]}..." if len(query_text) > 30 else f"[JD] {query_text}"
                else:
                    query_text = f"{h.get('searching_company', '')} {h.get('searching_position', '')}".strip()
                    title = f"[Comp] {query_text}"

                exp_title = f"{raw_time} : {title}"

                with st.expander(exp_title):
                    st.caption(
                        f"Input Tokens: {h.get('total_input_tokens', 0)} | "
                        f"Output Tokens: {h.get('total_output_tokens', 0)}"
                    )
                    candidates = h.get("candidates_cache", [])
                    if candidates:
                        df = pd.DataFrame(candidates)
                        if DEMO_MODE:
                            df["name"] = [f"Candidate {i + 1}" for i in range(len(df))]
                            df["current_job"] = df["current_job"].apply(
                                lambda x: re.sub(
                                    r"(?i)\s*@\s*.*",
                                    " @ [Company]",
                                    re.sub(r"(?i)\s+at\s+.*", " at [Company]", str(x))
                                )
                            )
                            df["linkedin_url"] = "[Protected in Demo]"
                        else:
                            # Mask locked URLs in the history table until unlocked
                            df["linkedin_url"] = df.apply(
                                lambda row: row["linkedin_url"] if row.get("permission") == 1 else "🔒 Locked",
                                axis=1
                            )

                        display_df = df[["name", "current_job", "linkedin_url", "ai_score", "ai_cv"]]
                        st.dataframe(display_df, use_container_width=True)
                    else:
                        st.write("No candidates found for this session.")
        else:
            st.error("Failed to fetch history. Please log in again.")

    elif menu == "🏠 Search":
        tab1, tab2 = st.tabs(["📄 JD Engine (2 Tokens)", "🏢 Fast Company (1 Token)"])

        with tab1:
            jd_input = st.text_area("Paste Job Description (JD):", height=150)

            if st.button("Start Match", disabled=st.session_state.is_searching, key="btn_jd"):
                if not jd_input.strip():
                    st.warning("Please paste a valid Job Description first.")
                else:
                    st.session_state.is_searching = True
                    res = execute_scout_with_progress({"mode": "jd", "content": jd_input})
                    st.session_state.is_searching = False

                    if res.status_code == 200:
                        data = res.json()
                        st.session_state.tokens = data["tokens_left"]
                        st.session_state.current_search = data["results"]
                        st.rerun()
                    else:
                        st.error(res.json().get("detail", "An error occurred during search."))

        with tab2:
            c1, c2 = st.columns(2)
            comp = c1.text_input("Company:")
            job = c2.text_input("Position (Optional):")

            if st.button("Direct Search", disabled=st.session_state.is_searching, key="btn_comp"):
                if not comp.strip():
                    st.warning("Please enter a target company name.")
                else:
                    st.session_state.is_searching = True
                    res = execute_scout_with_progress({
                        "mode": "keyword",
                        "content": comp,
                        "job_title": job
                    })
                    st.session_state.is_searching = False

                    if res.status_code == 200:
                        data = res.json()
                        st.session_state.tokens = data["tokens_left"]
                        st.session_state.current_search = data["results"]
                        st.rerun()
                    else:
                        st.error(res.json().get("detail", "An error occurred during search."))

        if st.session_state.current_search:
            st.divider()
            st.subheader("🎯 Matched Candidates")

            with st.container(height=600, border=True):
                sorted_search = sorted(
                    st.session_state.current_search,
                    key=lambda x: x.get("ai_score", 0),
                    reverse=True
                )

                for idx, p in enumerate(sorted_search):
                    score = p.get("ai_score", 0)
                    st.markdown(f"#### {idx + 1}. {p['name']} | {p['current_job']} | Score: {score}")
                    with st.expander("✨ Mini CV"):
                        st.write(p["ai_cv"])

                    sid = p.get("search_id", "")
                    btn_key = f"url_{sid}_{idx}"

                    # Check whether this candidate profile is unlocked
                    is_unlocked = (
                        p.get("permission", 0) == 1
                        or bool(p.get("link"))
                        or (btn_key in st.session_state)
                    )

                    if is_unlocked:
                        final_url = (
                            st.session_state.get(btn_key)
                            or p.get("link")
                            or p.get("linkedin_url")
                        )
                        if not final_url or not str(final_url).startswith("http"):
                            final_url = "https://www.linkedin.com"
                        st.link_button("Go to LinkedIn", final_url)
                    else:
                        target_linkedin_url = p.get("linkedin_url", "")
                        if st.button("Unlock Contact (1 Token)", key=f"un_{sid}_{idx}"):
                            u_res = requests.post(
                                f"{API_URL}/unlock",
                                json={"search_id": sid, "linkedin_url": target_linkedin_url},
                                headers=get_auth_headers()
                            )
                            if u_res.status_code == 200:
                                u_data = u_res.json()
                                st.session_state[btn_key] = u_data["url"]
                                st.session_state.tokens = u_data["tokens_left"]
                                p["permission"] = 1
                                p["link"] = u_data["url"]
                                st.rerun()
                            else:
                                st.error(u_res.json().get("detail", "Unlock failed."))

    elif menu == "👤 Account":
        st.header("Account Overview")
        st.write(f"**Registered Email:** {st.session_state.email}")
        st.write(f"**Remaining Balance:** {st.session_state.tokens} Tokens")


if st.session_state.page == "landing":
    landing_page()
elif st.session_state.page == "auth":
    auth_page()
elif st.session_state.page == "app" and st.session_state.logged_in:
    main_app()
else:
    st.session_state.page = "landing"
    st.rerun()