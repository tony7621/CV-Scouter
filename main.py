import os
from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from supabase import create_client, Client
from dotenv import load_dotenv
from scout_engine import perform_scout_task
from datetime import datetime, timezone

load_dotenv()
app = FastAPI()

# 初始化 Supabase
supabase: Client = create_client(os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY"))

# ==========================================
# 資料模型 (防偽造：移除業務操作中的 email)
# ==========================================
class AuthRequest(BaseModel):
    email: str
    password: str

class ScoutTask(BaseModel):
    mode: str
    content: str
    job_title: str = ""

class UnlockTask(BaseModel):
    profile_id: str

# ==========================================
# 資安與輔助函數
# ==========================================
security = HTTPBearer()

def get_current_user_email(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """攔截 API 請求，強制驗證 JWT Token，提取真實 Email"""
    token = credentials.credentials
    try:
        # 將 Token 丟給 Supabase 驗證，偽造或過期會直接報錯
        user_data = supabase.auth.get_user(token)
        if not user_data or not user_data.user:
            raise ValueError("無效的使用者")
        return user_data.user.email
    except Exception:
        raise HTTPException(status_code=401, detail="憑證無效或已過期，請重新登入。")

def get_user_tokens(email: str) -> int:
    res = supabase.table("users").select("tokens_left").eq("email", email).execute()
    if not res.data:
        supabase.table("users").upsert({"email": email, "tokens_left": 5}, on_conflict="email").execute()
        return 5
    return res.data[0]["tokens_left"]

# ==========================================
# API 路由
# ==========================================

@app.post("/api/v1/register")
async def register_user(req: AuthRequest):
    if len(req.password) < 6:
        raise HTTPException(status_code=400, detail="密碼長度至少需 6 位數")
    
    try:
        supabase.auth.sign_up({"email": req.email, "password": req.password})
        supabase.table("users").upsert({"email": req.email, "tokens_left": 5}, on_conflict="email").execute()
        return {"success": True, "message": "註冊成功！已贈送 5 點試用額度。"}
    except Exception as e:
        err_msg = str(e).lower()
        if "429" in err_msg or "rate limit" in err_msg:
            raise HTTPException(status_code=429, detail="註冊過於頻繁，請稍後再試。")
        if "already registered" in err_msg:
            raise HTTPException(status_code=400, detail="該 Email 已被註冊，請直接登入。")
        raise HTTPException(status_code=400, detail=f"註冊失敗: {str(e)}")

@app.post("/api/v1/login")
async def login_user(req: AuthRequest):
    try:
        auth_res = supabase.auth.sign_in_with_password({"email": req.email, "password": req.password})
        tokens = get_user_tokens(req.email)
        # 登入時發放最高權限 JWT 憑證給前端
        access_token = auth_res.session.access_token 
        return {"success": True, "message": "登入成功！", "tokens_left": tokens, "access_token": access_token}
    except Exception:
        raise HTTPException(status_code=401, detail="信箱或密碼錯誤，請重新檢查。")

@app.get("/api/v1/user")
async def get_user_info(user_email: str = Depends(get_current_user_email)):
    tokens = get_user_tokens(user_email)
    return {"email": user_email, "tokens_left": tokens}

@app.get("/api/v1/history")
async def get_history(user_email: str = Depends(get_current_user_email)):
    """取得歷史紀錄與對應的候選人名單，用於展現 Excel 格式"""
    res = supabase.table("search_history").select("*, candidates_cache(*)").eq("user_email", user_email).order("created_at", desc=True).execute()
    return {"success": True, "history": res.data}

@app.post("/api/v1/scout")
async def run_scout(task: ScoutTask, user_email: str = Depends(get_current_user_email)):
    cost = 2 if task.mode == "jd" else 1
    current_tokens = get_user_tokens(user_email)

    if current_tokens < cost:
        raise HTTPException(status_code=402, detail="Token 餘額不足。")

    # 先扣款，鎖定點數
    new_balance = current_tokens - cost
    supabase.table("users").update({"tokens_left": new_balance}).eq("email", user_email).execute()

    start_time = datetime.now(timezone.utc).isoformat()
    try:
        query_text = task.content if task.mode == "jd" else f"{task.content} {task.job_title}".strip()
        results = perform_scout_task(jd_text=task.content) if task.mode == "jd" else perform_scout_task(company=task.content, job_title=task.job_title)
        end_time = datetime.now(timezone.utc).isoformat()
        
        history_res = supabase.table("search_history").insert({
            "user_email": user_email, "search_mode": task.mode, "search_query": query_text, 
            "cost": cost, "start_time": start_time, "end_time": end_time
        }).execute()
        history_id = history_res.data[0]["id"]

        # 取得該用戶「所有已解鎖的 URL 集合」 (防重複扣款核心)
        unlocked_res = supabase.table("unlocked_profiles").select("linkedin_url").eq("user_email", user_email).execute()
        unlocked_urls = {row["linkedin_url"] for row in unlocked_res.data}

        safe_results = []
        for p in results:
            if "error" in p: continue
            
            # 判斷權限：如果抓到的 URL 以前買過，直接給 1 (免費開通)
            target_url = p["link"]
            perm = 1 if target_url in unlocked_urls else 0

            cache_res = supabase.table("candidates_cache").insert({
                "history_id": history_id, "name": p["name"], "current_job": p["current_job"],
                "ai_cv": p["ai_cv"], "linkedin_url": target_url, "permission": perm
            }).execute()
            
            safe_results.append({
<<<<<<< Updated upstream
                "profile_id": cache_res.data[0]["profile_id"], "name": p["name"],
                "current_job": p["current_job"], "ai_cv": p["ai_cv"],
                "link": target_url if perm == 1 else "" # 沒買過就清空 URL
=======
                "search_id": search_id, "name": p["name"], "current_job": p["current_job"], 
                "ai_cv": p["ai_cv"], "ai_score": p.get("ai_score", 0),
                "link": target_url if perm == 1 else "",
                "linkedin_url": target_url 
>>>>>>> Stashed changes
            })
        return {"success": True, "tokens_left": new_balance, "results": safe_results, "history_id": history_id}
    except Exception as e:
        # 發生錯誤退款止損
        supabase.table("users").update({"tokens_left": current_tokens}).eq("email", user_email).execute()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/unlock")
async def unlock_profile(task: UnlockTask, user_email: str = Depends(get_current_user_email)):
    cache_res = supabase.table("candidates_cache").select("linkedin_url").eq("profile_id", task.profile_id).execute()
    if not cache_res.data:
        raise HTTPException(status_code=404, detail="找不到該筆名單。")
    
    target_url = cache_res.data[0]["linkedin_url"]
    check_res = supabase.table("unlocked_profiles").select("*").eq("user_email", user_email).eq("linkedin_url", target_url).execute()
    
    if check_res.data:
        # 以前買過，補上 permission 
        supabase.table("candidates_cache").update({"permission": 1}).eq("profile_id", task.profile_id).execute()
        return {"success": True, "url": target_url, "tokens_left": get_user_tokens(user_email)}

    # 首次解鎖扣款
    current_tokens = get_user_tokens(user_email)
    if current_tokens < 1:
        raise HTTPException(status_code=402, detail="Token 不足。")

    new_balance = current_tokens - 1
    supabase.table("users").update({"tokens_left": new_balance}).eq("email", user_email).execute()
    supabase.table("unlocked_profiles").insert({"user_email": user_email, "linkedin_url": target_url}).execute()
    supabase.table("candidates_cache").update({"permission": 1}).eq("profile_id", task.profile_id).execute()
    
    return {"success": True, "url": target_url, "tokens_left": new_balance}