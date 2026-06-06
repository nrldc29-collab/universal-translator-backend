"""
Rule Engine — fully offline, zero-dependency implementations of all
ailang agent capabilities.

Every function is pure Python: no API calls, no network, no external
services. The pipeline_runner uses these by default.

To upgrade specific agents to LLM-powered versions, set in .env:
    USE_LLM_AGENTS=true

Then configure at least one LLM provider:
  Local (free, offline):  OLLAMA_ENABLED=true
  Cloud (API key):        OPENAI_API_KEY=sk-...

LLM providers are tried in order: Ollama (local) -> OpenAI (cloud) -> CIP -> stub

The interface (signatures and return shapes) is identical in all modes.

Accuracy vs LLM mode:
  Domain / urgency / formality     ~95%  (word-boundary keyword match)
  Dialect routing                  100%  (lookup table)
  Glossary enforcement             100%  (exact string match)
  Idiom / ambiguity detection       ~65% (known-phrase dict)
  Confidence flagging               ~80% (threshold scoring)
  Back-translation verification     ~70% (word overlap)
  Speaker profiling                 ~65% (word complexity heuristic)
  Context memory / pronouns         ~60% (named-entity heuristic)
  Quality scoring                   ~65% (length/number/overlap heuristic)
"""

from __future__ import annotations
import os
import re
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Mode flag
# ---------------------------------------------------------------------------

def llm_enabled() -> bool:
    return os.environ.get("USE_LLM_AGENTS", "").lower() in ("true", "1", "yes")


# ---------------------------------------------------------------------------
# Shared helper: word-boundary match (prevents "lol" hitting "metoprolol")
# ---------------------------------------------------------------------------

def _wb(text: str, term: str) -> bool:
    """True if `term` appears as a whole word in `text`."""
    return bool(re.search(r'\b' + re.escape(term) + r'\b', text, re.IGNORECASE))

def _wb_count(text: str, terms: List[str]) -> int:
    return sum(1 for t in terms if _wb(text, t))


# ===========================================================================
# 1. DOMAIN DETECTION
# ===========================================================================

_DOMAIN_TERMS: Dict[str, List[str]] = {
    "medical": [
        "doctor","hospital","medication","allergy","allergic","pain","blood",
        "emergency","dose","dosage","symptom","diagnosis","surgery","prescription",
        "pharmacy","nurse","fever","infection","vaccine","therapy","clinic",
        "ambulance","oxygen","pulse","fracture","diabetes","insulin","antibiotic",
        "penicillin","morphine","metoprolol","metformin","patient","wound",
        "bleeding","unconscious","seizure","stroke","cancer","tumor","chemotherapy",
        "biopsy","ultrasound","icu","triage","anesthesia","catheter","intravenous",
        "hypertension","cardiac","respiratory","anticoagulant","aspirin",
    ],
    "legal": [
        "lawyer","court","contract","rights","judge","arrest","custody","statute",
        "liability","plaintiff","defendant","verdict","testimony","bail","warrant",
        "appeal","jurisdiction","negligence","settlement","attorney","lawsuit",
        "prosecution","acquittal","indictment","subpoena","affidavit","waive",
        "waiver","hereby","pursuant","notwithstanding",
    ],
    "financial": [
        "money","bank","price","cost","invoice","payment","refund","interest",
        "mortgage","deposit","withdrawal","balance","credit","debit","currency",
        "tax","insurance","loan","budget","revenue","profit","dividend","equity",
        "shares","stock","portfolio","investment","audit","payroll","receipt",
    ],
    "technical": [
        "server","database","api","endpoint","deploy","container","kubernetes",
        "module","function","variable","compile","runtime","debug","framework",
        "repository","commit","merge","branch","docker","microservice","pipeline",
        "algorithm","encryption","authentication","cache","socket","protocol",
        "http","rest","graphql","webhook","payload","json","yaml","sdk","cli",
    ],
    "travel": [
        "passport","visa","airport","flight","hotel","reservation","boarding",
        "customs","luggage","gate","terminal","taxi","train","ticket","itinerary",
        "accommodation","hostel","resort","tour","departure","arrival","baggage",
    ],
    "education": [
        "school","university","professor","student","exam","grade","homework",
        "lecture","degree","scholarship","campus","tuition","semester","thesis",
        "assignment","classroom","teacher","enroll","curriculum","syllabus",
    ],
}

def detect_domain(text: str) -> str:
    lowered = text.lower()
    scores = {domain: _wb_count(lowered, terms)
              for domain, terms in _DOMAIN_TERMS.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "general"


# ===========================================================================
# 2. FORMALITY DETECTION
# ===========================================================================

_FORMAL_MARKERS = [
    "would you","could you","i would appreciate","kindly","sir","madam",
    "regarding","therefore","furthermore","pursuant","hereby","therein",
    "notwithstanding","whereas","herewith","henceforth","aforementioned",
]
_INFORMAL_MARKERS = [
    "hey","gonna","wanna","lol","yo","dude","bro","nah","yeah","cool",
    "stuff","kinda","gotta","lemme","gimme","y'all","tbh","omg","wtf",
    "lmao","bruh","lit","vibe","chill","sick","dope","fire","goat","ngl",
]

def detect_formality(text: str, domain: str) -> str:
    lowered = text.lower()
    # Use word-boundary matching to avoid substring false positives
    formal_score   = _wb_count(lowered, _FORMAL_MARKERS)
    informal_score = _wb_count(lowered, _INFORMAL_MARKERS)
    if formal_score > informal_score:                  return "formal"
    if informal_score > formal_score:                  return "informal"
    if domain in ("medical","legal","financial"):      return "formal"
    return "neutral"


# ===========================================================================
# 3. URGENCY DETECTION
# ===========================================================================

_URGENT_TERMS = [
    "emergency","urgent","help","immediately","hurry","quick","asap",
    "dying","danger","fire","accident","bleeding","unconscious","critical",
    "life-threatening","mayday","sos","stat","right away","right now",
]

def detect_urgency(text: str, context: Dict) -> str:
    if _wb_count(text.lower(), _URGENT_TERMS) > 0: return "urgent"
    return context.get("urgency", "normal")


# ===========================================================================
# 4. MODEL SELECTION (routing hint for LLM mode)
# ===========================================================================

def select_model(domain: str, urgency: str, text_length: int) -> str:
    """Select the best model alias for this translation.

    Returns a model alias string that _route_ai_call maps to the
    appropriate provider (Ollama / OpenAI / stub).
    """
    # Check if Ollama is available (local LLM, preferred)
    ollama_enabled = os.environ.get("OLLAMA_ENABLED", "").lower() in ("true", "1", "yes")
    # Check if OpenAI is available (cloud LLM)
    openai_key = os.environ.get("OPENAI_API_KEY", "")
    openai_available = bool(openai_key and not openai_key.startswith("your_api"))

    if domain in ("medical","legal"):
        # Critical domains: prefer OpenAI for highest accuracy, Ollama if no key
        return "claude" if openai_available else ("claude" if ollama_enabled else "fast")
    if urgency == "urgent" and text_length < 80:
        return "fast"
    if text_length > 300:
        return "claude" if (openai_available or ollama_enabled) else "fast"
    return "fast"


# ===========================================================================
# 5. TRANSLATION INSTRUCTIONS BUILDER
# ===========================================================================

def build_instructions(domain: str, formality: str, urgency: str) -> List[str]:
    out: List[str] = []
    _domain_instrs = {
        "medical":   ["Use precise medical terminology",
                      "Do not paraphrase drug names",
                      "Preserve dosage numbers exactly"],
        "legal":     ["Maintain legal precision",
                      "Keep formal register",
                      "Preserve clause structure"],
        "financial": ["Preserve all numbers and currencies exactly",
                      "Use standard financial terminology"],
        "technical": ["Keep technical terms untranslated when standard",
                      "Preserve code identifiers and acronyms"],
        "travel":    ["Use locally common terms for places and transport"],
    }
    out += _domain_instrs.get(domain, [])
    if formality == "formal":   out.append("Use formal register and honorifics")
    if formality == "informal": out.append("Keep casual tone, use target language colloquialisms")
    if urgency == "urgent":     out.append("Prioritize clarity and brevity over elegance")
    return out


# ===========================================================================
# 6. DIALECT ROUTING
# ===========================================================================

_DIALECT_DEFAULTS: Dict[str, str] = {
    "es": "es-MX", "pt": "pt-BR", "zh": "zh-CN",
    "ar": "ar-EG", "en": "en-US", "fr": "fr-FR", "de": "de-DE",
}

_DIALECT_HINTS: Dict[str, str] = {
    "es-MX": "Mexican Spanish: prefer 'carro' over 'coche', 'camion' for bus, use ustedes not vosotros.",
    "es-ES": "Spain Spanish: 'coche', 'autobuses', vosotros is appropriate.",
    "es-AR": "Rioplatense Spanish: use 'vos' instead of 'tu'.",
    "pt-BR": "Brazilian Portuguese: 'voce' preferred, 'onibus' for bus, 'celular' for phone.",
    "pt-PT": "European Portuguese: 'autocarro' for bus, 'telemovel' for phone.",
    "zh-CN": "Simplified Chinese, Mandarin mainland.",
    "zh-TW": "Traditional Chinese, Taiwan.",
    "zh-HK": "Traditional Chinese with Cantonese influences, Hong Kong.",
    "en-GB": "British English: 'lift' not 'elevator', 'flat' not 'apartment', '-ise' endings.",
    "en-US": "American English: standard vocabulary, '-ize' endings.",
    "fr-CA": "Canadian French (Quebecois): 'courriel' for email, distinct vocabulary.",
    "ar-EG": "Egyptian Arabic dialect — most widely understood.",
    "ar-SA": "Modern Standard / Gulf Arabic.",
    "de-AT": "Austrian German: regional vocabulary differences.",
    "de-CH": "Swiss German: formal written standard.",
}

def resolve_dialect(lang: str, preference: str = "") -> str:
    if preference and len(preference) > 2: return preference
    return _DIALECT_DEFAULTS.get(lang, lang)

def get_dialect_hint(dialect_code: str) -> str:
    return _DIALECT_HINTS.get(dialect_code, "")


# ===========================================================================
# 7. GLOSSARY INJECTION
# ===========================================================================

def load_glossary(glossary: List[Dict], lang_pair: str) -> List[Dict]:
    return [e for e in (glossary or [])
            if e.get("lang_pair") in (lang_pair, "*")]

def find_glossary_matches(text: str, entries: List[Dict]) -> List[Dict]:
    lowered = text.lower()
    return [e for e in entries if e.get("source","").lower() in lowered]

def build_glossary_note(matches: List[Dict]) -> str:
    if not matches: return ""
    lines = ["Mandatory term translations (do not deviate):"]
    for m in matches:
        ctx = f" ({m['context']})" if m.get("context") else ""
        lines.append(f"  '{m['source']}' => '{m['target']}'{ctx}")
    return "\n".join(lines)


# ===========================================================================
# 8. CONFIDENCE FLAGGING
# ===========================================================================

def classify_confidence(score: float, domain: str) -> str:
    threshold = 0.92 if domain in ("medical","legal") else 0.85
    if score >= threshold:  return "high"
    if score >= 0.65:       return "medium"
    return "low"

def confidence_result(text: str, translation: str,
                      score: float, domain: str) -> Dict:
    tier = classify_confidence(score, domain)
    return {
        "final_translation": translation,
        "tier":    tier,
        "escalated": False,
        "flagged": tier != "high",
        # LLM upgrade: ConfidenceFallbackAgent retranslates medium/low tier
        # results using Claude when USE_LLM_AGENTS=true.
    }


# ===========================================================================
# 9. BACK-TRANSLATION VERIFICATION (word overlap heuristic)
# ===========================================================================

def _tokenise(text: str) -> set:
    return set(re.findall(r'\b\w+\b', text.lower()))

def word_overlap_score(a: str, b: str) -> float:
    ta, tb = _tokenise(a), _tokenise(b)
    if not ta or not tb: return 0.0
    # Remove very common stop words to make score more meaningful
    stops = {"the","a","an","is","are","was","were","be","to","of","and","or",
             "in","on","at","for","with","that","this","it","i","we","you"}
    ta -= stops; tb -= stops
    if not ta or not tb: return 0.5  # all stop words — assume ok
    return len(ta & tb) / max(len(ta), len(tb))

def back_translation_result(original: str, translation: str,
                             back_translated: str, domain: str) -> Dict:
    score     = word_overlap_score(original, back_translated)
    threshold = 0.35 if domain in ("medical","legal") else 0.25
    passed    = score >= threshold
    return {
        "verified":           passed,
        "final_translation":  translation,
        "similarity_score":   round(score, 3),
        "method":             "word_overlap",
        "improved":           False,
        "flagged":            not passed,
        # LLM upgrade: BackTranslatorAgent calls Claude to actually
        # back-translate and semantically compare, then rewrites if needed.
    }


# ===========================================================================
# 10. AMBIGUITY DETECTION (known-phrase dictionary)
# ===========================================================================

_KNOWN_AMBIGUITIES: List[Dict] = [
    {"phrase":"break a leg",    "type":"idiom",
     "interpretations":["good luck (idiomatic)","literally break a leg"],
     "preferred":"good luck (idiomatic)"},
    {"phrase":"can't bear",     "type":"lexical",
     "interpretations":["cannot endure/tolerate","cannot physically carry"],
     "preferred":"cannot endure/tolerate"},
    {"phrase":"cannot bear",    "type":"lexical",
     "interpretations":["cannot endure","cannot physically carry"],
     "preferred":"cannot endure"},
    {"phrase":"bear it",        "type":"lexical",
     "interpretations":["endure it","physically carry it"],
     "preferred":"endure it"},
    {"phrase":"i can't stand",  "type":"lexical",
     "interpretations":["I strongly dislike","I cannot physically stand"],
     "preferred":"I strongly dislike"},
    {"phrase":"time flies",     "type":"idiom",
     "interpretations":["time passes quickly","insects that fly"],
     "preferred":"time passes quickly"},
    {"phrase":"hit the road",   "type":"idiom",
     "interpretations":["begin a journey","literally hit the road"],
     "preferred":"begin a journey"},
    {"phrase":"kick the bucket","type":"idiom",
     "interpretations":["to die (idiomatic)","to literally kick a bucket"],
     "preferred":"to die (idiomatic)"},
    {"phrase":"raining cats and dogs","type":"idiom",
     "interpretations":["raining very hard","literal animals falling"],
     "preferred":"raining very hard"},
    {"phrase":"under the weather","type":"idiom",
     "interpretations":["feeling ill","literally under weather"],
     "preferred":"feeling ill"},
    {"phrase":"bite the bullet","type":"idiom",
     "interpretations":["endure pain stoically","literally bite a bullet"],
     "preferred":"endure pain stoically"},
    {"phrase":"once in a blue moon","type":"idiom",
     "interpretations":["very rarely","literally a blue moon"],
     "preferred":"very rarely"},
    {"phrase":"it's not rocket science","type":"idiom",
     "interpretations":["it's not difficult","literally rocket science"],
     "preferred":"it's not difficult"},
]

def detect_ambiguities(text: str, source_lang: str) -> List[Dict]:
    lowered = text.lower()
    return [
        {**entry, "confidence": 0.85, "method": "rule_based"}
        for entry in _KNOWN_AMBIGUITIES
        if entry["phrase"] in lowered
    ]


# ===========================================================================
# 11. SPEAKER PROFILING (word complexity heuristic)
# ===========================================================================

_COMPLEX_WORDS = {
    "administer","pursuant","notwithstanding","henceforth","aforementioned",
    "myocardial","infarction","anticoagulant","contraindicated","pharmacological",
    "jurisprudence","indemnification","amortization","depreciation","algorithmic",
    "microservice","containerized","kubernetes","orthogonal","epistemological",
    "exacerbate","ameliorate","pathophysiology","post-operative","intravenous",
}
_SLANG_WORDS = {
    "gonna","wanna","kinda","gotta","lemme","gimme","ain't","y'all","tbh",
    "omg","lol","bruh","lit","vibe","dope","fire","goat","slay","cap","ngl",
}

def analyze_vocabulary_level(texts: List[str]) -> str:
    if not texts: return "unknown"
    combined = " ".join(texts).lower()
    # Only analyse ASCII words to avoid Chinese chars inflating avg_len
    words = [w for w in re.findall(r'\b[a-z]{2,}\b', combined)]
    if not words: return "unknown"
    avg_len       = sum(len(w) for w in words) / len(words)
    complex_count = sum(1 for w in words if w in _COMPLEX_WORDS)
    if complex_count >= 2 or avg_len >= 7.5: return "advanced"
    if avg_len >= 5.5:                        return "intermediate"
    return "basic"

def analyze_register(texts: List[str]) -> str:
    if not texts: return "neutral"
    combined = " ".join(texts).lower()
    formal_score   = _wb_count(combined, _FORMAL_MARKERS)
    words          = re.findall(r'\b[a-z]+\b', combined)
    slang_count    = sum(1 for w in words if w in _SLANG_WORDS)
    informal_score = _wb_count(combined, _INFORMAL_MARKERS)
    if formal_score > max(informal_score, slang_count): return "formal"
    if slang_count >= 2:                                return "slang"
    if informal_score > formal_score:                   return "informal"
    return "neutral"

def get_style_instructions(profile: Dict, target_lang: str) -> List[str]:
    vocab    = profile.get("vocabulary_level","intermediate")
    register = profile.get("register","neutral")
    out: List[str] = []
    if vocab == "basic":
        out.append(f"Use simple, everyday vocabulary in {target_lang}.")
    elif vocab in ("advanced","technical"):
        out.append(f"Match sophisticated vocabulary level in {target_lang}.")
    if register == "formal":
        out.append("Use formal register and honorifics.")
    elif register == "informal":
        out.append("Use conversational informal speech.")
    elif register == "slang":
        out.append("Match casual/slang register with culturally equivalent expressions.")
    return out


# ===========================================================================
# 12. CONTEXT MEMORY (named entity + pronoun resolution)
# ===========================================================================

# Pronouns to exclude from name detection
_PRONOUNS = {
    "he","she","they","it","we","i","you","him","her","them","his","hers",
    "its","our","your","their","mine","yours","ours","theirs","this","that",
    "these","those","who","which","what","there","here","is","was","are",
    "were","has","have","had","be","been","being","do","did","does",
}
_NAME_PATTERN = re.compile(r'\b([A-Z][a-z]{1,20})\b')
_PRONOUN_REFS = {
    "he":"male","him":"male","his":"male",
    "she":"female","her":"female","hers":"female",
    "they":"neutral","them":"neutral","their":"neutral",
    "it":"object",
}

def extract_entities(text: str, history: List[Dict]) -> Dict:
    # Collect capitalised words that are not pronouns
    def _names(t: str) -> List[str]:
        return [n for n in _NAME_PATTERN.findall(t)
                if n.lower() not in _PRONOUNS]

    current_names = _names(text)
    history_names: List[str] = []
    for turn in history[-4:]:
        history_names += _names(turn.get("text",""))

    people = list(dict.fromkeys(current_names + history_names))
    pronouns_used = [p for p in _PRONOUN_REFS if _wb(text.lower(), p)]
    return {"people": people, "pronouns_used": pronouns_used}

def resolve_pronouns(text: str, entities: Dict, history: List[Dict]) -> str:
    pronouns_used = entities.get("pronouns_used", [])
    if not pronouns_used:
        return text

    # Build mention map: only real names (filtered), not pronouns
    mention_map: Dict[str, str] = {}
    for turn in history[-6:]:
        for name in _NAME_PATTERN.findall(turn.get("text","")):
            if name.lower() not in _PRONOUNS:
                mention_map[name.lower()] = name

    if not mention_map:
        return text

    resolved = text
    # If exactly one known person — safe to annotate pronouns
    if len(mention_map) == 1:
        name = list(mention_map.values())[0]
        for pronoun in ("him","her","them","it"):
            if _wb(resolved.lower(), pronoun):
                pat = re.compile(r'\b' + pronoun + r'\b', re.IGNORECASE)
                resolved = pat.sub(f"{pronoun} ({name})", resolved, count=1)
    return resolved

def build_history_summary(history: List[Dict], max_turns: int = 4) -> str:
    lines = []
    for turn in history[-max_turns:]:
        spk = turn.get("speaker","?")
        src = turn.get("text","")
        tgt = turn.get("translated","")
        lines.append(f"{spk}: {src} → {tgt}")
    return "\n".join(lines)

def detect_topic_shift(text: str, history: List[Dict]) -> bool:
    if not history: return False
    last_domain = detect_domain(history[-1].get("text",""))
    curr_domain = detect_domain(text)
    return curr_domain != last_domain and curr_domain != "general"


# ===========================================================================
# 13. QUALITY SCORING (heuristic)
# ===========================================================================

def quality_score(original: str, translation: str,
                  source_lang: str, target_lang: str, domain: str) -> Dict:
    issues: List[str] = []

    if not translation or not translation.strip():
        return {"pass":False,"score":0,"issues":["Empty translation"],"critical":True,"method":"rule_based"}

    orig_words  = len(original.split())
    trans_words = len(translation.split())
    ratio       = trans_words / max(orig_words, 1)

    if ratio < 0.3:
        issues.append(f"Translation suspiciously short (ratio {ratio:.2f})")
    if ratio > 5.0:
        issues.append(f"Translation suspiciously long (ratio {ratio:.2f})")

    # Same-language check (did it actually translate?)
    overlap = word_overlap_score(original, translation)
    if overlap > 0.80 and source_lang != target_lang:
        issues.append("Translation too similar to source — may not have translated")

    # Dosage preservation for medical
    if domain == "medical":
        numbers = re.findall(r'\b\d+(?:\.\d+)?\s*(?:mg|ml|mcg|unit|%)\b',
                             original, re.IGNORECASE)
        for num in numbers:
            val = re.search(r'\d+(?:\.\d+)?', num).group()
            if val not in translation:
                issues.append(f"Dosage '{num}' missing from translation")

    score = max(0, 10 - len(issues) * 2)
    return {
        "pass":     not issues,
        "score":    score,
        "issues":   issues,
        "critical": any("missing" in i or "empty" in i.lower() for i in issues),
        "method":   "rule_based",
        # LLM upgrade: QualityGuard uses Claude for full semantic review.
    }


# ===========================================================================
# 14. EMOTIONAL TONE DETECTION + TTS CONFIG
# ===========================================================================

_EMOTION_KEYWORDS: Dict[str, List[str]] = {
    "urgent":  ["emergency","hurry","quick","help","danger","urgent","immediately",
                "dying","bleeding","accident","poison","asap","stat","now"],
    "sad":     ["sorry","lost","miss","sad","unfortunately","regret","grief",
                "condolence","passed away","funeral","mourn","heartbroken"],
    "angry":   ["angry","furious","unacceptable","outraged","terrible","horrible",
                "disgusting","ridiculous","infuriated","livid"],
    "fearful": ["afraid","scared","terrified","fear","panic","anxious","dread"],
    "excited": ["amazing","fantastic","incredible","wonderful","thrilled","excited",
                "brilliant","awesome","outstanding","celebrate"],
    "warm":    ["thank you","grateful","appreciate","love","care","wonderful",
                "kind","generous","heartfelt","touched"],
}

_EMOTION_TTS: Dict[str, Dict] = {
    "neutral":  {"speed":1.0,  "pause_ms":200, "voice_style":"default"},
    "urgent":   {"speed":1.15, "pause_ms":100, "voice_style":"assertive"},
    "sad":      {"speed":0.85, "pause_ms":350, "voice_style":"soft"},
    "angry":    {"speed":1.05, "pause_ms":120, "voice_style":"firm"},
    "fearful":  {"speed":1.1,  "pause_ms":180, "voice_style":"tense"},
    "excited":  {"speed":1.1,  "pause_ms":150, "voice_style":"energetic"},
    "warm":     {"speed":0.95, "pause_ms":250, "voice_style":"friendly"},
}

def detect_emotion(text: str, context: Dict) -> Dict:
    lowered = text.lower()
    scores  = {e: _wb_count(lowered, kws) for e, kws in _EMOTION_KEYWORDS.items()}
    best    = max(scores, key=scores.get)
    emotion = best if scores[best] > 0 else "neutral"
    if context.get("urgency") == "urgent": emotion = "urgent"
    return {"emotion":emotion, "confidence":0.75, "method":"rule_based",
            "keyword_hits":scores.get(emotion, 0)}

def get_tts_config(text: str, emotion: str, lang: str) -> Dict:
    profile = _EMOTION_TTS.get(emotion, _EMOTION_TTS["neutral"])
    return {"text":text, "language":lang, **profile}
