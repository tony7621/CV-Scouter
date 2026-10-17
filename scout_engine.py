import os
import json
import logging
from typing import Dict, List, Any
from tavily import TavilyClient
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# ==========================================
# Core Configuration & Hyperparameters
# ==========================================
LLM_MODEL = "gpt-4o-mini"
LLM_TEMP_EXTRACT = 0.1
LLM_TEMP_EVALUATE = 0.1
LLM_TEMP_REWRITE = 0.1

LINKEDIN_DOMAIN = "linkedin.com/in/"
TECH_FOOTPRINT_DOMAINS = ["github.com", "dev.to", "medium.com"]

DEFAULT_MAX_RESULTS = 12
FOOTPRINT_MAX_RESULTS = 3

# Scoring Weights for Phase 3 (Comprehensive Weight Calculation)
WEIGHT_GROUP_RELATIVE = 0.30
WEIGHT_INDIVIDUAL_ABSOLUTE = 0.70
MIN_PRE_SCREEN_SCORE = 35

# Read DEMO_MODE from environment variables (defaults to False)
DEMO_MODE = os.getenv("DEMO_MODE", "False").lower() in ("true", "1", "t")

# ==========================================
# System Prompts
# ==========================================
SYSTEM_PROMPT_EXTRACT = """
You are a highly pragmatic headhunting algorithm.
Output STRICTLY in JSON format: {"search_string": "string", "shrink_jd": "string"}
Rules:
1. search_string: Must include Location, Job Title, and 2-3 core skills. Add negative keywords (e.g. -Sales -Marketing).
2. shrink_jd: Compress the JD into under 50 words. Focus ONLY on hard requirements (Must-haves) and core tech stack. No fluff.
"""

SYSTEM_PROMPT_GROUP_EVAL = """
You are an objective technical recruiting lead conducting Phase 1 Rapid Pre-screening and Group Relative Scoring.
Compare all candidate snippets horizontally against the provided JD requirements.
Output STRICTLY in JSON format:
{
  "evaluations": [
    {
      "candidate_id": int,
      "relative_score": int,
      "is_shortlisted": bool
    }
  ]
}
Rules:
1. relative_score: Integer 0 to 100 based on how each candidate ranks relative to the overall quality of this specific batch.
2. is_shortlisted: Set to false ONLY if the candidate is completely irrelevant or has severe, unbridgeable experience gaps.
"""

SYSTEM_PROMPT_REWRITE = """
You are a cold, rational recruiting assistant conducting an independent 1-on-1 candidate evaluation.
Output STRICTLY in JSON format: {"ai_summary": "string", "mini_cv": "string", "ai_score": int}
Rules:
1. ai_summary: Generate EXACTLY ONE concise sentence summarizing the candidate's core expertise, background, and key achievements.
2. mini_cv: Under 100 words, highly objective, bullet points of core skills. Remove useless web noise. If a specific skill is not explicitly mentioned in the resume, you are strictly prohibited from inferring or fabricating it.
3. ai_score: Integer 0 to 100. Evaluate this individual profile strictly against the provided JD requirements. Be harsh and realistic.
"""

SYSTEM_PROMPT_REWRITE_DEMO = """
You are a cold, rational recruiting assistant conducting an independent 1-on-1 candidate evaluation.
Output STRICTLY in JSON format: {"ai_summary": "string", "mini_cv": "string", "ai_score": int}
Rules:
1. ai_summary: Generate EXACTLY ONE concise sentence summarizing the candidate's core expertise and background. CRITICAL: You MUST anonymize any real company names (e.g., replace with "[Company]").
2. mini_cv: Under 100 words, highly objective, bullet points of core skills. Remove useless web noise. If a specific skill is not explicitly mentioned in the resume, you are strictly prohibited from inferring or fabricating it. CRITICAL: You MUST anonymize all person names and specific company names (e.g., use "Candidate", "Company A").
3. ai_score: Integer 0 to 100. Evaluate this individual profile strictly against the provided JD requirements. Be harsh and realistic.
"""

tavily = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def llm_chat_handler(
    system_prompt: str,
    user_content: str,
    temperature: float,
    json_mode: bool = False
) -> tuple[str, int, int]:
    """Executes an OpenAI Chat Completion call and tracks token usage."""
    kwargs: Dict[str, Any] = {
        "model": LLM_MODEL,
        "temperature": temperature,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ]
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    response = openai_client.chat.completions.create(**kwargs)
    content = response.choices[0].message.content.strip()
    in_tokens = response.usage.prompt_tokens if response.usage else 0
    out_tokens = response.usage.completion_tokens if response.usage else 0
    return content, in_tokens, out_tokens


def extract_candidate_name(title: str) -> str:
    """Extracts a clean candidate name from a search result title."""
    if not title:
        return "Unknown"
    parts = title.split("-")[0].split("|")[0].strip()
    return parts if parts else "Unknown"


def retrieve_cross_platform_candidates(search_query: str) -> List[Dict[str, Any]]:
    """
    Executes cross-domain RAG retrieval:
    1. Searches LinkedIn directly for matching candidate profiles.
    2. Scans technical communities (GitHub, Dev.to, Medium) for real technical footprints,
       then performs Identity Resolution to reverse-map footprints back to LinkedIn profiles.
    """
    merged_results: Dict[str, Dict[str, Any]] = {}

    # Step 1: Primary LinkedIn Profile Retrieval
    linkedin_query = f"site:{LINKEDIN_DOMAIN} {search_query}"
    try:
        li_response = tavily.search(
            query=linkedin_query,
            search_depth="basic",
            max_results=DEFAULT_MAX_RESULTS
        )
        for item in li_response.get("results", []):
            url = item.get("url", "")
            if LINKEDIN_DOMAIN in url and url not in merged_results:
                merged_results[url] = {
                    "title": item.get("title", "Unknown"),
                    "url": url,
                    "content": item.get("content", ""),
                    "source": "linkedin"
                }
    except Exception as exc:
        logger.warning("Primary LinkedIn search encountered an error: %s", exc)

    # Step 2: Cross-Platform Technical Footprint Discovery & Identity Resolution
    domain_filter = " OR ".join([f"site:{d}" for d in TECH_FOOTPRINT_DOMAINS])
    footprint_query = f"({domain_filter}) {search_query}"
    try:
        fp_response = tavily.search(
            query=footprint_query,
            search_depth="basic",
            max_results=FOOTPRINT_MAX_RESULTS
        )
        for fp_item in fp_response.get("results", []):
            candidate_handle = extract_candidate_name(fp_item.get("title", ""))
            fp_snippet = fp_item.get("content", "")
            if not candidate_handle or candidate_handle.lower() in ("unknown", "github"):
                continue

            # Identity Resolution: Reverse-map technical footprint to a LinkedIn Profile
            resolution_query = f'site:{LINKEDIN_DOMAIN} "{candidate_handle}" {search_query}'
            res_lookup = tavily.search(
                query=resolution_query,
                search_depth="basic",
                max_results=1
            )
            resolved_hits = res_lookup.get("results", [])
            if resolved_hits:
                li_hit = resolved_hits[0]
                li_url = li_hit.get("url", "")
                if LINKEDIN_DOMAIN in li_url:
                    if li_url in merged_results:
                        # Enrich existing LinkedIn profile with external technical footprint
                        merged_results[li_url]["content"] += f"\n[External Tech Footprint]: {fp_snippet}"
                    else:
                        merged_results[li_url] = {
                            "title": li_hit.get("title", candidate_handle),
                            "url": li_url,
                            "content": f"{li_hit.get('content', '')}\n[External Tech Footprint]: {fp_snippet}",
                            "source": "cross_domain_resolved"
                        }
    except Exception as exc:
        logger.warning("Cross-domain footprint resolution skipped due to error: %s", exc)

    return list(merged_results.values())[:DEFAULT_MAX_RESULTS]


def perform_scout_task(company: str = "", job_title: str = "", jd_text: str = "") -> Dict[str, Any]:
    """
    Main pipeline orchestrating JD extraction, cross-domain retrieval,
    and the 2-stage Dual Comparison evaluation mechanism.
    """
    total_in = 0
    total_out = 0
    extracted_keywords = ""
    shrink_jd = ""

    # ==========================================
    # Step 1: In-Depth JD Extraction & Compression
    # ==========================================
    if jd_text and jd_text.strip():
        try:
            raw_res, i_tok, o_tok = llm_chat_handler(
                SYSTEM_PROMPT_EXTRACT, jd_text, LLM_TEMP_EXTRACT, json_mode=True
            )
            total_in += i_tok
            total_out += o_tok
            parsed = json.loads(raw_res)
            extracted_keywords = parsed.get("search_string", "").strip()
            shrink_jd = parsed.get("shrink_jd", "").strip()
        except (json.JSONDecodeError, Exception) as exc:
            logger.error("JD Extraction failed: %s", exc)
            return {"error": "AI Extraction Failed."}

        if not extracted_keywords:
            return {"error": "Failed to extract valid search keywords from JD."}
        search_query = extracted_keywords
        target_requirements = shrink_jd

    elif company and company.strip():
        clean_company = company.strip()
        clean_title = job_title.strip() if job_title else ""
        search_query = f'"{clean_company}" "{clean_title}"'.strip() if clean_title else f'"{clean_company}"'
        target_requirements = f"{clean_company} {clean_title}".strip()
    else:
        return {"error": "Missing search parameters. Please provide a JD or Company name."}

    # ==========================================
    # Step 2: Cross-Platform RAG Retrieval
    # ==========================================
    raw_results = retrieve_cross_platform_candidates(search_query)
    if not raw_results:
        return {
            "candidates": [],
            "tavily_raw_data": [],
            "total_input_tokens": total_in,
            "total_output_tokens": total_out,
            "extracted_keywords": extracted_keywords,
            "shrink_jd": shrink_jd
        }

    # ==========================================
    # Step 3: Multi-Stage AI Evaluation Mechanism
    # Phase 1 - Rapid Pre-screening & Group Relative Scoring
    # ==========================================
    batch_overview = []
    for idx, res in enumerate(raw_results):
        batch_overview.append({
            "candidate_id": idx,
            "title": res.get("title", ""),
            "snippet": res.get("content", "")[:400]
        })

    group_eval_input = (
        f"Job Requirements:\n{target_requirements}\n\n"
        f"Candidates Batch:\n{json.dumps(batch_overview, ensure_ascii=False)}"
    )

    relative_scores_map: Dict[int, int] = {}
    shortlisted_indices: List[int] = []

    try:
        group_raw, i_tok, o_tok = llm_chat_handler(
            SYSTEM_PROMPT_GROUP_EVAL, group_eval_input, LLM_TEMP_EVALUATE, json_mode=True
        )
        total_in += i_tok
        total_out += o_tok
        group_parsed = json.loads(group_raw)

        for item in group_parsed.get("evaluations", []):
            cid = item.get("candidate_id")
            rel_score = int(item.get("relative_score", 50))
            is_shortlisted = bool(item.get("is_shortlisted", True))

            if isinstance(cid, int) and 0 <= cid < len(raw_results):
                relative_scores_map[cid] = max(0, min(100, rel_score))
                if is_shortlisted and rel_score >= MIN_PRE_SCREEN_SCORE:
                    shortlisted_indices.append(cid)
    except (json.JSONDecodeError, Exception) as exc:
        logger.warning("Phase 1 Group Evaluation fallback triggered: %s", exc)

    # Fallback: if Phase 1 filtered out everyone or failed, evaluate all retrieved candidates
    if not shortlisted_indices:
        shortlisted_indices = list(range(len(raw_results)))
        for idx in shortlisted_indices:
            relative_scores_map.setdefault(idx, 60)

    # ==========================================
    # Phase 2 - In-Depth 1-on-1 Individual Absolute Scoring
    # & Phase 3 - Comprehensive Weight Calculation
    # ==========================================
    final_candidates = []
    current_rewrite_prompt = SYSTEM_PROMPT_REWRITE_DEMO if DEMO_MODE else SYSTEM_PROMPT_REWRITE

    for display_idx, cand_idx in enumerate(shortlisted_indices):
        res = raw_results[cand_idx]
        name = f"Candidate {display_idx + 1}" if DEMO_MODE else extract_candidate_name(res.get("title", "Unknown"))
        link = res.get("url", "")

        # Isolated 1-on-1 prompt context to prevent attention confusion and scoring drift
        eval_content = (
            f"Candidate Profile & Technical Footprint:\n{res.get('content', '')}\n\n"
            f"Target Requirements:\n{target_requirements}"
        )

        try:
            raw_cv, i_tok, o_tok = llm_chat_handler(
                current_rewrite_prompt, eval_content, LLM_TEMP_REWRITE, json_mode=True
            )
            total_in += i_tok
            total_out += o_tok
            ai_eval = json.loads(raw_cv)
        except (json.JSONDecodeError, Exception) as exc:
            logger.error("Phase 2 Individual Evaluation failed for candidate %d: %s", cand_idx, exc)
            ai_eval = {
                "ai_summary": "Error processing candidate summary.",
                "mini_cv": "Error processing candidate profile.",
                "ai_score": 0
            }

        # Phase 3: Weighted Average of Group Relative Score & Individual Absolute Score
        absolute_score = int(ai_eval.get("ai_score", 0))
        relative_score = relative_scores_map.get(cand_idx, absolute_score)
        weighted_score = round(
            (relative_score * WEIGHT_GROUP_RELATIVE) +
            (absolute_score * WEIGHT_INDIVIDUAL_ABSOLUTE)
        )
        final_score = max(0, min(100, weighted_score))

        final_candidates.append({
            "name": name,
            "current_job": ai_eval.get("ai_summary", "Candidate Summary"),
            "link": link,
            "ai_cv": ai_eval.get("mini_cv", ""),
            "ai_score": final_score
        })

    # Sort candidates by final weighted score descending
    final_candidates.sort(key=lambda x: x.get("ai_score", 0), reverse=True)

    return {
        "candidates": final_candidates,
        "tavily_raw_data": raw_results,
        "total_input_tokens": total_in,
        "total_output_tokens": total_out,
        "extracted_keywords": extracted_keywords,
        "shrink_jd": shrink_jd
    }