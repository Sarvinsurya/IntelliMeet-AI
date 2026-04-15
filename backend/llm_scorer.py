"""
backend/llm_scorer.py
=====================
Score resume against job description using an LLM.
Uses Groq Cloud (free tier, fast). Set GROQ_API_KEY in environment.
Falls back to keyword extraction when no key or API fails.
"""
import json
import os
import re
import logging

logger = logging.getLogger(__name__)

# Truncate resume/job text to stay within model context
MAX_RESUME_CHARS = 6000
MAX_JD_CHARS = 2000

# Groq: free tier, OpenAI-compatible API. Get key at https://console.groq.com
GROQ_BASE_URL = "https://api.groq.com/openai/v1"
# 70B follows instructions better for role-fit scoring; 8b is faster but often ignores "fit only"
GROQ_MODEL = "llama-3.3-70b-versatile"


def _extract_keywords_from_jd(job_description: str, max_keywords: int = 15) -> list[str]:
    """Simple heuristic: take significant words (skip common stop words)."""
    if not job_description or not job_description.strip():
        return []
    stop = {
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with",
        "by", "from", "as", "is", "was", "are", "were", "been", "be", "have", "has", "had",
        "do", "does", "did", "will", "would", "could", "should", "may", "might", "must",
        "this", "that", "these", "those", "it", "its", "we", "our", "you", "your",
        "years", "year", "experience", "required", "preferred", "ability", "skills",
    }
    words = re.findall(r"\b[a-zA-Z]{3,}\b", job_description.lower())
    seen = set()
    out = []
    for w in words:
        if w not in stop and w not in seen:
            seen.add(w)
            out.append(w)
            if len(out) >= max_keywords:
                break
    return out


def score_resume_with_llm(
    job_description: str,
    resume_text: str,
    threshold: float = 50,
    api_key: str = None,
) -> dict:
    """
    Use Groq API to score how well the resume matches the job description.
    Returns: {"score": 0-100, "above_threshold": bool, "reasoning": str, "source": "llm"|"keyword_fallback"}
    """
    api_key = api_key or os.environ.get("GROQ_API_KEY")
    jd = (job_description or "").strip()[:MAX_JD_CHARS]
    resume = (resume_text or "").strip()[:MAX_RESUME_CHARS]

    if not resume:
        return {
            "score": 0,
            "above_threshold": False,
            "reasoning": "Resume text could not be extracted.",
            "source": "none",
        }

    if api_key and jd:
        try:
            import openai
            client = openai.OpenAI(
                base_url=GROQ_BASE_URL,
                api_key=api_key,
            )
            system_msg = """You are a strict technical recruiter who evaluates if candidates are QUALIFIED for a specific role.

CORE PRINCIPLE: Only candidates whose PRIMARY CAREER FOCUS matches the role domain should score above threshold.

EVALUATION PROCESS:

STEP 1 - IDENTIFY ROLE DOMAIN
Extract the PRIMARY domain this role needs from the job description:
- Is it Data Science/ML/AI?
- Is it Web Development (Frontend/Backend/Full-stack)?
- Is it DevOps/Cloud/Infrastructure?
- Is it Mobile Development?
- Is it something else?

STEP 2 - IDENTIFY CANDIDATE'S PRIMARY DOMAIN
Look at their ACTUAL WORK (not interests/certifications):
- What are their projects ACTUALLY about?
- What did they build in previous jobs/internships?
- What is their degree focused on?

STEP 3 - DOMAIN MATCH DECISION
Ask: "Is this candidate's PRIMARY domain the SAME as the role's domain?"

IF YES → Can score 70-98 (depending on depth/quality)
IF NO → MUST score below 55 (even if they know some overlapping tools)

CRITICAL DISTINCTION EXAMPLES:

Example 1 - Data Science Role:
✅ Score 70+: Resume shows ML projects, data analysis work, statistics degree
❌ Score <55: Resume shows web apps (React/Node), even if they know Python/SQL
→ Why? Python/SQL are TOOLS used in many fields. Web dev ≠ Data Science.

Example 2 - Backend Developer Role:
✅ Score 70+: Resume shows API development, microservices, database design
❌ Score <55: Resume shows ML models, data pipelines, even if they know Node.js
→ Why? Backend dev ≠ Data Engineering. Different career paths.

Example 3 - Frontend Developer Role:
✅ Score 70+: Resume shows React/Vue apps, UI/UX work, responsive design
❌ Score <55: Resume shows data dashboards using React, but primary focus is data analysis
→ Why? Using React for dashboards ≠ Frontend developer career.

SCORING BANDS:

85-98: EXCEPTIONAL MATCH
- Primary domain = role domain
- Multiple substantial projects in this exact domain
- Direct work experience in this domain
- Education aligned with this domain

70-84: GOOD MATCH
- Primary domain = role domain
- Several projects in this domain
- Some relevant experience or strong education
- Meets all core requirements

50-69: WEAK MATCH - DIFFERENT PRIMARY DOMAIN
- Primary domain ≠ role domain
- Has SOME overlapping tools/skills
- But clearly pursuing a different career path
- Would need complete retraining

25-49: POOR MATCH
- Completely different domain
- Minimal overlapping skills
- Wrong career direction

STRICT RULES:
1. Knowing common tools (Python, SQL, Git) does NOT make someone qualified for every role that uses those tools
2. "Interested in X" or "certified in X" WITHOUT projects in X = NOT qualified in X
3. If their projects are in domain A and role needs domain B → score MUST be <55
4. Be ruthlessly honest about PRIMARY domain from their actual work
5. Give precise scores: 23, 38, 47, 52, 58, 63, 71, 78, 84, 88, 92, 96
6. NEVER use multiples of 5 or 10"""

            user_msg = f"""JOB REQUIREMENTS:
{jd}

CANDIDATE RESUME:
{resume}

YOUR TASK: Determine if this candidate's PRIMARY CAREER DOMAIN matches what this role needs.

FOLLOW THESE STEPS EXACTLY:

**STEP 1: What domain does this ROLE need?**
Read the job description carefully. Is this role for:
- Data Science / Machine Learning / AI?
- Web Development (Frontend/Backend/Full-stack)?
- Mobile Development?
- DevOps / Cloud / Infrastructure?
- Another specific domain?

**STEP 2: What is the candidate's PRIMARY domain?**
Look at their ACTUAL PROJECT WORK (most important evidence):
- List their 3-5 main projects
- What did each project focus on? (e.g., "Web app for e-commerce", "ML model for prediction", "Mobile game")
- What domain do these projects collectively represent?

Also check:
- Previous job titles and what they built there
- What their degree/education focused on

**STEP 3: Do the domains MATCH?**
Compare STEP 1 and STEP 2.

If PRIMARY domains are THE SAME:
  → Candidate qualifies for this role → Score 70-98 based on depth/quality
  
If PRIMARY domains are DIFFERENT:
  → Candidate does NOT qualify → Score MUST be 25-54
  → Even if they know some common tools (Python, SQL, Git)
  → Tools alone ≠ Domain expertise
  → BUT within 25-54, differentiate based on quality/education/interest

**STEP 4: Assign Score**

IF DOMAINS MATCH (score 70-98):
- 90-98: Exceptional - multiple strong projects, work experience, perfect education
- 78-89: Strong - several good projects, relevant experience or education
- 70-77: Good - meets requirements, some projects in domain

IF DOMAINS DON'T MATCH (score 25-54):
Even though both candidates are rejected, you MUST DIFFERENTIATE them based on:

CRITICAL: Give DIFFERENT scores even if both are from the same wrong domain!

Evaluate these factors to differentiate:
1. **Certifications in target domain** (+3-8 points)
   - Has ML/DS certification vs none
2. **Relevant coursework** (+2-6 points)
   - Took data analysis/ML courses vs none
3. **Tool proficiency** (+2-5 points)
   - Knows Python, SQL, Pandas vs just basic programming
4. **Interest signals** (+1-4 points)
   - Explicitly mentions "interested in data science" vs no mention
5. **Side projects** (+2-6 points)
   - Any data-related hobby projects vs none
6. **Education relevance** (+2-5 points)
   - CS degree vs non-technical degree

Within the rejection range:
- 47-54: Different domain + multiple relevant certs/courses + clear DS interest
- 39-46: Different domain + some relevant tools/certs + mentions interest
- 31-38: Different domain + basic tools only (Python/SQL) + no DS interest
- 25-30: Completely unrelated field + no overlap

EXAMPLE TO FORCE DIFFERENTIATION:
Both are web devs for DS role (both rejected):
- Candidate A: Python, ML certification, "interested in data science" → Score 49
- Candidate B: Python, no certs, no DS interest mentioned → Score 38
→ 11 point difference! Do NOT give them the same score.

CRITICAL REMINDERS:
- Web Development ≠ Data Science (even if both use Python)
- Data Science ≠ Backend Development (even if both use databases)
- Mobile Development ≠ Frontend Development (even if both build UIs)
- Certifications or "interests" WITHOUT projects = does NOT count

MANDATORY DIFFERENTIATION:
NO TWO CANDIDATES should receive the EXACT SAME SCORE unless they are truly identical (extremely rare).

When both are rejected but from same domain, find the differentiators:
✓ Count certifications: 2 certs vs 0 certs = +6-8 points difference
✓ Check interests section: mentions "data science" vs doesn't = +3-5 points
✓ Tool depth: knows Pandas/NumPy vs just Python = +3-4 points
✓ Coursework: took ML course vs didn't = +4-6 points

EXAMPLE - Both web devs, both rejected for DS role:
- Candidate A: Python, MySQL, "Interested in Data Analysis & ML", has ML certification → Score 49
- Candidate B: Python, MySQL, React projects only, no DS interest → Score 38
→ Must be 10+ point difference based on interest+certification

Threshold for this role: {threshold}

🚨 CRITICAL SCORING REQUIREMENTS:
1. NO TWO CANDIDATES should receive the SAME score (vary by at least 3-6 points minimum)
2. NEVER use round numbers: BANNED scores: 40, 42, 45, 50, 55, 60, 65, 70, 75, 80, 85, 90, 95, 100
3. Use PRECISE, IRREGULAR scores: 28, 33, 37, 41, 44, 48, 51, 56, 59, 62, 67, 72, 76, 79, 83, 87, 91, 94, 97
4. Even tiny differences (one more certification, slightly better wording) = 3-5 point difference
5. If you find yourself giving the same score twice, ADD/SUBTRACT 4-7 points based on ANY small factor

SCORING EXAMPLES for rejected candidates (different wrong domains):
- DevOps candidate for DS role: 36 (has Python, Docker, no DS interest)
- DevOps candidate for DS role: 44 (has Python, Docker, + ML course, mentions "data analysis")
→ 8 point difference for the ML course + interest

- Web dev for DS role: 39 (React, Node, Python, no DS work)
- Web dev for DS role: 47 (React, Node, Python, + Pandas, mentions "interested in AI")
→ 8 point difference for Pandas + interest

Return ONLY valid JSON:
{{"score": <integer 0-100>, "above_threshold": <boolean>, "reasoning": "<State: 1) Role's domain, 2) Candidate's primary domain from projects, 3) Match decision, 4) If rejected: what factors affected their score within rejection range, 5) Why this SPECIFIC score (not 3 points higher/lower)>"}}"""

            resp = client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": user_msg},
                ],
                temperature=1.2,  # Very high temp to force score variation
                top_p=0.95,  # Add nucleus sampling for more diversity
            )
            raw = (resp.choices[0].message.content or "").strip()
            # Strip markdown code block if present
            if raw.startswith("```"):
                raw = re.sub(r"^```\w*\n?", "", raw).strip()
                raw = re.sub(r"\n?```$", "", raw).strip()
            data = json.loads(raw)
            return {
                "score": int(data.get("score", 0)),
                "above_threshold": bool(data.get("above_threshold", False)),
                "reasoning": str(data.get("reasoning", ""))[:500],
                "source": "llm",
            }
        except Exception as e:
            logger.warning("LLM scoring failed, using keyword fallback: %s", e)
            print(f"  [LLM skipped] Groq API failed: {e} → using keyword match instead.")

    # Fallback: extract keywords from job description and score by presence in resume
    if not api_key and jd:
        print("  [LLM skipped] No GROQ_API_KEY in environment → using keyword match.")
    elif api_key and not jd:
        print("  [LLM skipped] No job skills text → using keyword match.")
    keywords = _extract_keywords_from_jd(jd) if jd else []
    if not keywords:
        return {
            "score": 100,
            "above_threshold": True,
            "reasoning": "No job description provided; no keyword check.",
            "source": "keyword_fallback",
        }
    resume_lower = resume.lower()
    matched = [k for k in keywords if k in resume_lower]
    score = round(100 * len(matched) / len(keywords))
    above = score >= threshold
    return {
        "score": score,
        "above_threshold": above,
        "reasoning": f"Matched {len(matched)}/{len(keywords)} terms from job description." + (
            f" Matched: {', '.join(matched[:10])}." if matched else ""
        ),
        "source": "keyword_fallback",
        "matched_keywords": matched,
        "missing_keywords": [k for k in keywords if k not in resume_lower],
    }
