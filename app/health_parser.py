"""
app/health_parser.py
────────────────────────────────────────────────────────────────────────────
Parses free-text WhatsApp messages into structured health log data.
LLaMA does the heavy lifting. Regex fallback if Ollama unavailable.
"""

import json, re, requests
from datetime import date
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator, ValidationError

# LLM handled by llm_client.py (OpenRouter or Ollama)
from app.llm_client import llm_complete as _llm_complete

# ── Pydantic schema — enforces structure on LLaMA output ─────────────────────
class HealthLog(BaseModel):
    log_date:            Optional[str]   = None
    steps:               Optional[int]   = None
    meals:               Optional[List[str]] = None
    mood_score:          Optional[float] = Field(None, ge=1, le=10)
    energy_score:        Optional[float] = Field(None, ge=1, le=10)
    pain_score:          Optional[float] = Field(None, ge=1, le=10)
    pain_locations:      Optional[List[str]] = None
    on_period:           Optional[bool]  = False
    cycle_day:           Optional[int]   = Field(None, ge=1, le=35)
    herbal_drinks:       Optional[List[str]] = None
    medicines:           Optional[List[str]] = None
    meditation_minutes:  Optional[int]   = Field(None, ge=0)
    sleep_hours:         Optional[float] = Field(None, ge=0, le=24)
    exercise_type:       Optional[str]   = None
    exercise_minutes:    Optional[int]   = Field(None, ge=0)
    exercise_intensity:  Optional[str]   = None
    notes:               Optional[str]   = None

    @field_validator("steps")
    @classmethod
    def steps_positive(cls, v):
        return abs(v) if v is not None else v  # "Steps -1000" → 1000

    @field_validator("pain_score", "mood_score", "energy_score")
    @classmethod
    def clamp_score(cls, v):
        if v is not None:
            return max(1.0, min(10.0, float(v)))
        return v

    @field_validator("exercise_type")
    @classmethod
    def normalize_exercise(cls, v):
        if v is None: return v
        valid = {"yoga","walking","running","stretching","gym","swimming","cycling","dance","pilates"}
        return v.lower() if v.lower() in valid else v.lower()

    @field_validator("exercise_intensity")
    @classmethod
    def normalize_intensity(cls, v):
        if v is None: return v
        return v.lower() if v.lower() in {"gentle","moderate","intense"} else "moderate"

    def to_dict(self) -> dict:
        return self.model_dump()


def _call_llama(prompt: str, system: str, label: str = "") -> Optional[dict]:
    """Call LLM (OpenRouter or Ollama), parse JSON, validate with Pydantic."""
    try:
        raw = _llm_complete(system=system, prompt=prompt, max_tokens=400, temperature=0.1)
        if not raw:
            return None
        raw = re.sub(r"```json|```", "", raw).strip()
        m = re.search(r'[{].*[}]', raw, re.DOTALL)
        if m: raw = m.group(0)
        parsed = json.loads(raw)
        validated = HealthLog(**parsed)
        return validated.to_dict()
    except (json.JSONDecodeError, ValidationError, Exception):
        return None

SYSTEM_PROMPT = """You are a health data extractor for an endometriosis tracker.
Extract health metrics from the user's natural language message.
Return ONLY valid JSON — no explanation, no markdown fences.

JSON schema (null for anything not mentioned):
{
  "log_date":           "YYYY-MM-DD",
  "steps":              integer or null,
  "meals":              ["food1","food2"] or null,
  "mood_score":         float 1-10 or null,
  "energy_score":       float 1-10 or null,
  "pain_score":         float 1-10 or null,
  "pain_locations":     ["lower abdomen","back"] or null,
  "on_period":          true/false or null,
  "cycle_day":          integer or null,
  "herbal_drinks":      ["ginger tea"] or null,
  "medicines":          ["ibuprofen"] or null,
  "meditation_minutes": integer or null,
  "sleep_hours":        float or null,
  "exercise_type":      "yoga/walking/running/stretching/gym/swimming/dance/pilates/cycling" or null,
  "exercise_minutes":   integer or null,
  "exercise_intensity": "gentle/moderate/intense" or null,
  "notes":              "anything else" or null
}

Rules:
- "feeling 6/10", "mood 6" → mood_score: 6.0
- "pain 7", "cramps 8/10" → pain_score: 7.0 or 8.0
- "low energy", "exhausted", "no energy", "drained" → energy_score: 2.0
- "okayish energy", "average energy", "okay energy" → energy_score: 5.0
- "good energy", "high energy", "feeling great", "energetic" → energy_score: 8.0
- "no pain", "pain free", "pain 1" → pain_score: 1.0
- "less pain", "little pain", "mild pain", "slight pain", "manageable pain" → pain_score: 3.0
- "moderate pain", "some pain", "okay pain" → pain_score: 5.0
- "bad pain", "high pain", "lot of pain", "severe pain" → pain_score: 7.0
- "unbearable pain", "worst pain", "extreme pain" → pain_score: 10.0
- "bad mood", "terrible mood", "low mood" → mood_score: 2.0
- "okay mood", "alright mood", "decent mood" → mood_score: 5.0
- "good mood", "great mood", "happy", "positive" → mood_score: 8.0
- Scale: pain/mood/energy all 1-10. Always infer a number from natural language — never return null if the user mentioned the concept
- "period day 2" → on_period: true, cycle_day: 2
- "Steps -1000" or "Steps- 1000" → steps: 1000 (the dash is a separator, always positive integer)
- "20 min yoga", "yoga 30 min", "gentle yoga" → exercise_type: "yoga", exercise_minutes: 20/30
- "walked 45 min", "morning walk" → exercise_type: "walking", exercise_minutes: 45
- "ran 5km", "20 min run" → exercise_type: "running"
- "15 min stretch", "stretching" → exercise_type: "stretching"
- "gentle/restorative/yin" → exercise_intensity: "gentle"
- "power/hot/vinyasa/intense" → exercise_intensity: "intense"
- All foods mentioned → meals list
- Herbal teas, kadha, golden milk → herbal_drinks list
- Any medicine/tablet → medicines list
- Today's date: {today}"""

EXERCISE_TYPES = {
    "yoga":       ["yoga","asana","vinyasa","hatha","pranayama","yin yoga"],
    "walking":    ["walk","walked","walking","stroll"],
    "running":    ["run","ran","running","jog","jogging"],
    "stretching": ["stretch","stretching","flexibility"],
    "gym":        ["gym","workout","weights","strength"],
    "swimming":   ["swim","swimming","pool"],
    "cycling":    ["cycl","bike","cycling"],
    "dance":      ["danc","zumba"],
    "pilates":    ["pilates"],
}

GENTLE_WORDS  = ["gentle","restorative","yin","slow","easy","light","relaxing"]
INTENSE_WORDS = ["power","intense","hot","vinyasa","ashtanga","hiit","vigorous"]


def parse_health_message(message: str) -> dict:
    """
    Parse WhatsApp message into structured health data.
    Flow:
      1. LLaMA attempt 1 → Pydantic validation
      2. If fails → re-prompt with stricter instructions (attempt 2)
      3. If still fails → regex fallback
    """
    today  = str(date.today())
    system = SYSTEM_PROMPT.replace("{today}", today)

    # ── Attempt 1: LLaMA + Pydantic validation ────────────────────────────────
    prompt1 = f"Extract health data from this message:\n\n{message}"
    data = _call_llama(prompt1, system, label="attempt1")

    # ── Attempt 2: Re-prompt with stricter instructions ───────────────────────
    if data is None:
        strict_system = system + """

IMPORTANT: Your previous response was not valid JSON or failed validation.
Return ONLY a raw JSON object. No text before or after it.
Every field must be null or the correct type — no strings where numbers are expected.
Steps must be a positive integer. Scores must be floats between 1.0 and 10.0."""
        prompt2 = (
            f"STRICT JSON ONLY. Extract health data:\n\n{message}\n\n"
            "Return only {{...}} with no other text."
        )
        data = _call_llama(prompt2, strict_system, label="attempt2")

    # ── Attempt 3: Regex fallback ─────────────────────────────────────────────
    if data is None:
        data = _regex_parse(message, today)
        source = "regex_fallback"
    else:
        source = "llama"

    # Ensure required defaults
    data.setdefault("log_date", today)
    if not data.get("log_date"): data["log_date"] = today
    if data.get("on_period") is None: data["on_period"] = False
    if data.get("exercise_type") and not data.get("exercise_intensity"):
        data["exercise_intensity"] = _infer_intensity(message)

    return {"success": True, "data": data, "raw_message": message, "error": source if source != "llama" else None}


def _infer_intensity(text: str) -> str:
    t = text.lower()
    if any(w in t for w in GENTLE_WORDS):  return "gentle"
    if any(w in t for w in INTENSE_WORDS): return "intense"
    return "moderate"


def _regex_parse(text: str, today: str) -> dict:
    t = text.lower()

    # Natural language → score mappings
    PAIN_WORDS = {
        1.0: ["no pain","pain free","pain-free","zero pain","pain 1"],
        2.0: ["very little pain","barely any pain","minimal pain"],
        3.0: ["less pain","little pain","mild pain","slight pain","manageable pain","low pain","bit of pain"],
        4.0: ["some pain","a little pain"],
        5.0: ["moderate pain","medium pain","okay pain","average pain","pain okay","pain fine"],
        6.0: ["above average pain","quite some pain"],
        7.0: ["bad pain","high pain","lot of pain","lots of pain","severe pain","strong pain"],
        8.0: ["very bad pain","really bad pain","intense pain"],
        9.0: ["horrible pain","terrible pain","awful pain"],
        10.0: ["unbearable pain","worst pain","extreme pain","excruciating"],
    }
    MOOD_WORDS = {
        1.0: ["terrible mood","awful mood","horrible mood","very bad mood","worst mood"],
        2.0: ["bad mood","low mood","very sad","depressed"],
        3.0: ["not great mood","down","not good mood"],
        4.0: ["slightly off","below average mood"],
        5.0: ["okay mood","alright mood","decent mood","fine mood","average mood","neutral mood"],
        6.0: ["not bad mood","fairly good mood"],
        7.0: ["good mood","pretty good mood"],
        8.0: ["great mood","happy","positive mood","feeling good"],
        9.0: ["very happy","excellent mood","amazing mood"],
        10.0: ["best mood","perfect mood","on top of the world"],
    }
    ENERGY_WORDS = {
        1.0: ["no energy","zero energy","completely drained","exhausted","bedridden"],
        2.0: ["very low energy","very tired","drained","wiped out"],
        3.0: ["low energy","tired","fatigued","lethargic"],
        4.0: ["below average energy","slightly tired"],
        5.0: ["okayish energy","average energy","okay energy","decent energy","moderate energy","some energy"],
        6.0: ["fairly good energy","not bad energy"],
        7.0: ["good energy","pretty energetic"],
        8.0: ["high energy","great energy","energetic","feeling energised","energized"],
        9.0: ["very energetic","lots of energy"],
        10.0: ["full of energy","best energy","peak energy"],
    }

    def _infer_from_words(word_map, text):
        for score, phrases in sorted(word_map.items()):
            for phrase in phrases:
                if phrase in text:
                    return score
        return None

    def find_score(keywords):
        for kw in keywords:
            m = re.search(rf'{kw}[:\s\-]*(\d+(?:\.\d+)?)\s*(?:/10)?', t)
            if m: return float(m.group(1))
        return None

    # Infer scores from natural language if numeric not found
    pain_score  = find_score(["pain","cramp","ache"]) or _infer_from_words(PAIN_WORDS, t)
    mood_score  = find_score(["mood","feeling","feel"]) or _infer_from_words(MOOD_WORDS, t)
    energy_score = find_score(["energy","energi"]) or _infer_from_words(ENERGY_WORDS, t)

    steps = None
    # Handle "Steps -1000" or "Steps: 1000" or "steps 1000" — dash is separator not minus
    m = re.search(r'steps?\s*[-:=]?\s*(\d[\d,]+)', t) or re.search(r'(\d[\d,]+)\s*steps?', t)
    if m: steps = abs(int(m.group(1).replace(",", "")))  # abs() ensures never negative

    on_period = bool(re.search(r'period|menstruat|cycle day', t))
    cycle_day = None
    m = re.search(r'(?:period|cycle)\s*day\s*(\d+)', t)
    if m: cycle_day = int(m.group(1))

    meditation = None
    m = re.search(r'medit\w*\s*(\d+)\s*min|(\d+)\s*min\w*\s*medit', t)
    if m: meditation = int(m.group(1) or m.group(2))

    sleep = None
    m = re.search(r'sleep\w*\s*(\d+(?:\.\d+)?)\s*h|(\d+(?:\.\d+)?)\s*h\w*\s*sleep', t)
    if m: sleep = float(m.group(1) or m.group(2))

    exercise_type, exercise_minutes = None, None
    for etype, keywords in EXERCISE_TYPES.items():
        for kw in keywords:
            m = re.search(rf'(\d+)\s*min\w*\s*{kw}|{kw}\w*\s*(?:for\s*)?(\d+)\s*min', t)
            if m:
                exercise_type    = etype
                exercise_minutes = int(m.group(1) or m.group(2))
                break
        if exercise_type: break

    return {
        "log_date":           today,
        "steps":              steps,
        "meals":              None,
        "mood_score":         mood_score,
        "energy_score":       energy_score,
        "pain_score":         pain_score,
        "pain_locations":     None,
        "on_period":          on_period,
        "cycle_day":          cycle_day,
        "herbal_drinks":      None,
        "medicines":          None,
        "meditation_minutes": meditation,
        "sleep_hours":        sleep,
        "exercise_type":      exercise_type,
        "exercise_minutes":   exercise_minutes,
        "exercise_intensity": _infer_intensity(text) if exercise_type else None,
        "notes":              text[:200],
    }


def build_confirmation(data: dict, action: str = "logged",
                       nutrition: dict = None) -> str:
    """Build SHORT WhatsApp confirmation — just key metrics + nutrition."""
    d = data.get("log_date", str(date.today()))
    header = f"✅ *Logged {d}*"

    # Key metrics only — one compact line each
    metrics = []
    if data.get("pain_score") is not None:
        ps = data["pain_score"]
        em = "🟢" if ps <= 3 else ("🟡" if ps <= 6 else "🔴")
        metrics.append(f"{em} Pain {ps}/10")
    if data.get("mood_score") is not None:
        metrics.append(f"😊 Mood {data['mood_score']}/10")
    if data.get("energy_score") is not None:
        metrics.append(f"⚡ Energy {data['energy_score']}/10")
    if data.get("sleep_hours"):
        metrics.append(f"😴 {data['sleep_hours']}h sleep")
    if data.get("steps"):
        metrics.append(f"👣 {int(data['steps']):,} steps")
    if data.get("exercise_type"):
        emins = f" {data['exercise_minutes']}min" if data.get("exercise_minutes") else ""
        metrics.append(f"🏃 {data['exercise_type'].title()}{emins}")

    lines = [header, "  ·  ".join(metrics) if metrics else ""]

    # Nutrition block
    if nutrition and nutrition.get("calories"):
        lines.append(f"\n📊 ~{nutrition['calories']} kcal  |  {nutrition.get('protein_g',0):.0f}g protein  |  {nutrition.get('iron_mg',0):.1f}mg iron")
        if nutrition.get("notes"):
            lines.append(f"💡 {nutrition['notes'][:120]}")

    lines.append("\n_Reply *summary* · *weekly* · *help*_")
    return "\n".join(lines)
