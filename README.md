# 🔍 CVScouter – AI-Driven Candidate Sourcing Agent (PoC)

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-Backend-009688)
![Streamlit](https://img.shields.io/badge/Streamlit-Frontend-FF4B4B)
![Supabase](https://img.shields.io/badge/Supabase-PostgreSQL-3ECF8E)
![OpenAI](https://img.shields.io/badge/OpenAI-GPT--4o--mini-412991)
![Tavily](https://img.shields.io/badge/Tavily-RAG_Search-orange)

---

### 🎥 System Demo


https://github.com/user-attachments/assets/2a0028af-4a7d-4a11-936a-5809c1453acd

<video src="./cv_scouter%20demo.mp4" controls="controls" width="100%"></video>


---

## 📌 1. Overview & Business Impact

An independently developed, all-in-one AI recruitment web application featuring a complete full-stack architecture from the frontend UI to the backend database. Users simply input a Job Description (JD) on the webpage, and the system initiates a **Retrieval-Augmented Generation (RAG)** workflow: it automatically extracts keywords, conducts cross-domain searches for unstructured talent data (scanning not just LinkedIn, but also technical communities like GitHub to capture real technical footprints), and utilizes LLMs to extract and evaluate the most suitable candidates.

This project resolves the core pain points of traditional manual sourcing—which is time-consuming and prone to missing talent due to rigid keyword constraints—achieving a highly automated headhunting workflow.

### 🏆 PoC Execution Metrics & Core Achievements
* **Peak Performance**: For a standard JD averaging 400 words, the end-to-end processing time from initiating the search on the frontend to completing the evaluation and database entry is **50–60 seconds** on average.
* **Ultra-Low Cost**: Benefiting from JD compression technology (`Shrink JD`) and `gpt-4o-mini` optimization, the comprehensive API cost (LLM + Search) for a single sourcing and in-depth evaluation session covering 10+ candidates is strictly controlled to **under $0.2 HKD**.
* **Cross-Domain Sourcing (Hidden Talent)**: During an internal beta test in collaboration with professional headhunters (importing 3 real-world JDs), the system cross-referenced technical footprints from external platforms like GitHub and reverse-mapped them to LinkedIn. It uncovered high-potential talent that traditional LinkedIn-only searches could not reach, automatically building a Talent Pool of **30+ highly qualified candidates**.

---

## ⚙️ 2. System Architecture & Workflow

1. **In-Depth JD Extraction**:
   * Utilizes OpenAI to extract core search strings (Location, Job Title, 2–3 core skills, and negative keywords like `-Sales -Marketing`) from lengthy JDs.
   * Automatically compresses the JD (`shrink_jd`) into under 50 words focusing strictly on hard skills and experience requirements (Must-haves), significantly reducing token consumption for subsequent stages.
2. **Cross-Platform Footprint Tracking & RAG Retrieval**:
   * Breaks through the limitations of traditional recruiting tools that rely solely on LinkedIn resumes by converting extracted keywords into targeted search queries via the **Tavily API**.
   * **Core Differentiator**: Simultaneously scans LinkedIn profiles alongside GitHub open-source contributions, tech blogs, and forums (`github.com`, `dev.to`, `medium.com`) to capture a candidate's actual technical footprint.
   * Performs automated background **Identity Resolution**, reverse-targeting and mapping external technical footprints back to the corresponding LinkedIn Profile to serve as an enriched knowledge base for LLM evaluation.
3. **Multi-Stage AI Evaluation Mechanism**:
   * **Phase 1 – Rapid Pre-screening (Group Relative Scoring)**: Conducts a broad horizontal comparison between the compressed JD and all initially retrieved candidates, deriving a relative score (`relative_score`) based on batch quality and filtering out irrelevant outliers.
   * **Phase 2 – In-Depth Dual Comparison (Individual Absolute Scoring)**: Evaluates each shortlisted candidate independently one-on-one against the JD (`absolute_score`), eliminating context contamination.
   * **Phase 3 – Comprehensive Weight Calculation**: Computes a weighted average (`30% Group Relative + 70% Individual Absolute`) to produce the final objective `ai_score`.
4. **Structured Extraction & Full-Stack Integration**:
   * Enforces clean JSON output (`ai_summary`, bulleted `mini_cv`, and `ai_score`).
   * The **FastAPI** backend persists results to **Supabase (PostgreSQL)** (`candidates_cache`, `jd_search_history`, `company_search_history`, `unlocked_profiles`) and serves them to the **Streamlit** frontend with a token-based contact unlocking mechanism.

---

## 💡 3. Technical Challenges & Solutions

### Challenge 1: Preventing LLM Hallucination & Ensuring Structured Output
* **Pain Point**: Unstructured HTML snippets scraped from the web often contain noise. LLMs can easily get distracted or hallucinate unmentioned candidate skills, and any deviation from valid JSON breaks backend parsing.
* **Solution**:
  1. **Strict Prompt Engineering**: Enforced strict directives in `SYSTEM_PROMPT_REWRITE` (*"Be harsh and realistic"*, *"Remove useless web noise"*), capping `mini_cv` at 100 words in bullet points and explicitly prohibiting the inference of unmentioned skills.
  2. **Enforced Structured Output**: Locked the OpenAI API response schema via `response_format={"type": "json_object"}`.
  3. **Temperature Control**: Lowered `temperature` to `0.1` across extraction and evaluation stages to ensure deterministic, objective grading.

### Challenge 2: Resolving "Scoring Standard Drift" & "Attention Confusion"
* **Pain Point**: Feeding 10+ candidate profiles into a single prompt caused the LLM's attention mechanism to degrade over long contexts and unfairly penalize qualified candidates when compared against a single outlier profile.
* **Solution**: Refactored the pipeline into a **Dual Scoring & Weight Integration Mechanism**:
  1. **First Evaluation (Group Relative Scoring)**: Evaluates the batch horizontally to establish a relative baseline and filter out unqualified outliers.
  2. **Second Evaluation (Individual Absolute Scoring)**: Isolates each shortlisted candidate in an independent loop (`JD vs. Candidate A`, `JD vs. Candidate B`), generating an absolute score completely free from cross-candidate noise.
  3. **Comprehensive Weight Calculation**: Combines both scores via backend weighting to achieve both batch-level perspective and individual objectivity.

---

## 🛠️ 4. Project Setup & Installation

### Prerequisites
* Python 3.10+
* A [Supabase](https://supabase.com/) project
* [OpenAI API Key](https://platform.openai.com/)
* [Tavily API Key](https://tavily.com/)

### 1. Install Dependencies
```bash
pip install -r requirements.txt
