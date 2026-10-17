import os
<<<<<<< Updated upstream
=======
import json
import re
>>>>>>> Stashed changes
from tavily import TavilyClient
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# ==========================================
# 🎛️ CVScouter 核心控制面板 (隨時可調)
# ==========================================

# [1. API 與模型參數]
LLM_MODEL = "gpt-4o-mini"       # 務實首選：成本極低，處理文字改寫游刃有餘
LLM_TEMP_EXTRACT = 0.1          # 提取關鍵字需要極度精準，溫度壓低
LLM_TEMP_REWRITE = 0.4          # 改寫 CV 給一點點彈性，但不要讓它開始編故事

# [2. 搜尋引擎參數]
TARGET_DOMAIN = "linkedin.com/in/"
DEFAULT_MAX_RESULTS = 15        # 一次抓 15 筆，CP 值最高 (Tavily 算一次額度)

<<<<<<< Updated upstream
# [3. 系統提示詞 (System Prompts - 絕對的規則)]
=======
# 從環境變數讀取 DEMO_MODE，預設為 False
DEMO_MODE = os.getenv("DEMO_MODE", "False").lower() in ("true", "1", "t")

>>>>>>> Stashed changes
SYSTEM_PROMPT_EXTRACT = """
你是一個極度務實的獵頭演算法。請從 JD 中提取關鍵資訊並組合成一個「高強度搜尋字串」。
規則：
1. 包含核心職稱 (必備)。
2. 包含核心技術或產業關鍵字 (如 FMCG, java)。
3. 包含地點約束 (如 香港 或 Taiwan)。
4. 必須加上排除詞以減少雜訊：-業務 -Sales -Marketing -工程師 -Teacher -Philips。
5. 輸出格式：只輸出組合成的搜尋字串，不要任何解釋。
用空格隔開，絕對不要有任何解釋或標點符號。
"""

# 將原本的 ai_job_title 改為 ai_summary，要求生成一句話總結
SYSTEM_PROMPT_REWRITE = """
<<<<<<< Updated upstream
你是一個專業的招募助理。請將用戶提供的網頁摘要使用與原文相同的語言進行改寫，改寫成 100 字以內的「極簡個人簡歷 (Mini CV)」。
規則：
1. 語氣客觀、精煉，條列式呈現核心技能與過去經歷。
2. 剔除所有無意義的網頁雜訊（如 "View profile", "Contact info"）。
3. 如果摘要內容太少，就直接總結現有資訊，不要瞎掰。
=======
You are a cold, rational recruiting assistant. 
Output STRICTLY in JSON format: {"ai_summary": "string", "mini_cv": "string", "ai_score": int}
Rules:
1. ai_summary: Generate EXACTLY ONE concise sentence summarizing the candidate's core expertise, background, and key achievements.
2. mini_cv: Under 100 words, highly objective, bullet points of core skills. Remove useless web noise.
3. ai_score: Integer 0 to 100. Evaluate profile against the provided JD requirements. Be harsh and realistic.
"""

# DEMO 模式下同樣生成一句話總結，並強制公司名稱打碼
SYSTEM_PROMPT_REWRITE_DEMO = """
You are a cold, rational recruiting assistant. 
Output STRICTLY in JSON format: {"ai_summary": "string", "mini_cv": "string", "ai_score": int}
Rules:
1. ai_summary: Generate EXACTLY ONE concise sentence summarizing the candidate's core expertise and background. CRITICAL: You MUST anonymize any real company names (e.g., replace with "[Company]").
2. mini_cv: Under 100 words, highly objective, bullet points of core skills. Remove useless web noise. CRITICAL: You MUST anonymize all person names and specific company names (e.g., use "Candidate", "Company A").
3. ai_score: Integer 0 to 100. Evaluate profile against the provided JD requirements. Be harsh and realistic.
>>>>>>> Stashed changes
"""

# ==========================================
# 啟動 API 客戶端
# ==========================================
tavily = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


# ------------------------------------------
# 🛠️ 1. 工具層：底層對接機器
# ------------------------------------------
def llm_chat_handler(system_prompt: str, user_content: str, temperature: float) -> str:
    """雙通道 AI 呼叫器：System 管規則，User 丟資料"""
    response = openai_client.chat.completions.create(
        model=LLM_MODEL,
        temperature=temperature,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ]
    )
    return response.choices[0].message.content.strip()

def tavily_search_engine(query: str, max_results: int = DEFAULT_MAX_RESULTS) -> list:
    """通用 Tavily 搜尋器，只負責把 JSON 拔回來"""
    full_query = f"site:{TARGET_DOMAIN} {query}"
    search_result = tavily.search(
        query=full_query, 
        search_depth="basic", 
        max_results=max_results
    )
    return search_result.get('results', [])


# ------------------------------------------
# 🧠 2. 邏輯層：資料加工機器
# ------------------------------------------
def extract_keywords_from_jd(jd_text: str) -> str:
    """[模式二專用] 將長篇 JD 脫水成搜尋字串"""
    # 規則傳 System，JD 內容傳 User
    return llm_chat_handler(SYSTEM_PROMPT_EXTRACT, jd_text, temperature=LLM_TEMP_EXTRACT)

def clean_profile_identity(title: str):
    """[通用] 暴力切開 LinkedIn 網頁標題，提取乾淨的姓名與現職"""
    # 範例輸入: "Katie Humphreys - Senior Recruiter at Google - LinkedIn"
    parts = title.split('-')
    name = parts[0].strip()
    
    # 嘗試抓取職稱，如果格式太亂就回傳 N/A
    current_job = parts[1].strip() if len(parts) > 1 else "N/A"
    
    # 清理殘留的 " | LinkedIn" 等字眼
    current_job = current_job.replace(" | LinkedIn", "").replace("...", "").strip()
    return name, current_job

def rewrite_content_to_cv(content: str) -> str:
    """[核心價值] 將 100 字的網頁雜亂摘要，洗成專業的 Mini CV"""
    if not content or len(content) < 10:
        return "無足夠公開資訊可供總結。"
        
    # 規則傳 System，雜亂摘要傳 User
    return llm_chat_handler(SYSTEM_PROMPT_REWRITE, content, temperature=LLM_TEMP_REWRITE)


# ------------------------------------------
# 🎮 3. 總管層：唯一對外接口 (給 main.py 呼叫)
# ------------------------------------------
def perform_scout_task(company: str = "", job_title: str = "", jd_text: str = "") -> list:
    """
    雙軌並行總管：判斷要走「JD 模式」還是「公司快查模式」，
    並強制產出規格化的 4 個欄位 (name, current_job, link, ai_cv)。
    """
    
    # A. 判斷搜尋指令 (A/B 策略路由)
    if jd_text:
        # 走 JD 提取邏輯
        search_query = extract_keywords_from_jd(jd_text)
    elif company and job_title:
        # 走精準公司鎖定邏輯
        search_query = f'"{company}" "{job_title}"'
    else:
        return [{"error": "請提供 JD 或 (公司+職位) 參數"}]

    # B. 執行抓取
    raw_results = tavily_search_engine(search_query)
    
    # C. 執行清洗與 AI 改寫
    final_candidates = []
<<<<<<< Updated upstream
    for res in raw_results:
        # 提取 1.1 名字 與 1.2 現在的工作
        name, current_job = clean_profile_identity(res.get('title', 'Unknown - Unknown'))
        
        # 提取 1.3 連結
        link = res.get('url', '')
        
        # 提取 1.4 AI 改寫 CV (消耗 OpenAI Token 的地方)
        ai_cv = rewrite_content_to_cv(res.get('content', ''))
        
        # 組合標準化字典
=======
    
    for idx, res in enumerate(raw_results):
        # 決定 Prompt 與姓名顯示方式
        if DEMO_MODE:
            name = f"Candidate {idx + 1}"
            current_prompt = SYSTEM_PROMPT_REWRITE_DEMO
        else:
            parts = res.get('title', 'Unknown').split('-')
            name = parts[0].strip()
            current_prompt = SYSTEM_PROMPT_REWRITE
            
        link = res.get('url', '')
        
        eval_content = f"Profile:\n{res.get('content', '')}\n\nRequirements:\n{shrink_jd if jd_text else company + ' ' + job_title}"
        
        raw_cv, i_tok, o_tok = llm_chat_handler(current_prompt, eval_content, LLM_TEMP_REWRITE, True)
        total_in += i_tok
        total_out += o_tok
        
        try:
            ai_eval = json.loads(raw_cv)
        except:
            ai_eval = {"ai_summary": "Error processing summary.", "mini_cv": "Error processing profile.", "ai_score": 0}
            
>>>>>>> Stashed changes
        final_candidates.append({
            "name": name,
            # 這裡直接拿 AI 寫好的一句話總結塞進去 UI 原本顯示職位的位置
            "current_job": ai_eval.get("ai_summary", "Candidate Summary"), 
            "link": link,
            "ai_cv": ai_cv
        })
        
    return final_candidates