"""
Context layer for improving translations with technical jargon and context memory.
Maintains conversation context and handles domain-specific terminology.
"""

import json
import re
from typing import Dict, List, Optional, Set
from pathlib import Path
from collections import defaultdict


class TechnicalJargonDatabase:
    """
    Database of technical terms and jargon for different domains.
    Helps maintain consistent translation of technical terminology.
    """
    
    def __init__(self, jargon_file: Optional[str] = None):
        self.jargon_file = jargon_file or "models/jargon/technical_terms.json"
        self.domains = self._load_jargon()
        self._custom_terms = defaultdict(dict)  # domain -> {term: translation}
        
    def _load_jargon(self) -> Dict[str, Dict[str, Dict[str, str]]]:
        """Load technical terms from JSON file."""
        path = Path(self.jargon_file)
        if not path.exists():
            return self._default_jargon()
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading jargon database: {e}")
            return self._default_jargon()
    
    def _default_jargon(self) -> Dict[str, Dict[str, Dict[str, str]]]:
        """Default technical jargon for common domains."""
        return {
            "medical": {
                "en": {
                    "myocardial infarction": "infarto de miocardio",
                    "hypertension": "hipertensión",
                    "diabetes mellitus": "diabetes mellitus",
                    "cerebrovascular accident": "accidente cerebrovascular",
                    "myocardial": "miocardio",
                    "infarction": "infarto",
                },
                "es": {
                    "infarto de miocardio": "myocardial infarction",
                    "hipertensión": "hypertension",
                    "diabetes mellitus": "diabetes mellitus",
                }
            },
            "legal": {
                "en": {
                    "plaintiff": "demandante",
                    "defendant": "demandado",
                    "affidavit": "afidávit",
                    "subpoena": "citación",
                    "jurisdiction": "jurisdicción",
                },
                "es": {
                    "demandante": "plaintiff",
                    "demandado": "defendant",
                    "afidávit": "affidavit",
                }
            },
            "tech": {
                "en": {
                    "API": "API",
                    "endpoint": "punto de conexión",
                    "database": "base de datos",
                    "framework": "marco de trabajo",
                    "middleware": "middleware",
                    "kubernetes": "kubernetes",
                    "docker": "docker",
                    "microservice": "microservicio",
                    "latency": "latencia",
                    "throughput": "rendimiento",
                },
                "es": {
                    "punto de conexión": "endpoint",
                    "base de datos": "database",
                    "marco de trabajo": "framework",
                }
            },
            "business": {
                "en": {
                    "ROI": "ROI",
                    "stakeholder": "partes interesadas",
                    "deliverable": "entregable",
                    "milestone": "hito",
                    "sprint": "sprint",
                    "agile": "ágil",
                },
                "es": {
                    "partes interesadas": "stakeholder",
                    "entregable": "deliverable",
                    "hito": "milestone",
                }
            }
        }
    
    def detect_domain(self, text: str) -> Optional[str]:
        """
        Detect the domain of the text based on technical terms.
        Returns the most likely domain or None.
        """
        text_lower = text.lower()
        domain_scores = defaultdict(int)
        
        for domain, languages in self.domains.items():
            for lang, terms in languages.items():
                for term in terms.keys():
                    if term.lower() in text_lower:
                        domain_scores[domain] += 1
        
        if not domain_scores:
            return None
        
        # Return domain with highest score
        return max(domain_scores.items(), key=lambda x: x[1])[0]
    
    def get_translation(
        self,
        term: str,
        source_lang: str,
        target_lang: str,
        domain: Optional[str] = None,
    ) -> Optional[str]:
        """
        Get the correct translation for a technical term.
        """
        if domain is None:
            domain = self.detect_domain(term)
        
        if domain and domain in self.domains:
            lang_data = self.domains[domain].get(source_lang, {})
            return lang_data.get(term.lower())
        
        return None
    
    def add_custom_term(
        self,
        term: str,
        translation: str,
        source_lang: str,
        target_lang: str,
        domain: str = "custom",
    ) -> None:
        """Add a custom technical term to the database."""
        if domain not in self.domains:
            self.domains[domain] = {}
        if source_lang not in self.domains[domain]:
            self.domains[domain][source_lang] = {}
        
        self.domains[domain][source_lang][term.lower()] = translation
        self._save_jargon()
    
    def _save_jargon(self) -> None:
        """Save jargon database to file."""
        path = Path(self.jargon_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.domains, f, indent=2, ensure_ascii=False)


class ContextMemory:
    """
    Maintains conversation context and translation memory.
    Remembers previous translations and context for better accuracy.
    """
    
    def __init__(self, max_history: int = 20):
        self.max_history = max_history
        self.conversation_history = []
        self.translation_memory = {}  # original -> (translation, count)
        self.detected_domains = set()
        self._term_usage_count = defaultdict(int)
        
    def add_exchange(
        self,
        source_text: str,
        translated_text: str,
        source_lang: str,
        target_lang: str,
        domain: Optional[str] = None,
    ) -> None:
        """Add a translation exchange to memory."""
        self.conversation_history.append({
            "source": source_text,
            "translation": translated_text,
            "source_lang": source_lang,
            "target_lang": target_lang,
            "domain": domain,
            "timestamp": len(self.conversation_history),
        })
        
        # Trim history if too long
        if len(self.conversation_history) > self.max_history:
            self.conversation_history = self.conversation_history[-self.max_history:]
        
        # Update translation memory
        key = f"{source_text}::{source_lang}->{target_lang}"
        if key in self.translation_memory:
            text, count = self.translation_memory[key]
            self.translation_memory[key] = (translated_text, count + 1)
        else:
            self.translation_memory[key] = (translated_text, 1)
        
        if domain:
            self.detected_domains.add(domain)
    
    def get_previous_translation(
        self,
        text: str,
        source_lang: str,
        target_lang: str,
    ) -> Optional[str]:
        """Get a previous translation if available."""
        key = f"{text}::{source_lang}->{target_lang}"
        if key in self.translation_memory:
            translation, count = self.translation_memory[key]
            return translation
        return None
    
    def get_context_summary(self) -> Dict:
        """Get a summary of the conversation context."""
        return {
            "total_exchanges": len(self.conversation_history),
            "detected_domains": list(self.detected_domains),
            "recent_topics": self._extract_topics(),
            "frequent_terms": dict(sorted(
                self._term_usage_count.items(),
                key=lambda x: x[1],
                reverse=True
            )[:10])
        }
    
    def _extract_topics(self) -> List[str]:
        """Extract main topics from recent conversation."""
        # Simple keyword extraction from recent history
        recent = self.conversation_history[-5:] if self.conversation_history else []
        all_text = " ".join(ex["source"] for ex in recent)
        
        # Extract capitalized words or quoted terms as potential topics
        topics = re.findall(r'"([^"]+)"|\b([A-Z][a-z]+)\b', all_text)
        topics = [t[0] or t[1] for t in topics if t[0] or t[1]]
        
        return list(set(topics))[:5]
    
    def clear(self) -> None:
        """Clear the context memory."""
        self.conversation_history = []
        self.translation_memory = {}
        self.detected_domains = set()
        self._term_usage_count = defaultdict(int)


class EnhancedContextLayer:
    """
    Enhanced context layer with technical jargon and context memory.
    Provides improved translations by considering context and technical terminology.
    """
    
    def __init__(
        self,
        jargon_db: Optional[TechnicalJargonDatabase] = None,
        context_memory: Optional[ContextMemory] = None,
    ):
        self.jargon_db = jargon_db or TechnicalJargonDatabase()
        self.context_memory = context_memory or ContextMemory()
        self._current_domain = None
        
    def improve(
        self,
        text: str,
        source_language: str,
        target_language: str,
        tone: Optional[str] = None,
    ) -> str:
        """
        Improve text translation by applying context and jargon knowledge.
        
        Args:
            text: Text to translate
            source_language: Source language code
            target_language: Target language code
            tone: Optional tone specification
            
        Returns:
            Improved text (with jargon corrections applied)
        """
        # Detect domain
        self._current_domain = self.jargon_db.detect_domain(text)
        
        # Check for technical terms and apply corrections
        improved_text = self._apply_jargon_corrections(
            text,
            source_language,
            target_language,
        )
        
        return improved_text
    
    def _apply_jargon_corrections(
        self,
        text: str,
        source_lang: str,
        target_lang: str,
    ) -> str:
        """
        Apply technical jargon corrections to text.
        Replaces common terms with their correct technical translations.
        """
        words = text.split()
        corrected = []
        
        for word in words:
            # Check if this is a technical term
            translation = self.jargon_db.get_translation(
                word,
                source_lang,
                target_lang,
                self._current_domain,
            )
            
            if translation:
                corrected.append(translation)
                self.context_memory._term_usage_count[word] += 1
            else:
                corrected.append(word)
        
        return " ".join(corrected)
    
    def add_exchange(
        self,
        source_text: str,
        translated_text: str,
        source_lang: str,
        target_lang: str,
    ) -> None:
        """Add a translation exchange to context memory."""
        self.context_memory.add_exchange(
            source_text,
            translated_text,
            source_lang,
            target_lang,
            self._current_domain,
        )
    
    def get_context_info(self) -> Dict:
        """Get context information for the UI."""
        return {
            "current_domain": self._current_domain,
            "context_summary": self.context_memory.get_context_summary(),
            "jargon_terms": self._get_relevant_jargon(),
        }
    
    def _get_relevant_jargon(self) -> List[Dict]:
        """Get jargon terms relevant to current context."""
        if not self._current_domain:
            return []
        
        domain_data = self.jargon_db.domains.get(self._current_domain, {})
        terms = domain_data.get("en", {})  # Default to English terms
        
        return [
            {"term": term, "translation": trans, "domain": self._current_domain}
            for term, trans in list(terms.items())[:10]
        ]
    
    def clear_context(self) -> None:
        """Clear the context memory."""
        self.context_memory.clear()
        self._current_domain = None


class PassthroughContextLayer:
    """
    Simple pass-through context layer for backward compatibility.
    """
    def improve(
        self,
        text: str,
        source_language: str,
        target_language: str,
        tone: Optional[str] = None,
    ) -> str:
        return text