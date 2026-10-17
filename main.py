import os
import logging
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from supabase import create_client, Client
from dotenv import load_dotenv
from scout_engine import perform_scout_task

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(
    title="CVScouter API",
    description="AI-Driven Candidate Sourcing Agent Backend",
    version="1.0.0"
)

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

security = HTTPBearer()


# ==========================================
# Request Schemas
# ==========================================
class AuthRequest(BaseModel):
    email: str
    password: str = Field(..., min_length=6)


class ScoutTask(BaseModel):
    mode: str
    content: str
    job_title: str = ""


class UnlockTask(BaseModel):
    search_id: str
    linkedin_url: str


# ==========================================
# Helper & Dependency Functions
# ==========================================
def get_current_user_email(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """Validates Bearer JWT token via Supabase Auth and returns the user's email."""
    token = credentials.credentials
    try:
        user_data = supabase.auth.get_user(token)
        if not user_data or not user_data.user or not user_data.user.email:
            raise ValueError("Invalid user session.")
        return user_data.user.email
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired authentication token.")


def get_user_tokens(email: str) -> int:
    """Retrieves the remaining token balance for a given user, initializing to 5 if new."""
    res = supabase.table("users").select("tokens_left").eq("email", email).execute()
    if not res.data:
        supabase.table("users").upsert({"email": email, "tokens_left": 5}, on_conflict="email").execute()
        return 5
    return res.data[0]["tokens_left"]


# ==========================================
# API Endpoints
# ==========================================
@app.post("/api/v1/register")
def register_user(req: AuthRequest):
    """Registers a new user account and allocates initial free tokens."""
    try:
        supabase.auth.sign_up({"email": req.email, "password": req.password})
        supabase.table("users").upsert({"email": req.email, "tokens_left": 5}, on_conflict="email").execute()
        return {"success": True, "message": "Registration successful."}
    except Exception as exc:
        logger.error("User registration failed: %s", exc)
        raise HTTPException(status_code=400, detail="Registration failed. Please verify your email or try again.")


@app.post("/api/v1/login")
def login_user(req: AuthRequest):
    """Authenticates a user and returns their access token and current token balance."""
    try:
        auth_res = supabase.auth.sign_in_with_password({"email": req.email, "password": req.password})
        tokens = get_user_tokens(req.email)
        return {
            "success": True,
            "tokens_left": tokens,
            "access_token": auth_res.session.access_token
        }
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid email or password.")


@app.get("/api/v1/history")
def get_history(user_email: str = Depends(get_current_user_email)):
    """Fetches and merges both JD search history and Company search history for the current user."""
    jd_res = (
        supabase.table("jd_search_history")
        .select("*, candidates_cache(*)")
        .eq("user_email", user_email)
        .order("created_at", desc=True)
        .execute()
    )
    comp_res = (
        supabase.table("company_search_history")
        .select("*, candidates_cache(*)")
        .eq("user_email", user_email)
        .order("created_at", desc=True)
        .execute()
    )

    combined = []
    for item in (jd_res.data or []):
        item["search_mode"] = "jd"
        combined.append(item)
    for item in (comp_res.data or []):
        item["search_mode"] = "keyword"
        combined.append(item)

    combined.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return {"success": True, "history": combined}


@app.post("/api/v1/scout")
def run_scout(task: ScoutTask, user_email: str = Depends(get_current_user_email)):
    """Deducts tokens, triggers the AI sourcing engine, and stores structured results in Supabase."""
    if not task.content or not task.content.strip():
        raise HTTPException(status_code=400, detail="Search content cannot be empty.")

    cost = 2 if task.mode == "jd" else 1
    current_tokens = get_user_tokens(user_email)

    if current_tokens < cost:
        raise HTTPException(status_code=402, detail="Insufficient tokens for this search.")

    new_balance = current_tokens - cost
    supabase.table("users").update({"tokens_left": new_balance}).eq("email", user_email).execute()

    try:
        # 1. Create pending search history record
        if task.mode == "jd":
            h_res = supabase.table("jd_search_history").insert({
                "user_email": user_email,
                "raw_jd": task.content,
                "status": "processing"
            }).execute()
        else:
            h_res = supabase.table("company_search_history").insert({
                "user_email": user_email,
                "searching_company": task.content,
                "searching_position": task.job_title,
                "status": "processing"
            }).execute()

        search_id = h_res.data[0]["search_id"]

        # 2. Execute AI Sourcing & Dual Evaluation Engine
        if task.mode == "jd":
            engine_data = perform_scout_task(jd_text=task.content)
        else:
            engine_data = perform_scout_task(company=task.content, job_title=task.job_title)

        if "error" in engine_data:
            raise ValueError(engine_data["error"])

        # 3. Update search history record with completion metrics
        completed_at = datetime.now(timezone.utc).isoformat()
        if task.mode == "jd":
            supabase.table("jd_search_history").update({
                "shrink_jd": engine_data["shrink_jd"],
                "extracted_keywords": engine_data["extracted_keywords"],
                "tavily_raw_data": engine_data["tavily_raw_data"],
                "total_input_tokens": engine_data["total_input_tokens"],
                "total_output_tokens": engine_data["total_output_tokens"],
                "status": "completed",
                "completed_at": completed_at
            }).eq("search_id", search_id).execute()
        else:
            supabase.table("company_search_history").update({
                "tavily_raw_data": engine_data["tavily_raw_data"],
                "total_input_tokens": engine_data["total_input_tokens"],
                "total_output_tokens": engine_data["total_output_tokens"],
                "status": "completed",
                "completed_at": completed_at
            }).eq("search_id", search_id).execute()

        # 4. Cache candidates and check unlock permissions
        unlocked_res = (
            supabase.table("unlocked_profiles")
            .select("linkedin_url")
            .eq("user_email", user_email)
            .execute()
        )
        unlocked_urls = {row["linkedin_url"] for row in (unlocked_res.data or [])}

        safe_results = []
        for p in engine_data["candidates"]:
            target_url = p["link"]
            if not target_url:
                continue

            perm = 1 if target_url in unlocked_urls else 0

            supabase.table("candidates_cache").upsert({
                "search_id": search_id,
                "linkedin_url": target_url,
                "name": p["name"],
                "current_job": p["current_job"],
                "ai_cv": p["ai_cv"],
                "ai_score": p.get("ai_score", 0),
                "permission": perm
            }).execute()

            safe_results.append({
                "search_id": search_id,
                "name": p["name"],
                "current_job": p["current_job"],
                "ai_cv": p["ai_cv"],
                "ai_score": p.get("ai_score", 0),
                "permission": perm,
                "link": target_url if perm == 1 else "",
                "linkedin_url": target_url
            })

        return {
            "success": True,
            "tokens_left": new_balance,
            "results": safe_results,
            "search_id": search_id
        }

    except Exception as exc:
        # Refund tokens if the search pipeline fails
        logger.error("Scout task failed for user %s: %s", user_email, exc)
        supabase.table("users").update({"tokens_left": current_tokens}).eq("email", user_email).execute()
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/v1/unlock")
def unlock_profile(task: UnlockTask, user_email: str = Depends(get_current_user_email)):
    """Unlocks a candidate's LinkedIn URL by deducting 1 token if not previously unlocked."""
    target_url = task.linkedin_url

    check_res = (
        supabase.table("unlocked_profiles")
        .select("*")
        .eq("user_email", user_email)
        .eq("linkedin_url", target_url)
        .execute()
    )

    if check_res.data:
        supabase.table("candidates_cache").update({"permission": 1}).eq(
            "search_id", task.search_id
        ).eq("linkedin_url", target_url).execute()
        return {"success": True, "url": target_url, "tokens_left": get_user_tokens(user_email)}

    current_tokens = get_user_tokens(user_email)
    if current_tokens < 1:
        raise HTTPException(status_code=402, detail="Insufficient tokens to unlock contact.")

    new_balance = current_tokens - 1
    supabase.table("users").update({"tokens_left": new_balance}).eq("email", user_email).execute()
    supabase.table("unlocked_profiles").insert({"user_email": user_email, "linkedin_url": target_url}).execute()
    supabase.table("candidates_cache").update({"permission": 1}).eq(
        "search_id", task.search_id
    ).eq("linkedin_url", target_url).execute()

    return {"success": True, "url": target_url, "tokens_left": new_balance}