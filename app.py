import streamlit as st
import requests
import time
import pandas as pd
import os
import re

DEMO_MODE = os.getenv("DEMO_MODE", "False").lower() in ("true", "1", "t")

API_URL = "http://127.0.0.1:8000/api/v1"

st.set_page_config(page_title="CVScouter", page_icon="🔍", layout="wide")

# 初始化所有的 Session State
if "page" not in st.session_state: st.session_state.page = "landing"
if "logged_in" not in st.session_state: st.session_state.logged_in = False
if "email" not in st.session_state: st.session_state.email = ""
if "tokens" not in st.session_state: st.session_state.tokens = 0
if "access_token" not in st.session_state: st.session_state.access_token = "" # 儲存 JWT 的金鑰庫
if "current_search" not in st.session_state: st.session_state.current_search = None
if "is_searching" not in st.session_state: st.session_state.is_searching = False

def get_auth_headers():
    """每次呼叫受保護的 API 都必須帶上此 Header 驗證身分"""
    return {"Authorization": f"Bearer {st.session_state.access_token}"}

def load_latest_history():
    if st.session_state.current_search is None:
        res = requests.get(f"{API_URL}/history", headers=get_auth_headers())
        if res.status_code == 200 and res.json().get("history"):
            latest = res.json()["history"][0]
            if latest.get("candidates_cache"):
                st.session_state.current_search = latest["candidates_cache"]

# ==========================================
# Landing Page
# ==========================================
def landing_page():
    st.title("🚀 CVScouter - 務實的極速獵頭工具")
    st.markdown("""
    ### 不廢話，直接給名單。
    這是一個專為效率設計的 AI 招募引擎。你只需要提供 JD 或目標公司，我們立刻穿越雜訊，提取出標準化的 Mini CV 供你評估。
    
    * **⚡ 節省時間**：跳過繁瑣的履歷篩選，直接看 AI 濃縮的核心技能。
    * **🎯 精準打擊**：專注鎖定具有潛力的高價值人才。
    """)
    st.divider()
    if st.button("👉 立即登入 / 註冊開始使用", type="primary"):
        st.session_state.page = "auth"
        st.rerun()

# ==========================================
# 認證介面
# ==========================================
def auth_page():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("← 返回介紹頁"):
            st.session_state.page = "landing"
            st.rerun()
            
        st.title("🔒 系統登入")
        tab_login, tab_reg = st.tabs(["系統登入", "新用戶註冊"])

        with tab_login:
            with st.form("login_form"):
                email = st.text_input("信箱：", key="l_email")
                pwd = st.text_input("密碼：", type="password", key="l_pwd")
                if st.form_submit_button("立即登入", use_container_width=True):
                    res = requests.post(f"{API_URL}/login", json={"email": email, "password": pwd})
                    if res.status_code == 200:
                        data = res.json()
                        st.session_state.logged_in = True
                        st.session_state.email = email
                        st.session_state.tokens = data["tokens_left"]
                        st.session_state.access_token = data["access_token"] # 扣住憑證
                        st.session_state.page = "app"
                        load_latest_history()
                        st.rerun()
                    else:
                        st.error("登入失敗，請檢查帳密。")

        with tab_reg:
            st.info("🎁 註冊即送 5 點試用額度")
            with st.form("reg_form"):
                r_email = st.text_input("設定信箱：", key="r_email")
                r_pwd = st.text_input("設定密碼 (至少 6 位)：", type="password", key="r_pwd")
                if st.form_submit_button("建立帳戶", use_container_width=True):
                    res = requests.post(f"{API_URL}/register", json={"email": r_email, "password": r_pwd})
                    if res.status_code == 200:
                        st.success("註冊成功！請切換至「系統登入」分頁進入。")
                    else:
                        st.error("註冊失敗。")

# ==========================================
# 主應用程式介面
# ==========================================
def simulate_progress_bar():
    progress_bar = st.progress(0)
    status_text = st.empty()
    for i in range(1, 95):
        time.sleep(0.05)
        progress_bar.progress(i)
        status_text.markdown(f"🤖 **小 AI 搜尋中... 請稍後 ({i}%)**")
    return progress_bar, status_text

def main_app():
    c1, c2, c3 = st.columns([1, 7, 2])
    with c1:
        if st.button("🏠 CVScouter", help="點擊返回主工作區"):
            st.session_state.current_search = None
            st.rerun()
    with c3:
<<<<<<< Updated upstream
        st.markdown(f"👤 {st.session_state.email} | 💰 **{st.session_state.tokens} 點**")
=======
        demo_badge = " (🎥 DEMO MODE)" if DEMO_MODE else ""
        st.markdown(f"👤 {st.session_state.email}{demo_badge} | 💰 **{st.session_state.tokens} Tokens**")
>>>>>>> Stashed changes
    st.divider()

    menu = st.sidebar.radio("導覽", ["🏠 開始搜尋", "📜 歷史紀錄 (Excel模式)", "👤 帳戶資訊"])
    if st.sidebar.button("登出"):
        st.session_state.clear()
        st.rerun()

    if menu == "📜 歷史紀錄 (Excel模式)":
        st.header("歷史搜尋分析")
        res = requests.get(f"{API_URL}/history", headers=get_auth_headers())
        if res.status_code == 200:
            for h in res.json().get("history", []):
                raw_time = h['created_at'][:16].replace("T", " ")
                if h['search_mode'] == 'jd':
                    title = h['search_query'][:10] + "..." if len(h['search_query']) > 10 else h['search_query']
                else:
                    title = h['search_query']
                
                exp_title = f"{raw_time} : {title}"
                
                with st.expander(exp_title):
                    st.caption(f"耗時：{h.get('start_time', 'N/A')} 到 {h.get('end_time', 'N/A')} | 花費：{h['cost']} 點")
                    candidates = h.get('candidates_cache', [])
                    if candidates:
                        df = pd.DataFrame(candidates)
<<<<<<< Updated upstream
                        display_df = df[['name', 'current_job', 'linkedin_url', 'ai_cv']].rename(
                            columns={'name': '姓名', 'current_job': '現職', 'linkedin_url': 'LinkedIn 連結', 'ai_cv': 'AI 摘要'}
                        )
=======
                        if DEMO_MODE:
                            df['name'] = [f"Candidate {i+1}" for i in range(len(df))]
                            df['current_job'] = df['current_job'].apply(
                                lambda x: re.sub(r'(?i)\s*@\s*.*', ' @ [Company]', re.sub(r'(?i)\s+at\s+.*', ' at [Company]', str(x)))
                            )
                            df['linkedin_url'] = "[Protected in Demo]"
                            
                        display_df = df[['name', 'current_job', 'linkedin_url', 'ai_score', 'ai_cv']]
>>>>>>> Stashed changes
                        st.dataframe(display_df, use_container_width=True)
                    else:
                        st.write("無名單紀錄。")
        else:
            st.error("無法取得歷史紀錄，憑證可能已過期，請重新登入。")

    elif menu == "🏠 開始搜尋":
        tab1, tab2 = st.tabs(["📄 JD 驅動 (2 點) - 深度語意提取", "🏢 公司快查 (1 點) - 精準鎖定打擊"])
        
        with tab1:
            st.info("💡 **模式說明**：貼上完整的職位描述 (JD)，AI 會自動淬鍊出最核心的 3 個關鍵字進行全網比對。適合只有 JD，不知道從何找起的場景。")
            jd_input = st.text_area("貼上 JD 內容：", height=150)
            
            if st.button("開始 AI 匹配", disabled=st.session_state.is_searching, key="btn_jd"):
                st.session_state.is_searching = True
                p_bar, p_text = simulate_progress_bar()
                
                res = requests.post(f"{API_URL}/scout", json={"mode": "jd", "content": jd_input}, headers=get_auth_headers())
                
                p_bar.progress(100)
                p_text.markdown("✅ **搜尋完成！**")
                time.sleep(0.5)
                
                st.session_state.is_searching = False
                if res.status_code == 200:
                    data = res.json()
                    st.session_state.tokens = data["tokens_left"]
                    st.session_state.current_search = data["results"]
                    st.rerun()
                else:
                    st.error(res.json().get("detail", "API 錯誤，請確認憑證或點數。"))

        with tab2:
            st.info("💡 **模式說明**：直接鎖定特定的競品公司與職稱進行粗暴打撈。成本最低，適合目標已經非常明確的獵頭。")
            c1, c2 = st.columns(2)
            comp = c1.text_input("公司名稱：")
            job = c2.text_input("職位 (選填)：")
            
            if st.button("直接抓取名單", disabled=st.session_state.is_searching, key="btn_comp"):
                st.session_state.is_searching = True
                p_bar, p_text = simulate_progress_bar()
                
                res = requests.post(f"{API_URL}/scout", json={"mode": "keyword", "content": comp, "job_title": job}, headers=get_auth_headers())
                
                p_bar.progress(100)
                p_text.markdown("✅ **搜尋完成！**")
                time.sleep(0.5)
                
                st.session_state.is_searching = False
                if res.status_code == 200:
                    data = res.json()
                    st.session_state.tokens = data["tokens_left"]
                    st.session_state.current_search = data["results"]
                    st.rerun()
                else:
                    st.error(res.json().get("detail", "API 錯誤，請確認憑證或點數。"))

        if st.session_state.current_search:
            st.divider()
            st.subheader("🎯 搜尋結果")
            for idx, p in enumerate(st.session_state.current_search):
                st.markdown(f"#### {idx+1}. {p['name']} | {p['current_job']}")
                with st.expander("✨ Mini CV"): st.write(p['ai_cv'])
                
<<<<<<< Updated upstream
                pid = p.get('profile_id', 'legacy_id')
                link = p.get('link', p.get('linkedin_url', ''))
                
                if link or f"url_{pid}" in st.session_state:
                    final_url = st.session_state.get(f"url_{pid}", link)
                    st.link_button("前往 LinkedIn", final_url)
                else:
                    if st.button("解鎖聯絡資訊 (1 點)", key=f"un_{pid}"):
                        u_res = requests.post(f"{API_URL}/unlock", json={"profile_id": pid}, headers=get_auth_headers())
                        if u_res.status_code == 200:
                            st.session_state[f"url_{pid}"] = u_res.json()["url"]
                            st.session_state.tokens = u_res.json()["tokens_left"]
                            st.rerun()
                        else:
                            st.error("解鎖失敗，點數不足或憑證過期。")

    elif menu == "👤 帳戶資訊":
        st.header("帳戶總覽")
        st.write("極簡後台，不玩花樣。")
=======
                for idx, p in enumerate(sorted_search):
                    score = p.get('ai_score', 0)
                    st.markdown(f"#### {idx+1}. {p['name']} | {p['current_job']} | Score: {score}")
                    with st.expander("✨ Mini CV"): 
                        st.write(p['ai_cv'])
                    
                    sid = p.get('search_id', '')
                    
                   # 確保抓到 AI 搜尋到的真實網址
                    l_url = p.get('link')
                    if not l_url and 'linkedin_url' in p:
                        l_url = p['linkedin_url']

                    btn_key = f"url_{sid}_{idx}"
                    
                    if l_url or btn_key in st.session_state:
                        final_url = st.session_state.get(btn_key, l_url)
                        
                        # 拿掉 DEMO_MODE 的強制替換，直接使用真實網址
                        # 這裡只做防呆，萬一真的沒抓到網址才給首頁，避免 Streamlit 報錯
                        if not final_url or not str(final_url).startswith("http"):
                            final_url = "https://www.linkedin.com"
                            
                        st.link_button("Go to LinkedIn", final_url)
                    else:
                        # 解鎖按鈕也用回原本真實的 hidden_url
                        hidden_url = p.get('linkedin_url', '')
                        if st.button("Unlock Contact (1 Token)", key=f"un_{sid}_{idx}"):
                            u_res = requests.post(f"{API_URL}/unlock", json={"search_id": sid, "linkedin_url": hidden_url}, headers=get_auth_headers())
                            if u_res.status_code == 200:
                                st.session_state[btn_key] = u_res.json()["url"]
                                st.session_state.tokens = u_res.json()["tokens_left"]
                                st.rerun()
                            else:
                                st.error("Unlock failed.")

    elif menu == "👤 Account":
        st.header("Account")
        st.write("Minimal setup.")
>>>>>>> Stashed changes

# ==========================================
# 路由控制總管
# ==========================================
if st.session_state.page == "landing":
    landing_page()
elif st.session_state.page == "auth":
    auth_page()
elif st.session_state.page == "app" and st.session_state.logged_in:
    main_app()
else:
    st.session_state.page = "landing"
    st.rerun()