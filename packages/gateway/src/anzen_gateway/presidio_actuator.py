"""
Presidio Actuator for PII Detection and Anonymization

Integrates Microsoft Presidio for detecting and masking PII in text.
"""

import logging
import re
from typing import Any, Dict, List

# Try to import Presidio, fall back to pattern-based detection if not available
try:
    from presidio_analyzer import AnalyzerEngine, RecognizerRegistry
    from presidio_analyzer.nlp_engine import NlpEngine
    from presidio_anonymizer import AnonymizerEngine
    from presidio_anonymizer.entities import OperatorConfig, RecognizerResult

    PRESIDIO_AVAILABLE = True
except ImportError:
    PRESIDIO_AVAILABLE = False

    # Mock classes for when Presidio is not available
    class AnalyzerEngine:
        def __init__(self, *args, **kwargs):
            pass

        def analyze(self, *args, **kwargs):
            return []

    class AnonymizerEngine:
        def __init__(self, *args, **kwargs):
            pass

        def anonymize(self, *args, **kwargs):
            class MockResult:
                def __init__(self, text):
                    self.text = text

            return MockResult("")

    class RecognizerResult:
        def __init__(self, *args, **kwargs):
            pass

    class OperatorConfig:
        def __init__(self, *args, **kwargs):
            pass

    class NlpEngine:
        def __init__(self, *args, **kwargs):
            pass


logger = logging.getLogger(__name__)


class SimpleNlpEngine(NlpEngine):
    """Simple NLP engine that doesn't require spaCy models."""

    def __init__(self):
        self.engine_name = "simple"
        self._loaded = True

    def process_text(self, text: str, language: str = "en"):
        """Simple text processing without spaCy."""

        # Create a simple mock document with all attributes Presidio might need
        class MockDoc:
            def __init__(self, text):
                self.text = text
                self.tokens = text.split()
                self.lemmas = [token.lower() for token in self.tokens]
                self.pos_tags = ["NOUN"] * len(self.tokens)
                self.entities = []
                self.scores = []  # Add scores attribute
                self.ents = []  # Add ents attribute
                self.noun_chunks = []  # Add noun_chunks attribute

            def __iter__(self):
                return iter(self.tokens)

            def __len__(self):
                return len(self.tokens)

            def __getitem__(self, i):
                return self.tokens[i]

        return MockDoc(text)

    def process_batch(self, texts: List[str], language: str = "en"):
        """Process multiple texts."""
        return [self.process_text(text, language) for text in texts]

    def is_available(self) -> bool:
        return True

    def is_loaded(self) -> bool:
        return self._loaded

    def load(self) -> None:
        """Load the engine (no-op for simple engine)."""
        self._loaded = True

    def get_supported_languages(self) -> List[str]:
        """Get supported languages."""
        return ["en"]

    def get_supported_entities(self) -> List[str]:
        """Get supported entities."""
        return []  # We rely on pattern-based recognizers

    def is_stopword(self, word: str, language: str = "en") -> bool:
        """Check if word is a stopword."""
        stopwords = {
            "the",
            "a",
            "an",
            "and",
            "or",
            "but",
            "in",
            "on",
            "at",
            "to",
            "for",
            "of",
            "with",
            "by",
        }
        return word.lower() in stopwords

    def is_punct(self, word: str, language: str = "en") -> bool:
        """Check if word is punctuation."""
        return word in ".,!?;:()[]{}\"'"


class PresidioActuator:
    """Presidio-based PII detection and anonymization."""

    def __init__(self):
        """Initialize Presidio engines."""
        # Force pattern-based detection to avoid spaCy model dependencies
        logger.info("Using pattern-based PII detection (no spaCy models required)")
        self.analyzer = None
        self.anonymizer = None

        # Define PII patterns for detection
        self.patterns = {
            "EMAIL_ADDRESS": re.compile(
                r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
            ),
            "PHONE_NUMBER": re.compile(
                r"(\+?1[-.\s]?)?\(?([0-9]{3})\)?[-.\s]?([0-9]{3})[-.\s]?([0-9]{4})"
            ),
            "US_SSN": re.compile(r"\b\d{3}-?\d{2}-?\d{4}\b"),
            "CREDIT_CARD": re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b"),
            "IBAN_CODE": re.compile(
                r"\b[A-Z]{2}\d{2}[A-Z0-9]{4}\d{7}([A-Z0-9]?){0,16}\b"
            ),
            "US_PASSPORT": re.compile(r"\b[A-Z]\d{8}\b"),
            "IP_ADDRESS": re.compile(r"\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b"),
            "PERSON": re.compile(r"\b[A-Z][a-z]+ [A-Z][a-z]+\b"),
        }

    def detect_pii(self, text: str, language: str = "en") -> List[Dict[str, Any]]:
        """
        Detect PII entities in text.

        Args:
            text: Input text to analyze
            language: Language code (default: en)

        Returns:
            List of detected entities with type, start, end, score, text
        """
        # Use pattern-based detection
        entities = []
        risk_levels = {
            "CREDIT_CARD": 0.95,
            "US_SSN": 0.95,
            "US_PASSPORT": 0.90,
            "IBAN_CODE": 0.85,
            "EMAIL_ADDRESS": 0.80,
            "PHONE_NUMBER": 0.75,
            "IP_ADDRESS": 0.70,
            "PERSON": 0.60,
        }

        for entity_type, pattern in self.patterns.items():
            for match in pattern.finditer(text):
                entity = {
                    "type": entity_type,
                    "start": match.start(),
                    "end": match.end(),
                    "score": risk_levels.get(entity_type, 0.5),
                    "text": match.group(),
                }
                entities.append(entity)

        logger.info(f"Detected {len(entities)} PII entities using pattern matching")
        return entities

    def anonymize_text(self, text: str, entities: List[Dict[str, Any]] = None) -> str:
        """
        Anonymize PII in text.

        Args:
            text: Input text to anonymize
            entities: Pre-detected entities (optional, will detect if not provided)

        Returns:
            Anonymized text with PII masked
        """
        # If no entities provided, detect them first
        if entities is None:
            entities = self.detect_pii(text)

        # Use pattern-based anonymization
        # Sort entities by start position in reverse order to avoid index shifting
        entities_sorted = sorted(entities, key=lambda x: x["start"], reverse=True)

        anonymized_text = text
        for entity in entities_sorted:
            entity_type = entity["type"]
            start = entity["start"]
            end = entity["end"]

            # Define replacement patterns
            if entity_type == "EMAIL_ADDRESS":
                replacement = f"***@{entity['text'].split('@')[1]}"
            elif entity_type == "PHONE_NUMBER":
                replacement = "***-***-" + entity["text"][-4:]
            elif entity_type == "CREDIT_CARD":
                replacement = "****-****-****-" + entity["text"][-4:]
            elif entity_type == "US_SSN":
                replacement = "***-**-" + entity["text"][-4:]
            elif entity_type == "IBAN_CODE":
                replacement = entity["text"][:4] + "****" + entity["text"][-4:]
            elif entity_type == "US_PASSPORT":
                replacement = "[PASSPORT]"
            elif entity_type == "IP_ADDRESS":
                replacement = "***.***.***." + entity["text"].split(".")[-1]
            elif entity_type == "PERSON":
                replacement = "[PERSON]"
            else:
                replacement = "[REDACTED]"

            # Replace the entity in the text
            anonymized_text = (
                anonymized_text[:start] + replacement + anonymized_text[end:]
            )

        logger.info(
            f"Anonymized text: {len(entities_sorted)} entities masked using pattern matching"
        )
        return anonymized_text


# NeMo Guardrails action functions
def detect_pii_entities(text: str) -> List[Dict[str, Any]]:
    """NeMo Guardrails action for PII detection."""
    actuator = PresidioActuator()
    return actuator.detect_pii(text)


def anonymize_pii_text(text: str) -> str:
    """NeMo Guardrails action for PII anonymization."""
    actuator = PresidioActuator()
    return actuator.anonymize_text(text)


def check_pii_risk_level(text: str) -> str:
    """NeMo Guardrails action for PII risk assessment."""
    actuator = PresidioActuator()
    entities = actuator.detect_pii(text)

    # Risk assessment logic
    high_risk_entities = ["CREDIT_CARD", "US_SSN", "US_PASSPORT", "IBAN_CODE"]
    medium_risk_entities = ["EMAIL_ADDRESS", "PHONE_NUMBER", "PERSON"]

    # Check for high-risk entities
    for entity in entities:
        if entity["type"] in high_risk_entities and entity["score"] >= 0.8:
            return "high"

    # Check for medium-risk entities
    for entity in entities:
        if entity["type"] in medium_risk_entities and entity["score"] >= 0.6:
            return "medium"

    # Low risk if no significant PII found
    return "low"
