from __future__ import annotations

import datetime as dt
import logging
import math
import re
import sys
import time
import unicodedata
import warnings
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from itertools import combinations
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from app.models.vendor import Vendor
from app.schemas.verification import (
    ClassifierResult,
    Flag as NLPFlag,
    FlagSeverity,
    NLPResult,
)

try:
    import nltk
    from nltk.corpus import stopwords
    from nltk.stem import PorterStemmer
except Exception:  # pragma: no cover - dependency fallback
    nltk = None
    stopwords = None
    PorterStemmer = None

try:
    import spacy
except Exception:  # pragma: no cover - dependency fallback
    spacy = None

try:
    from rapidfuzz import fuzz
except Exception:  # pragma: no cover - dependency fallback
    fuzz = None

try:
    from dateutil import parser as date_parser
except Exception:  # pragma: no cover - dependency fallback
    date_parser = None

try:
    from sklearn.feature_extraction.text import CountVectorizer, TfidfTransformer, TfidfVectorizer
    from sklearn.naive_bayes import MultinomialNB
    from sklearn.pipeline import Pipeline
except Exception:  # pragma: no cover - dependency fallback
    CountVectorizer = None
    TfidfTransformer = None
    TfidfVectorizer = None
    MultinomialNB = None
    Pipeline = None


def _configure_logger() -> logging.Logger:
    logger = logging.getLogger("trustgate.nlp")
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    if any(getattr(handler, "_trustgate_nlp", False) for handler in logger.handlers):
        return logger

    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    formatter = logging.Formatter(
        "[TrustGate NLP] %(asctime)s | %(message)s",
        datefmt="%H:%M:%S",
    )

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(logging.INFO)
    stream_handler.setFormatter(formatter)
    stream_handler._trustgate_nlp = True

    logs_dir = Path("logs")
    logs_dir.mkdir(parents=True, exist_ok=True)
    file_handler = RotatingFileHandler(
        logs_dir / "nlp_pipeline.log",
        maxBytes=1_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    file_handler._trustgate_nlp = True

    logger.addHandler(stream_handler)
    logger.addHandler(file_handler)
    return logger


logger = _configure_logger()

NIGERIAN_DOC_STOPWORDS = {
    "federal",
    "republic",
    "nigeria",
    "limited",
    "company",
    "incorporated",
    "certificate",
    "commission",
    "affairs",
    "corporate",
    "registered",
    "hereby",
    "certify",
    "pursuant",
    "section",
    "act",
}

NAME_TITLES = {
    "chief",
    "dr",
    "engr",
    "barr",
    "hon",
    "prince",
    "alhaji",
    "hajia",
    "mr",
    "mrs",
    "miss",
    "ms",
}

SEVERITY_DEDUCTIONS = {
    FlagSeverity.CRITICAL: 30,
    FlagSeverity.HIGH: 15,
    FlagSeverity.MEDIUM: 8,
    FlagSeverity.LOW: 3,
    FlagSeverity.INFO: 0,
}

CATEGORY_KEYWORDS = {
    "retail": ["goods", "store", "shop", "merchandise", "product", "sales"],
    "food": ["restaurant", "food", "catering", "kitchen", "meal", "eatery"],
    "tech": ["software", "technology", "digital", "it", "system", "app"],
    "financial": ["investment", "finance", "loan", "credit", "forex", "crypto"],
    "construction": ["building", "contractor", "construction", "estate", "property"],
    "logistics": ["delivery", "courier", "logistics", "transport", "haulage"],
}


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str
    flags: list[NLPFlag] = field(default_factory=list)
    similarity_score: float | None = None

    @property
    def checks_passed(self) -> int:
        return 1 if self.passed else 0

    @property
    def checks_failed(self) -> int:
        return 0 if self.passed else 1


AnomalyFlag = NLPFlag


def _clean_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _clean_lines(text: str) -> str:
    return "\n".join(line.strip() for line in (text or "").splitlines() if line.strip())


def _normalise_unicode(text: str) -> str:
    normalised = unicodedata.normalize("NFKD", text or "")
    return "".join(char for char in normalised if char.isprintable() or char.isspace())


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        cleaned = _clean_whitespace(value)
        key = cleaned.lower()
        if cleaned and key not in seen:
            seen.add(key)
            output.append(cleaned)
    return output


def detect_business_category(text: str) -> list[str]:
    text_lower = (text or "").lower()
    detected = []
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(keyword.lower() in text_lower for keyword in keywords):
            detected.append(category)
    logger.info("Business category signals detected: %s", detected)
    return detected


def _make_flag(
    flag_type: str,
    severity: FlagSeverity,
    detail: str,
    source_doc: str,
    evidence: str,
    check_method: str,
    similarity_score: float | None = None,
) -> NLPFlag:
    return NLPFlag(
        flag_type=flag_type,
        severity=severity,
        detail=detail,
        source_doc=source_doc,
        evidence=_clean_whitespace(evidence)[:500],
        check_method=check_method,
        similarity_score=similarity_score,
    )


def _token_set_ratio(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    if fuzz:
        return fuzz.token_set_ratio(left, right) / 100
    left_tokens = set(re.findall(r"\w+", left.lower()))
    right_tokens = set(re.findall(r"\w+", right.lower()))
    if not left_tokens or not right_tokens:
        return SequenceMatcher(None, left.lower(), right.lower()).ratio()
    overlap = len(left_tokens & right_tokens) / len(left_tokens | right_tokens)
    seq = SequenceMatcher(None, left.lower(), right.lower()).ratio()
    return max(overlap, seq)


_SPACY_SIMILARITY_MODEL = None


def spacy_semantic_similarity(text1: str, text2: str) -> float:
    """
    Uses spaCy similarity as a second layer for address comparison.
    The small English model has limited vectors, so failures or unavailable
    vectors safely return 0.0 and the existing token/layer checks still apply.
    """
    global _SPACY_SIMILARITY_MODEL
    if not spacy or not text1 or not text2:
        return 0.0
    try:
        if _SPACY_SIMILARITY_MODEL is None:
            _SPACY_SIMILARITY_MODEL = spacy.load("en_core_web_sm")
        doc1 = _SPACY_SIMILARITY_MODEL(text1)
        doc2 = _SPACY_SIMILARITY_MODEL(text2)
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message=r"\[W007\].*")
            return float(doc1.similarity(doc2))
    except Exception as exc:
        logger.debug("spaCy semantic similarity unavailable: %s", exc)
        return 0.0


def check_case_distribution(text: str, doc_type: str) -> list[NLPFlag]:
    alpha_chars = [char for char in text if char.isalpha()]
    if len(alpha_chars) <= 50:
        return []
    upper_pct = sum(1 for char in alpha_chars if char.isupper()) / len(alpha_chars)
    logger.info("   [ANOMALY] Case distribution %s: uppercase %.0f%%", doc_type, upper_pct * 100)
    if upper_pct > 0.85:
        return [
            _make_flag(
                "all_caps_document",
                FlagSeverity.MEDIUM,
                f"{upper_pct:.0%} of text is uppercase in {doc_type}. Possible photocopy or manual type.",
                doc_type,
                f"upper_pct={upper_pct:.3f}",
                "case_distribution",
                upper_pct,
            )
        ]
    return []


def _context_snippet(text: str, phrase: str, window: int = 50) -> str:
    match = re.search(re.escape(phrase), text, flags=re.IGNORECASE)
    if not match:
        return phrase
    start = max(0, match.start() - window)
    end = min(len(text), match.end() + window)
    return _clean_whitespace(text[start:end])


def _remove_name_titles(name: str) -> str:
    tokens = re.findall(r"[A-Za-z]+", name or "")
    return " ".join(token for token in tokens if token.lower().rstrip(".") not in NAME_TITLES)


def _normalise_person_name(name: str) -> str:
    return _remove_name_titles(name).title().strip()


def _name_token_set(name: str) -> set[str]:
    return {
        token.lower()
        for token in re.findall(r"[A-Za-z]+", _remove_name_titles(name))
        if token.lower() not in NAME_TITLES
    }


def _parse_date(value: str | None) -> dt.date | None:
    if not value:
        return None
    cleaned = re.sub(r"(\d+)(st|nd|rd|th)", r"\1", value, flags=re.IGNORECASE)
    if date_parser:
        try:
            return date_parser.parse(cleaned, fuzzy=True, default=dt.datetime(1900, 1, 1)).date()
        except Exception:
            logger.debug("Could not parse date with dateutil: %s", value)
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d %B %Y", "%B %Y"):
        try:
            return dt.datetime.strptime(cleaned, fmt).date()
        except ValueError:
            continue
    return None


def _is_sequential_digits(value: str) -> bool:
    digits = re.sub(r"\D", "", value)
    if len(digits) < 6:
        return False
    ascending = "01234567890123456789"
    descending = "98765432109876543210"
    return digits in ascending or digits in descending or len(set(digits)) == 1


def extract_and_normalise(ocr_output: dict) -> dict:
    """
    Takes raw OCR output and returns per-document original text, lower-case
    normalised text, and OCR confidence metadata.
    """
    normalised_docs: dict[str, dict[str, Any]] = {}
    for key, payload in (ocr_output or {}).items():
        if isinstance(payload, str):
            payload = {"raw_text": payload, "doc_type": key, "confidence_score": 1.0}
        doc_type = payload.get("doc_type") or key
        raw_text = payload.get("raw_text") or ""
        confidence = float(payload.get("confidence_score") or 0.0)
        printable = _normalise_unicode(raw_text)
        original = _clean_lines(printable)
        normalised = _clean_whitespace(original).lower()
        normalised_docs[doc_type] = {
            "original": original,
            "normalised": normalised,
            "confidence": confidence,
            "doc_type": doc_type,
        }
        logger.info("   doc: %-15s | raw length: %s chars | confidence: %.2f", doc_type, len(raw_text), confidence)
    return normalised_docs


class NigerianDocumentFieldExtractor:
    """Regex extractor calibrated for Nigerian business documents."""

    RC_NUMBER_PATTERN = r"RC\s*(\d{5,7})"
    BVN_PATTERN = r"\b(\d{11})\b"
    NIN_PATTERN = r"\b(\d{11})\b"
    TIN_PATTERN = r"\b(\d{8}-\d{4})\b"
    NGN_AMOUNT_PATTERN = r"NGN\s*([\d,]+(?:\.\d{2})?)"
    PHONE_PATTERN = r"(?:\+?234|0)[789][01]\d{8}"
    DATE_PATTERN_1 = (
        r"\b(\d{1,2}(?:st|nd|rd|th)?\s+"
        r"(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4})\b"
    )
    DATE_PATTERN_2 = r"\b(\d{1,2}/\d{1,2}/\d{4})\b"
    DATE_PATTERN_3 = (
        r"\b((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4})\b"
    )
    ADDRESS_PATTERN = (
        r"\d+[\w\s]+(?:Street|St\.?|Avenue|Ave\.?|Road|Rd\.?|Close|Crescent|Cres\.?|"
        r"Drive|Dr\.?|Way|Lane|Boulevard|Blvd\.?)[\w\s,]*(?:Lagos|Abuja|Kano|"
        r"Port Harcourt|Ibadan|Enugu|Kaduna|Benin|Onitsha|Aba)(?: State|, Nigeria)?"
    )

    def extract_all_fields(self, text: str, doc_type: str) -> dict:
        fields = {
            "rc_numbers": [],
            "bvn": [],
            "nin": [],
            "tin": [],
            "amounts": [],
            "phones": [],
            "dates": [],
            "addresses": [],
            "company_names": [],
            "director_names": [],
            "business_category_signals": [],
        }

        patterns = {
            "rc_numbers": self.RC_NUMBER_PATTERN,
            "bvn": self.BVN_PATTERN,
            "nin": self.NIN_PATTERN,
            "tin": self.TIN_PATTERN,
            "amounts": self.NGN_AMOUNT_PATTERN,
            "phones": self.PHONE_PATTERN,
            "dates": "|".join([self.DATE_PATTERN_1, self.DATE_PATTERN_2, self.DATE_PATTERN_3]),
            "addresses": self.ADDRESS_PATTERN,
        }

        for field, pattern in patterns.items():
            for match in re.finditer(pattern, text, flags=re.IGNORECASE):
                value = next((group for group in match.groups() if group), match.group(0))
                if field == "amounts":
                    value = f"NGN {value}"
                if field == "rc_numbers":
                    value = match.group(0)
                fields[field].append(_clean_whitespace(value))
                logger.info("   Found %s: %s in %s", field, _clean_whitespace(value), doc_type)

        label_patterns = {
            "company_names": r"(?:Company Name|Account Name|Taxpayer Name):\s*([^\n\r]+)",
            "director_names": r"(?:Directors?|Company Secretary|Surname|First Name|Middle Name):\s*([^\n\r]+)",
            "addresses": r"(?:Registered Address|Service Address|Address):\s*([^\n\r]+)",
        }
        for field, pattern in label_patterns.items():
            for match in re.finditer(pattern, text, flags=re.IGNORECASE):
                value = _clean_whitespace(match.group(1))
                fields[field].append(value)
                logger.info("   Found %s: %s in %s", field, value, doc_type)

        if "directors_id" in doc_type:
            surname = re.search(r"Surname:\s*([A-Za-z]+)", text, flags=re.IGNORECASE)
            first = re.search(r"First Name:\s*([A-Za-z]+)", text, flags=re.IGNORECASE)
            middle = re.search(r"Middle Name:\s*([A-Za-z]+)", text, flags=re.IGNORECASE)
            parts = [match.group(1) for match in (surname, first, middle) if match]
            if parts:
                full_name = " ".join(parts).title()
                fields["director_names"].append(full_name)
                logger.info("   Found director_names: %s in %s", full_name, doc_type)

        for key, values in fields.items():
            fields[key] = _dedupe(values)
        fields["business_category_signals"] = detect_business_category(text)
        return fields

    def normalise_rc_number(self, rc: str) -> str:
        digits = re.sub(r"\D", "", rc or "")
        normalised = f"RC{digits}" if digits else ""
        logger.debug("RC normalisation: %s -> %s", rc, normalised)
        return normalised

    def normalise_company_name(self, name: str) -> str:
        cleaned = re.sub(r"\b(limited|ltd|plc|llc|inc|incorporated)\b", "", name or "", flags=re.IGNORECASE)
        cleaned = re.sub(r"[^A-Za-z0-9\s]", " ", cleaned)
        cleaned = re.sub(r"\bsupplies\b", "supply", cleaned, flags=re.IGNORECASE)
        normalised = _clean_whitespace(cleaned).lower()
        logger.debug("Company name normalisation: %s -> %s", name, normalised)
        return normalised


class TextPreprocessor:
    """Full preprocessing pipeline for Nigerian business document text."""

    CODE_PATTERN = re.compile(r"^(RC|NIN|BVN|NGN)", flags=re.IGNORECASE)

    def __init__(self):
        self.stemmer = PorterStemmer() if PorterStemmer else None
        self.field_extractor = NigerianDocumentFieldExtractor()
        self._spacy_model = self._load_spacy_model()
        self._stopwords = self._load_stopwords()

    def _load_stopwords(self) -> set[str]:
        fallback = {
            "a",
            "an",
            "and",
            "are",
            "as",
            "at",
            "be",
            "by",
            "for",
            "from",
            "in",
            "is",
            "of",
            "on",
            "or",
            "the",
            "to",
            "with",
        }
        if not stopwords:
            return fallback | NIGERIAN_DOC_STOPWORDS
        try:
            return set(stopwords.words("english")) | NIGERIAN_DOC_STOPWORDS
        except LookupError:
            logger.warning("NLTK stopwords corpus missing; using built-in fallback stopword list")
            return fallback | NIGERIAN_DOC_STOPWORDS

    def _load_spacy_model(self):
        if not spacy:
            logger.warning("spaCy is not installed; NER will use regex fallback")
            return None
        try:
            return spacy.load("en_core_web_sm")
        except Exception as exc:
            logger.warning("spaCy model en_core_web_sm unavailable; NER will use regex fallback: %s", exc)
            try:
                return spacy.blank("en")
            except Exception:
                return None

    def tokenize(self, text: str) -> list[str]:
        try:
            if nltk:
                tokens = nltk.word_tokenize(text)
            else:
                raise LookupError("NLTK unavailable")
        except Exception:
            tokens = re.findall(r"RC\s*\d+|NGN\s*[\d,]+(?:\.\d{2})?|\d+/\d+/\d+|[A-Za-z]+|\d+", text)
        logger.debug("Tokenized %s tokens: %s", len(tokens), tokens)
        return tokens

    def remove_stopwords(self, tokens: list[str]) -> list[str]:
        kept: list[str] = []
        removed: list[str] = []
        for token in tokens:
            token_key = token.lower().strip(".:,;")
            if self.CODE_PATTERN.match(token) or token.isdigit() or token.istitle():
                kept.append(token)
            elif token_key in self._stopwords:
                removed.append(token)
            else:
                kept.append(token)
        logger.debug("Removed stopwords (%s): %s", len(removed), removed)
        return kept

    def pos_tag(self, tokens: list[str]) -> list[tuple[str, str]]:
        try:
            if nltk:
                tagged = nltk.pos_tag(tokens)
            else:
                raise LookupError("NLTK unavailable")
        except Exception:
            tagged = []
            for token in tokens:
                if token.isdigit() or re.search(r"\d", token):
                    tag = "CD"
                elif token.istitle() or token.isupper():
                    tag = "NNP"
                else:
                    tag = "NN"
                tagged.append((token, tag))
        logger.debug("POS tags: %s", tagged)
        return tagged

    def stem_tokens(self, tokens: list[str], pos_tags: list[tuple[str, str]]) -> list[str]:
        if not self.stemmer:
            return tokens
        tags = dict(pos_tags)
        stemmed: list[str] = []
        changes: list[tuple[str, str]] = []
        for token in tokens:
            tag = tags.get(token, "")
            if tag in {"NNP", "NNPS", "CD"} or self.CODE_PATTERN.match(token):
                stemmed.append(token)
                continue
            if tag.startswith(("NN", "VB")) and re.match(r"^[A-Za-z]+$", token):
                new_token = self.stemmer.stem(token)
                stemmed.append(new_token)
                if new_token != token:
                    changes.append((token, new_token))
            else:
                stemmed.append(token)
        logger.debug("Stemmed tokens: %s", changes)
        return stemmed

    def build_tfidf_vectors(self, corpus: list[str]) -> tuple[Any, Any, list[str]]:
        if not TfidfVectorizer or not any(corpus):
            logger.warning("TF-IDF unavailable or empty corpus; cosine similarity will be skipped")
            return None, None, []
        vectorizer = TfidfVectorizer(ngram_range=(1, 2), min_df=1, max_features=500, analyzer="word")
        matrix = vectorizer.fit_transform(corpus)
        feature_names = list(vectorizer.get_feature_names_out())
        logger.info("   TF-IDF vocabulary size: %s", len(feature_names))
        for index, row in enumerate(matrix):
            dense = row.toarray()[0]
            top_indexes = dense.argsort()[-10:][::-1]
            top_terms = [feature_names[i] for i in top_indexes if dense[i] > 0]
            logger.info("   document %s top TF-IDF terms: %s", index + 1, top_terms)
        return vectorizer, matrix, feature_names

    def run_ner(self, text: str, doc_type: str) -> dict:
        entities = {"ORG": [], "PERSON": [], "GPE": [], "DATE": [], "MONEY": [], "CARDINAL": []}
        try:
            if self._spacy_model and "ner" in self._spacy_model.pipe_names:
                doc = self._spacy_model(text)
                for entity in doc.ents:
                    if entity.label_ in entities:
                        entities[entity.label_].append(entity.text)
            else:
                raise RuntimeError("spaCy NER model unavailable")
        except Exception as exc:
            logger.debug("NER fallback for %s: %s", doc_type, exc)

        regex_fields = self.field_extractor.extract_all_fields(text, doc_type)
        entities["ORG"].extend(regex_fields["company_names"])
        entities["PERSON"].extend(regex_fields["director_names"])
        entities["GPE"].extend(re.findall(r"\b(?:Lagos|Abuja|Kano|Ibadan|Enugu|Kaduna|Benin|Onitsha|Aba)\b(?: State)?", text))
        entities["DATE"].extend(regex_fields["dates"])
        entities["MONEY"].extend(regex_fields["amounts"])
        entities["CARDINAL"].extend(regex_fields["rc_numbers"] + regex_fields["bvn"] + regex_fields["tin"])

        for key in entities:
            if key == "PERSON":
                entities[key] = _dedupe([_normalise_person_name(value) for value in entities[key]])
            else:
                entities[key] = _dedupe(entities[key])
        logger.info(
            "   %-15s -> ORG: %s | PERSON: %s | GPE: %s | DATE: %s",
            doc_type,
            entities["ORG"],
            entities["PERSON"],
            entities["GPE"],
            entities["DATE"],
        )
        return entities


class ConsistencyChecker:
    """Compares extracted document fields against the vendor submission."""

    def __init__(self):
        self.extractor = NigerianDocumentFieldExtractor()

    def check_business_name_consistency(self, submission_name: str, doc_names: dict[str, str | list[str]]) -> CheckResult:
        logger.info("   [CHECK] Business name consistency uses token_set_ratio for name/order tolerance")
        if not doc_names:
            flag = _make_flag(
                "business_name_missing",
                FlagSeverity.HIGH,
                "Business name was not found in any submitted document.",
                "all_documents",
                submission_name,
                "token_set_ratio",
            )
            return CheckResult("business_name", False, flag.detail, [flag])

        normalised_submission = self.extractor.normalise_company_name(submission_name)
        worst_score = 1.0
        flags: list[NLPFlag] = []
        for doc_type, names in doc_names.items():
            values = names if isinstance(names, list) else [names]
            for doc_name in values:
                normalised_doc = self.extractor.normalise_company_name(doc_name)
                score = _token_set_ratio(normalised_submission, normalised_doc)
                worst_score = min(worst_score, score)
                if score >= 0.95:
                    verdict = "PASS"
                elif score >= 0.75:
                    verdict = "PASS minor variation"
                elif score >= 0.50:
                    verdict = "FLAG medium"
                    flags.append(
                        _make_flag(
                            "name_mismatch",
                            FlagSeverity.MEDIUM,
                            "Significant business name variation across documents.",
                            doc_type,
                            f"{submission_name} vs {doc_name}",
                            "token_set_ratio",
                            score,
                        )
                    )
                else:
                    verdict = "FLAG critical"
                    flags.append(
                        _make_flag(
                            "name_mismatch_critical",
                            FlagSeverity.CRITICAL,
                            "Business name does not match submitted documents.",
                            doc_type,
                            f"{submission_name} vs {doc_name}",
                            "token_set_ratio",
                            score,
                        )
                    )
                logger.info(
                    "   [CHECK] Business name vs %s: similarity %.3f -> %s (threshold: 0.75)",
                    doc_type,
                    score,
                    verdict,
                )
        return CheckResult("business_name", not any(flag.severity != FlagSeverity.INFO for flag in flags), "Business name checked", flags, worst_score)

    def check_rc_number_consistency(self, submitted_rc: str, doc_rcs: dict[str, str | list[str]]) -> CheckResult:
        logger.info("   [CHECK] RC number consistency uses exact_match after normalisation")
        submitted = self.extractor.normalise_rc_number(submitted_rc)
        found: dict[str, list[str]] = {}
        for doc_type, values in doc_rcs.items():
            raw_values = values if isinstance(values, list) else [values]
            found[doc_type] = [self.extractor.normalise_rc_number(value) for value in raw_values if value]

        all_found = [value for values in found.values() for value in values if value]
        if not all_found:
            flag = _make_flag(
                "rc_not_found",
                FlagSeverity.CRITICAL,
                "RC number not found in any document.",
                "all_documents",
                submitted_rc,
                "exact_match",
            )
            logger.info("   [CHECK] RC number: submitted %r vs docs [] -> FLAG critical", submitted)
            return CheckResult("rc_number", False, flag.detail, [flag])

        if len(set(all_found)) > 1:
            flag = _make_flag(
                "rc_conflict",
                FlagSeverity.CRITICAL,
                "Conflicting RC numbers were found across documents.",
                "multiple_documents",
                ", ".join(all_found),
                "exact_match",
            )
            logger.info("   [CHECK] RC number conflicts: %s -> FLAG critical", all_found)
            return CheckResult("rc_number", False, flag.detail, [flag])

        if submitted and all(value == submitted for value in all_found):
            logger.info("   [CHECK] RC number: submitted %r vs doc %r -> normalized match -> PASS", submitted, all_found[0])
            return CheckResult("rc_number", True, "RC number matched exactly")

        flag = _make_flag(
            "rc_mismatch",
            FlagSeverity.CRITICAL,
            "RC number mismatch between submission and document.",
            "cac_certificate",
            f"submitted={submitted}; found={all_found}",
            "exact_match",
        )
        logger.info("   [CHECK] RC number: submitted %r vs docs %s -> FLAG critical", submitted, all_found)
        return CheckResult("rc_number", False, flag.detail, [flag])

    def check_director_name_consistency(
        self,
        submission_director: str,
        cac_directors: list[str],
        id_name: str,
    ) -> CheckResult:
        logger.info("   [CHECK] Director names use token overlap after Nigerian name-order normalisation")
        submitted_tokens = _name_token_set(submission_director)
        candidates = [*cac_directors]
        if id_name:
            candidates.append(id_name)
        if not submitted_tokens or not candidates:
            flag = _make_flag(
                "director_name_missing",
                FlagSeverity.HIGH,
                "Director name was not found in the submitted documents.",
                "all_documents",
                submission_director,
                "token_overlap",
            )
            return CheckResult("director_name", False, flag.detail, [flag])

        best_overlap = 0
        best_candidate = ""
        for candidate in candidates:
            candidate_tokens = _name_token_set(candidate)
            overlap = len(submitted_tokens & candidate_tokens)
            best_overlap = max(best_overlap, overlap)
            best_candidate = candidate if overlap == best_overlap else best_candidate
            logger.info(
                "   [CHECK] Director: %s tokens=%s vs %s tokens=%s -> overlap %s",
                submission_director,
                sorted(submitted_tokens),
                candidate,
                sorted(candidate_tokens),
                overlap,
            )

        if best_overlap >= len(submitted_tokens):
            return CheckResult("director_name", True, "Director name matched across documents")
        if best_overlap >= 2:
            logger.info("   [CHECK] Director: reordered/partial middle-name match accepted -> PASS")
            return CheckResult("director_name", True, "Director name matched with middle-name tolerance", similarity_score=best_overlap)
        severity = FlagSeverity.HIGH if best_overlap == 1 else FlagSeverity.CRITICAL
        flag = _make_flag(
            "director_name_mismatch",
            severity,
            "Director name partial match only." if best_overlap == 1 else "Director name not found in documents.",
            "directors_id",
            f"{submission_director} vs {best_candidate}",
            "token_overlap",
            float(best_overlap),
        )
        return CheckResult("director_name", False, flag.detail, [flag], float(best_overlap))

    def check_director_cross_verification(
        self,
        submission_director: str,
        director_names_by_doc: dict[str, list[str]],
    ) -> CheckResult:
        submitted_tokens = _name_token_set(submission_director)
        if not submitted_tokens:
            return CheckResult("director_cross_verification", True, "No submitted director to cross-check")
        matching_docs: list[str] = []
        non_matching_docs: list[str] = []
        for doc_type, names in director_names_by_doc.items():
            doc_matched = any(len(submitted_tokens & _name_token_set(name)) >= min(2, len(submitted_tokens)) for name in names)
            if doc_matched:
                matching_docs.append(doc_type)
            else:
                non_matching_docs.append(doc_type)
        logger.info(
            "   [CHECK] Director cross-verification: matched=%s missing=%s",
            matching_docs,
            non_matching_docs,
        )
        if len(matching_docs) == 1:
            flag = _make_flag(
                "director_single_document_only",
                FlagSeverity.LOW,
                "Director identity confirmed by single document only - no cross-verification.",
                matching_docs[0],
                f"matched={matching_docs}; missing={non_matching_docs}",
                "director_cross_document_presence",
            )
            return CheckResult("director_cross_verification", False, flag.detail, [flag])
        return CheckResult("director_cross_verification", True, "Director identity cross-verified")

    def check_address_consistency(self, submission_address: str, doc_addresses: dict[str, str | list[str]]) -> CheckResult:
        logger.info("   [CHECK] Address consistency uses layered comparison: street number, street, area, state")
        business_docs = {
            key: value
            for key, value in doc_addresses.items()
            if key not in {"directors_id", "id_card", "national_id"}
        }
        if not business_docs:
            flag = _make_flag(
                "address_missing",
                FlagSeverity.HIGH,
                "No business address was found in submitted documents.",
                "all_documents",
                submission_address,
                "address_layer_match",
            )
            return CheckResult("address", False, flag.detail, [flag])

        flags: list[NLPFlag] = []
        best_layers = 0
        for doc_type, addresses in business_docs.items():
            values = addresses if isinstance(addresses, list) else [addresses]
            for address in values:
                layers = self._address_layer_score(submission_address, address)
                token_score = _token_set_ratio(self._normalise_address(submission_address), self._normalise_address(address))
                semantic_score = spacy_semantic_similarity(submission_address, address)
                winning_method = "spacy_semantic_similarity" if semantic_score > token_score else "token_set_ratio"
                combined_score = max(token_score, semantic_score)
                left_no = re.match(r"\s*(\d+)", self._normalise_address(submission_address))
                right_no = re.match(r"\s*(\d+)", self._normalise_address(address))
                street_number_match = bool(left_no and right_no and left_no.group(1) == right_no.group(1))
                if layers < 3 and combined_score >= 0.82 and street_number_match:
                    layers = 3
                logger.info(
                    "   [CHECK] Address semantic layer: token_set=%.3f spaCy=%.3f winner=%s",
                    token_score,
                    semantic_score,
                    winning_method,
                )
                best_layers = max(best_layers, layers)
                if layers >= 3:
                    verdict = "PASS" if layers == 4 else "PASS with INFO"
                elif layers == 2:
                    verdict = "FLAG medium"
                    flags.append(
                        _make_flag(
                            "partial_address_match",
                            FlagSeverity.MEDIUM,
                            "Partial address match between submission and document.",
                            doc_type,
                            f"{submission_address} vs {address}",
                            "address_layer_match",
                            layers / 4,
                        )
                    )
                else:
                    verdict = "FLAG high"
                    flags.append(
                        _make_flag(
                            "address_mismatch",
                            FlagSeverity.HIGH,
                            "Address inconsistency across documents.",
                            doc_type,
                            f"{submission_address} vs {address}",
                            "address_layer_match",
                            layers / 4,
                        )
                    )
                logger.info("   [CHECK] Address vs %s: %s/4 layers -> %s", doc_type, layers, verdict)
        return CheckResult("address", not flags, "Address checked", flags, best_layers / 4 if best_layers else 0.0)

    def _address_layer_score(self, left: str, right: str) -> int:
        left_norm = self._normalise_address(left)
        right_norm = self._normalise_address(right)
        left_no = re.match(r"\s*(\d+)", left_norm)
        right_no = re.match(r"\s*(\d+)", right_norm)
        street_number = bool(left_no and right_no and left_no.group(1) == right_no.group(1))
        street_name = _token_set_ratio(left_norm.split(",")[0], right_norm.split(",")[0]) >= 0.80
        area = _token_set_ratio(",".join(left_norm.split(",")[1:3]), ",".join(right_norm.split(",")[1:3])) >= 0.75
        state = self._state_token(left_norm) == self._state_token(right_norm)
        logger.info(
            "      layers -> street_no:%s street:%s area:%s state:%s",
            street_number,
            street_name,
            area,
            state,
        )
        return sum([street_number, street_name, area, state])

    def _normalise_address(self, value: str) -> str:
        value = (value or "").lower()
        replacements = {
            " st.": " street",
            " st,": " street,",
            " ave.": " avenue",
            " rd.": " road",
            " fct": " abuja",
            "lagos state": "lagos",
            "lagos, nigeria": "lagos",
        }
        for old, new in replacements.items():
            value = value.replace(old, new)
        return _clean_whitespace(value)

    def _state_token(self, value: str) -> str:
        if "lagos" in value:
            return "lagos"
        if "abuja" in value or "fct" in value:
            return "abuja"
        return value.split(",")[-1].strip() if "," in value else value.strip()

    def check_date_plausibility(
        self,
        incorporation_date: str | None,
        utility_bill_date: str | None,
        id_expiry_date: str | None = None,
        vendor_registration_date: str | dt.date | dt.datetime | None = None,
    ) -> CheckResult:
        logger.info("   [CHECK] Date plausibility uses parsed Python date objects")
        today = dt.datetime.now(dt.UTC).date()
        inc = _parse_date(incorporation_date)
        bill = _parse_date(utility_bill_date)
        expiry = _parse_date(id_expiry_date)
        if isinstance(vendor_registration_date, dt.datetime):
            registration_date = vendor_registration_date.date()
        elif isinstance(vendor_registration_date, dt.date):
            registration_date = vendor_registration_date
        elif vendor_registration_date:
            registration_date = _parse_date(str(vendor_registration_date))
        else:
            registration_date = today
        flags: list[NLPFlag] = []
        logger.info("   [CHECK] Parsed dates -> incorporation=%s utility_bill=%s id_expiry=%s", inc, bill, expiry)

        if inc and inc > today:
            flags.append(_make_flag("future_incorporation_date", FlagSeverity.CRITICAL, "Incorporation date is in the future.", "cac_certificate", incorporation_date or "", "date_parse"))
        if inc and (today - inc).days < 7:
            flags.append(_make_flag("incorporated_this_week", FlagSeverity.CRITICAL, "Business was incorporated this week.", "cac_certificate", incorporation_date or "", "date_parse"))
        elif inc and (today - inc).days < 30:
            flags.append(_make_flag("recent_incorporation", FlagSeverity.MEDIUM, "Business was incorporated very recently.", "cac_certificate", incorporation_date or "", "date_parse"))
        if inc and registration_date:
            gap_days = (registration_date - inc).days
            logger.info("   [CHECK] Registration-to-payment gap: %s days", gap_days)
            if 0 <= gap_days < 7 and not any(flag.flag_type == "incorporated_this_week" for flag in flags):
                flags.append(
                    _make_flag(
                        "new_business_payment_registration",
                        FlagSeverity.CRITICAL,
                        "Business incorporated within 7 days of payment registration.",
                        "cac_certificate",
                        f"incorporation={inc}; registration={registration_date}; gap_days={gap_days}",
                        "registration_gap",
                    )
                )
            elif 0 <= gap_days < 30 and not any(flag.flag_type == "recent_incorporation" for flag in flags):
                flags.append(
                    _make_flag(
                        "recent_business_payment_registration",
                        FlagSeverity.MEDIUM,
                        "Business incorporated within 30 days of payment registration.",
                        "cac_certificate",
                        f"incorporation={inc}; registration={registration_date}; gap_days={gap_days}",
                        "registration_gap",
                    )
                )

        if bill and (today - bill).days > 120:
            flags.append(_make_flag("stale_utility_bill", FlagSeverity.MEDIUM, "Utility bill is older than three months.", "utility_bill", utility_bill_date or "", "date_parse"))
        if inc and bill and bill < inc and re.search(r"\d{1,2}", utility_bill_date or ""):
            logger.info("   [CHECK] Utility bill predates incorporation, but month-level bills are treated as review signals")
        if expiry and expiry < today:
            flags.append(_make_flag("expired_id", FlagSeverity.MEDIUM, "ID document may be expired.", "directors_id", id_expiry_date or "", "date_parse"))

        return CheckResult("date_plausibility", not flags, "Dates checked", flags)

    def check_document_completeness(self, tier: str, submitted_doc_types: list[str]) -> CheckResult:
        requirements = {
            "tier1": {"directors_id"},
            "tier2": {"cac_certificate", "utility_bill", "directors_id"},
            "tier3": {"cac_certificate", "utility_bill", "directors_id", "cac_form_cac2", "cac_form_cac7", "memart"},
        }
        required = requirements.get(tier, requirements["tier2"])
        submitted = set(submitted_doc_types)
        missing = sorted(required - submitted)
        logger.info("   [CHECK] Completeness: tier=%s required=%s submitted=%s missing=%s", tier, sorted(required), sorted(submitted), missing)
        if not submitted:
            flag = _make_flag("no_documents", FlagSeverity.CRITICAL, "No documents submitted.", "all_documents", tier, "completeness")
            return CheckResult("document_completeness", False, flag.detail, [flag])
        if missing:
            flags = [
                _make_flag(
                    "missing_required_document",
                    FlagSeverity.HIGH,
                    f"Missing required document: {doc_type}",
                    doc_type,
                    ",".join(submitted_doc_types),
                    "completeness",
                )
                for doc_type in missing
            ]
            return CheckResult("document_completeness", False, "Missing required documents", flags)
        return CheckResult("document_completeness", True, "All required documents present")


class LinguisticAnomalyDetector:
    """Language-level red flag detector for forged or suspicious documents."""

    FRAUD_INDICATOR_PHRASES = [
        "as directed",
        "transfer immediately",
        "urgent payment",
        "commission fee",
        "processing fee",
        "clearance fee",
        "inheritance",
        "next of kin",
        "beneficiary account",
        "diplomatic courier",
        "security company",
        "central bank approval",
        "anti-terrorism clearance",
    ]

    TEMPLATE_INDICATOR_PHRASES = [
        "insert company name here",
        "sample document",
        "for illustration purposes",
        "this is a template",
        "[company name]",
        "[director name]",
        "lorem ipsum",
    ]

    def detect_template_language(self, text: str, doc_type: str) -> list[AnomalyFlag]:
        flags: list[AnomalyFlag] = []
        lowered = text.lower()
        for phrase in self.TEMPLATE_INDICATOR_PHRASES:
            logger.debug("Checking template phrase in %s: %s", doc_type, phrase)
            if phrase in lowered:
                flags.append(
                    _make_flag(
                        "template_language",
                        FlagSeverity.CRITICAL,
                        "Document contains template placeholder language.",
                        doc_type,
                        _context_snippet(text, phrase),
                        "keyword_scan",
                    )
                )
                logger.info("   [ANOMALY] Template phrase detected in %s: %r -> CRITICAL", doc_type, phrase)
        if not re.search(r"[A-Z][a-z]+\s+[A-Z][a-z]+|\d{4,}", text):
            flags.append(
                _make_flag(
                    "generic_document_language",
                    FlagSeverity.MEDIUM,
                    "Document text appears unusually generic.",
                    doc_type,
                    text[:200],
                    "tfidf_genericity",
                )
            )
        return flags

    def detect_fraud_phrases(self, text: str, doc_type: str) -> list[AnomalyFlag]:
        flags: list[AnomalyFlag] = []
        lowered = text.lower()
        for phrase in self.FRAUD_INDICATOR_PHRASES:
            logger.debug("Checking fraud phrase in %s: %s", doc_type, phrase)
            if phrase in lowered:
                snippet = _context_snippet(text, phrase)
                flags.append(
                    _make_flag(
                        "fraud_phrase",
                        FlagSeverity.CRITICAL,
                        "High-risk fraud phrase detected.",
                        doc_type,
                        snippet,
                        "keyword_scan",
                    )
                )
                logger.info("   [ANOMALY] Fraud phrase detected in %s: %r -> CRITICAL", doc_type, phrase)
        if not flags:
            logger.info("   [ANOMALY] No high-risk phrases detected in %s", doc_type)
        return flags

    def detect_copy_paste_signatures(self, doc_texts: dict[str, str]) -> list[AnomalyFlag]:
        flags: list[AnomalyFlag] = []
        shingles = {doc_type: self._shingles(text) for doc_type, text in doc_texts.items()}
        for doc_type, values in shingles.items():
            logger.info("   [ANOMALY] %s shingle count: %s", doc_type, len(values))
        for left, right in combinations(shingles.keys(), 2):
            left_set = shingles[left]
            right_set = shingles[right]
            if not left_set or not right_set:
                continue
            score = len(left_set & right_set) / len(left_set | right_set)
            logger.info("   [ANOMALY] Copy-paste Jaccard %s vs %s: %.3f", left, right, score)
            if score > 0.40:
                flags.append(
                    _make_flag(
                        "copy_paste_signature",
                        FlagSeverity.HIGH,
                        "Possible copy-paste between different document types.",
                        f"{left},{right}",
                        f"jaccard={score:.3f}",
                        "jaccard_shingles",
                        score,
                    )
                )
        return flags

    def _shingles(self, text: str, size: int = 5) -> set[tuple[str, ...]]:
        tokens = re.findall(r"\w+", text.lower())
        return {tuple(tokens[index : index + size]) for index in range(max(0, len(tokens) - size + 1))}

    def detect_numeric_anomalies(self, text: str, doc_type: str) -> list[AnomalyFlag]:
        flags: list[AnomalyFlag] = []
        amounts = re.findall(NigerianDocumentFieldExtractor.NGN_AMOUNT_PATTERN, text, flags=re.IGNORECASE)
        for raw_amount in amounts:
            amount_digits = int(re.sub(r"\D", "", raw_amount) or "0")
            logger.info("   [ANOMALY] Numeric amount in %s: NGN %s", doc_type, raw_amount)
            if amount_digits in {10_000, 100_000, 1_000_000}:
                flags.append(
                    _make_flag(
                        "round_share_capital",
                        FlagSeverity.LOW,
                        "Round share capital amount is common in shell-company registrations.",
                        doc_type,
                        f"NGN {raw_amount}",
                        "numeric_rule",
                    )
                )
        for number in re.findall(r"\b\d{11}\b", text):
            if _is_sequential_digits(number):
                severity = FlagSeverity.INFO if doc_type == "directors_id" else FlagSeverity.CRITICAL
                flags.append(
                    _make_flag(
                        "suspicious_identity_number",
                        severity,
                        "Suspicious NIN/BVN pattern detected.",
                        doc_type,
                        number,
                        "numeric_rule",
                    )
                )
                logger.info("   [ANOMALY] Sequential 11-digit number in %s -> %s", doc_type, severity.value.upper())
        return flags

    def score_ocr_confidence(self, confidence_scores: dict[str, float]) -> list[AnomalyFlag]:
        flags: list[AnomalyFlag] = []
        for doc_type, confidence in confidence_scores.items():
            if confidence >= 0.85:
                logger.info("   [ANOMALY] OCR confidence %s: %.2f -> PASS", doc_type, confidence)
                continue
            if confidence < 0.50:
                severity = FlagSeverity.HIGH
                detail = "Extremely low OCR confidence; document may not be authentic."
            elif confidence < 0.70:
                severity = FlagSeverity.MEDIUM
                detail = "Very low OCR confidence; possible image manipulation."
            else:
                severity = FlagSeverity.LOW
                detail = "Low OCR confidence; poor scan quality."
            flags.append(_make_flag("ocr_confidence", severity, detail, doc_type, f"{confidence:.2f}", "ocr_confidence"))
            logger.info("   [ANOMALY] OCR confidence %s: %.2f -> %s", doc_type, confidence, severity.value.upper())
        return flags


class DocumentAuthenticityClassifier:
    """Naive Bayes classifier trained on synthetic Nigerian document samples."""

    TRAINING_DATA = {
        "authentic": [
            "corporate affairs commission certificate incorporation company limited registered address directors share capital",
            "ekedc electricity distribution company account number service address bill date amount due",
            "federal republic nigeria national identity card surname firstname date birth gender address",
            "fidelity bank account statement opening balance closing balance transaction reference",
            "federal inland revenue service tax identification number taxpayer name assessment year",
        ],
        "suspicious": [
            "insert company name here sample document illustration purposes template director name",
            "transfer immediately commission fee processing fee clearance beneficiary account urgent",
            "congratulations you have been selected inheritance next kin diplomatic courier security",
            "rc number see attached please note company registration certificate valid",
            "lorem ipsum dolor sit amet consectetur adipiscing elit sed do eiusmod",
        ],
    }

    def __init__(self):
        self.pipeline = None
        self.labels: list[str] = []
        self.trained = False

    def train(self) -> None:
        if not all([CountVectorizer, TfidfTransformer, MultinomialNB, Pipeline]):
            logger.warning("sklearn unavailable; authenticity classifier disabled")
            return
        texts: list[str] = []
        labels: list[str] = []
        for label, samples in self.TRAINING_DATA.items():
            texts.extend(samples)
            labels.extend([label] * len(samples))
            logger.info("   Classifier training samples: %s=%s", label, len(samples))
        self.labels = sorted(set(labels))
        self.pipeline = Pipeline(
            [
                ("count", CountVectorizer(ngram_range=(1, 2), stop_words="english")),
                ("tfidf", TfidfTransformer()),
                ("nb", MultinomialNB(alpha=1.0)),
            ]
        )
        self.pipeline.fit(texts, labels)
        self.trained = True
        vectorizer = self.pipeline.named_steps["count"]
        feature_names = vectorizer.get_feature_names_out()
        logger.info("   Laplacian smoothing (alpha=1.0) applied - prevents zero-probability for unseen words")
        logger.info("   Classifier vocabulary size: %s", len(feature_names))
        self._log_top_features(feature_names)

    def _log_top_features(self, feature_names) -> None:
        if not self.pipeline:
            return
        classifier = self.pipeline.named_steps["nb"]
        for class_index, label in enumerate(classifier.classes_):
            top_indexes = classifier.feature_log_prob_[class_index].argsort()[-10:][::-1]
            terms = [feature_names[index] for index in top_indexes]
            logger.info("   Top classifier features for %s: %s", label, terms)

    def predict(self, text: str) -> ClassifierResult:
        if not self.trained:
            self.train()
        if not self.pipeline:
            return ClassifierResult(
                predicted_class="authentic",
                confidence=0.0,
                top_suspicious_features=[],
                smoothing_applied="laplacian_alpha=1.0",
            )
        probabilities = self.pipeline.predict_proba([text])[0]
        classes = list(self.pipeline.named_steps["nb"].classes_)
        best_index = int(probabilities.argmax())
        predicted = classes[best_index]
        confidence = float(probabilities[best_index])
        explanation = self.explain_prediction(text)
        top_features = [item["feature"] for item in explanation.get("top_suspicious_features", [])]
        logger.info("   Classifier verdict: %s (confidence: %.3f)", predicted, confidence)
        logger.info("   Top suspicious features: %s", top_features)
        if predicted == "suspicious" and confidence > 0.70:
            logger.info("   WARNING HIGH SUSPICION from classifier - top features: %s", top_features)
        return ClassifierResult(
            predicted_class=predicted,
            confidence=confidence,
            top_suspicious_features=top_features,
            smoothing_applied="laplacian_alpha=1.0",
        )

    def explain_prediction(self, text: str) -> dict:
        if not self.pipeline:
            return {"top_suspicious_features": []}
        vectorizer = self.pipeline.named_steps["count"]
        classifier = self.pipeline.named_steps["nb"]
        feature_names = vectorizer.get_feature_names_out()
        classes = list(classifier.classes_)
        if "suspicious" not in classes or "authentic" not in classes:
            return {"top_suspicious_features": []}
        suspicious_index = classes.index("suspicious")
        authentic_index = classes.index("authentic")
        doc_features = set(vectorizer.transform([text]).nonzero()[1])
        deltas = []
        for index in doc_features:
            delta = classifier.feature_log_prob_[suspicious_index][index] - classifier.feature_log_prob_[authentic_index][index]
            deltas.append((feature_names[index], float(delta)))
        deltas.sort(key=lambda item: item[1], reverse=True)
        top = [{"feature": feature, "delta": round(delta, 4)} for feature, delta in deltas[:5]]
        logger.info("   Explanation: words pushing toward SUSPICIOUS: %s", top)
        return {"top_suspicious_features": top}


async def run_nlp_pipeline(ocr_output: dict, vendor_submission: dict) -> NLPResult:
    """Main NLP pipeline entry point."""
    start = time.perf_counter()
    vendor_name = vendor_submission.get("business_name", "unknown vendor")
    logger.info("▶ PIPELINE START — vendor: %s | docs: %s", vendor_name, len(ocr_output or {}))

    logger.info("── STEP 1/7: Text Extraction")
    docs = extract_and_normalise(ocr_output)

    logger.info("── STEP 2/7: Preprocessing")
    preprocessor = TextPreprocessor()
    processed_docs: dict[str, dict[str, Any]] = {}
    for doc_type, data in docs.items():
        tokens = preprocessor.tokenize(data["original"])
        filtered = preprocessor.remove_stopwords(tokens)
        tags = preprocessor.pos_tag(filtered)
        stemmed = preprocessor.stem_tokens(filtered, tags)
        processed_docs[doc_type] = {"tokens": tokens, "filtered": filtered, "pos_tags": tags, "stemmed": stemmed}
        logger.info(
            "   %-15s → tokenized: %s tokens | after stopword removal: %s | after stemming: %s",
            doc_type,
            len(tokens),
            len(filtered),
            len(stemmed),
        )
    preprocessor.build_tfidf_vectors([data["normalised"] for data in docs.values()])

    logger.info("── STEP 3/7: Named Entity Recognition")
    entities_by_doc = {doc_type: preprocessor.run_ner(data["original"], doc_type) for doc_type, data in docs.items()}
    category_signals = detect_business_category(" ".join(data["original"] for data in docs.values()))

    logger.info("── STEP 4/7: Field Extraction (regex + NER hybrid)")
    extractor = NigerianDocumentFieldExtractor()
    fields_by_doc = {doc_type: extractor.extract_all_fields(data["original"], doc_type) for doc_type, data in docs.items()}
    extracted_fields = _aggregate_fields(fields_by_doc, entities_by_doc)
    extracted_fields["business_category_signals"] = _dedupe(
        [*extracted_fields.get("business_category_signals", []), *category_signals]
    )
    logger.info("   RC numbers found     → %s", extracted_fields["rc_numbers"])
    logger.info("   Company names found  → %s", extracted_fields["company_names"])
    logger.info("   Director names found → %s", extracted_fields["director_names"])
    logger.info("   Addresses found      → %s", extracted_fields["addresses"])
    logger.info("   Dates found          → %s", extracted_fields["dates"])

    logger.info("── STEP 5/7: Consistency Checks")
    checker = ConsistencyChecker()
    check_results = [
        checker.check_business_name_consistency(vendor_submission.get("business_name", ""), _field_map(fields_by_doc, "company_names")),
        checker.check_rc_number_consistency(vendor_submission.get("rc_number", ""), _field_map(fields_by_doc, "rc_numbers")),
        checker.check_director_name_consistency(
            vendor_submission.get("director_name", ""),
            fields_by_doc.get("cac_certificate", {}).get("director_names", []),
            " ".join(fields_by_doc.get("directors_id", {}).get("director_names", [])[:1]),
        ),
        checker.check_director_cross_verification(
            vendor_submission.get("director_name", ""),
            _field_map(fields_by_doc, "director_names"),
        ),
        checker.check_address_consistency(vendor_submission.get("address", ""), _field_map(fields_by_doc, "addresses")),
        checker.check_date_plausibility(
            _first(fields_by_doc.get("cac_certificate", {}).get("dates", [])),
            _first(fields_by_doc.get("utility_bill", {}).get("dates", [])),
            None,
            vendor_submission.get("created_at") or vendor_submission.get("registration_date"),
        ),
        checker.check_document_completeness(vendor_submission.get("tier", "tier2"), list(docs.keys())),
    ]

    logger.info("── STEP 6/7: Linguistic Anomaly Detection")
    anomaly_detector = LinguisticAnomalyDetector()
    flags: list[NLPFlag] = []
    for result in check_results:
        flags.extend(result.flags)
    for doc_type, data in docs.items():
        logger.info("   [ANOMALY] Scanning %s", doc_type)
        flags.extend(anomaly_detector.detect_template_language(data["original"], doc_type))
        flags.extend(anomaly_detector.detect_fraud_phrases(data["original"], doc_type))
        flags.extend(anomaly_detector.detect_numeric_anomalies(data["original"], doc_type))
        flags.extend(check_case_distribution(data["original"], doc_type))
    flags.extend(anomaly_detector.detect_copy_paste_signatures({doc_type: data["normalised"] for doc_type, data in docs.items()}))
    flags.extend(anomaly_detector.score_ocr_confidence({doc_type: data["confidence"] for doc_type, data in docs.items()}))

    logger.info("── STEP 7/7: Scoring")
    classifier = DocumentAuthenticityClassifier()
    classifier.train()
    classifier_result = classifier.predict(" ".join(data["normalised"] for data in docs.values()))
    if (
        classifier_result.predicted_class == "suspicious"
        and classifier_result.confidence > 0.80
        and not any(flag.severity in {FlagSeverity.CRITICAL, FlagSeverity.HIGH} for flag in flags)
    ):
        flags.append(
            _make_flag(
                "classifier_linguistic_pattern",
                FlagSeverity.MEDIUM,
                "Statistical classifier flagged suspicious linguistic patterns.",
                "all_documents",
                ", ".join(classifier_result.top_suspicious_features),
                "classifier",
                classifier_result.confidence,
            )
        )

    score = _score_flags(flags)
    severity_counts = {severity.value: sum(1 for flag in flags if flag.severity == severity) for severity in FlagSeverity}
    logger.info("   Base score: 100")
    logger.info("   Deductions: %s", _deduction_summary(flags))
    logger.info("   Final NLP score: %s / 100", score)
    logger.info(
        "   Flags generated: %s low | %s medium | %s high | %s critical",
        severity_counts["low"],
        severity_counts["medium"],
        severity_counts["high"],
        severity_counts["critical"],
    )

    elapsed_ms = int((time.perf_counter() - start) * 1000)
    checks_passed = sum(result.checks_passed for result in check_results)
    checks_failed = sum(result.checks_failed for result in check_results)
    summary = _summary_for(score, flags, len(docs))
    verdict = "CLEAN" if score >= 80 else "REVIEW" if score >= 45 else "BLOCK"
    logger.info("✓ PIPELINE COMPLETE — %.1fs | score: %s | verdict contribution: %s", elapsed_ms / 1000, score, verdict)

    return NLPResult(
        nlp_score=score,
        flags=flags,
        extracted_fields={
            **extracted_fields,
            "by_doc": fields_by_doc,
            "entities_by_doc": entities_by_doc,
            "preprocessing": processed_docs,
        },
        classifier_result=classifier_result,
        processing_time_ms=elapsed_ms,
        summary=summary,
        documents_processed=len(docs),
        checks_passed=checks_passed,
        checks_failed=checks_failed,
    )


def _field_map(fields_by_doc: dict[str, dict], field_name: str) -> dict[str, list[str]]:
    return {doc_type: values.get(field_name, []) for doc_type, values in fields_by_doc.items() if values.get(field_name)}


def _aggregate_fields(fields_by_doc: dict[str, dict], entities_by_doc: dict[str, dict]) -> dict[str, list[str]]:
    aggregate = {
        "rc_numbers": [],
        "company_names": [],
        "director_names": [],
        "addresses": [],
        "dates": [],
        "amounts": [],
        "phones": [],
        "locations": [],
        "business_category_signals": [],
    }
    for fields in fields_by_doc.values():
        aggregate["rc_numbers"].extend(fields.get("rc_numbers", []))
        aggregate["company_names"].extend(fields.get("company_names", []))
        aggregate["director_names"].extend(fields.get("director_names", []))
        aggregate["addresses"].extend(fields.get("addresses", []))
        aggregate["dates"].extend(fields.get("dates", []))
        aggregate["amounts"].extend(fields.get("amounts", []))
        aggregate["phones"].extend(fields.get("phones", []))
        aggregate["business_category_signals"].extend(fields.get("business_category_signals", []))
    for entities in entities_by_doc.values():
        aggregate["company_names"].extend(entities.get("ORG", []))
        aggregate["director_names"].extend(entities.get("PERSON", []))
        aggregate["locations"].extend(entities.get("GPE", []))
        aggregate["dates"].extend(entities.get("DATE", []))
        aggregate["amounts"].extend(entities.get("MONEY", []))
    return {key: _dedupe(values) for key, values in aggregate.items()}


def _first(values: list[str]) -> str | None:
    return values[0] if values else None


def _score_flags(flags: list[NLPFlag]) -> int:
    score = 100
    for flag in flags:
        score -= SEVERITY_DEDUCTIONS[flag.severity]
    if any(flag.severity == FlagSeverity.CRITICAL for flag in flags):
        score = min(score, 35)
    if sum(1 for flag in flags if flag.severity == FlagSeverity.HIGH) >= 2:
        score = min(score, 55)
    return max(0, min(100, score))


def _deduction_summary(flags: list[NLPFlag]) -> str:
    parts = []
    for flag in flags:
        deduction = SEVERITY_DEDUCTIONS[flag.severity]
        if deduction:
            parts.append(f"{flag.flag_type}(-{deduction})")
    return " ".join(parts) or "none"


def _summary_for(score: int, flags: list[NLPFlag], documents_processed: int) -> str:
    critical = sum(1 for flag in flags if flag.severity == FlagSeverity.CRITICAL)
    high = sum(1 for flag in flags if flag.severity == FlagSeverity.HIGH)
    if critical:
        return f"NLP reviewed {documents_processed} documents and found {critical} critical fraud signal(s)."
    if high:
        return f"NLP reviewed {documents_processed} documents and found {high} high-risk consistency issue(s)."
    if score >= 80:
        return f"NLP reviewed {documents_processed} documents with mostly consistent business evidence."
    return f"NLP reviewed {documents_processed} documents and recommends manual compliance review."


def _legacy_severity(severity: FlagSeverity) -> int:
    return {
        FlagSeverity.INFO: 0,
        FlagSeverity.LOW: 1,
        FlagSeverity.MEDIUM: 2,
        FlagSeverity.HIGH: 3,
        FlagSeverity.CRITICAL: 3,
    }[severity]


def check_consistency(vendor: Vendor, extracted_text: str) -> tuple[list[dict], str]:
    """
    Compatibility adapter for the existing synchronous scorer.
    The full async pipeline is exposed as run_nlp_pipeline().
    """
    ocr_output = {
        "combined_documents": {
            "raw_text": extracted_text or "",
            "doc_type": "combined_documents",
            "confidence_score": 1.0 if extracted_text else 0.0,
        }
    }
    vendor_submission = {
        "business_name": vendor.business_name,
        "rc_number": vendor.rc_number or "",
        "director_name": vendor.director_name or "",
        "address": vendor.address,
        "bvn": vendor.bvn,
        "nin": vendor.nin,
        "tier": vendor.tier,
        "business_category": vendor.business_category or "",
        "website_url": vendor.website_url or "",
        "expected_monthly_volume": vendor.expected_monthly_volume or 0,
    }

    if not extracted_text:
        flag = _make_flag(
            "no_document_text",
            FlagSeverity.MEDIUM,
            "No readable document text was available for NLP checks.",
            "combined_documents",
            "",
            "ocr_text_presence",
        )
        return [_flag_to_legacy(flag)], flag.detail

    extractor = NigerianDocumentFieldExtractor()
    fields = extractor.extract_all_fields(extracted_text, "combined_documents")
    checker = ConsistencyChecker()
    results = [
        checker.check_business_name_consistency(vendor_submission["business_name"], {"combined_documents": fields.get("company_names", []) or [extracted_text[:120]]}),
        checker.check_address_consistency(vendor_submission["address"], {"combined_documents": fields.get("addresses", []) or [extracted_text[:120]]}),
    ]
    flags = [flag for result in results for flag in result.flags]
    if not flags:
        return [], "NLP consistency checks found no major text mismatch."
    return [_flag_to_legacy(flag) for flag in flags], " ".join(flag.detail for flag in flags)


def _flag_to_legacy(flag: NLPFlag) -> dict:
    return {
        "code": flag.flag_type.upper(),
        "title": flag.flag_type.replace("_", " ").title(),
        "description": flag.detail,
        "severity": _legacy_severity(flag.severity),
        "source": "nlp",
    }
