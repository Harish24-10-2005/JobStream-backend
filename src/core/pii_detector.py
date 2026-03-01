"""
PII Detector — Personal Identifiable Information Detection & Redaction

Detects and optionally redacts PII from text before sending to LLMs
or storing in logs. Essential for GDPR compliance and data protection.

Supported PII types:
  - Email addresses
  - Phone numbers (US/international)
  - Social Security Numbers
  - Credit card numbers (Luhn validation)
  - IP addresses
  - Physical addresses (basic)
  - Dates of birth patterns

Usage:
    from src.core.pii_detector import PIIDetector

    detector = PIIDetector()
    result = detector.detect("Email me at john@example.com")
    redacted = detector.redact("SSN: 123-45-6789")
    # → "SSN: [REDACTED_SSN]"
"""

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class PIIType(str, Enum):
	EMAIL = 'email'
	PHONE = 'phone'
	SSN = 'ssn'
	CREDIT_CARD = 'credit_card'
	IP_ADDRESS = 'ip_address'
	DATE_OF_BIRTH = 'date_of_birth'
	ADDRESS = 'address'


@dataclass
class PIIMatch:
	"""A single PII detection match."""

	pii_type: PIIType
	value: str
	start: int
	end: int
	confidence: float  # 0.0 to 1.0


@dataclass
class PIIDetectionResult:
	"""Result from PII detection scan."""

	has_pii: bool
	matches: List[PIIMatch] = field(default_factory=list)
	redacted_text: Optional[str] = None
	pii_types_found: List[PIIType] = field(default_factory=list)

	@property
	def count(self) -> int:
		return len(self.matches)


class PIIDetector:
	"""
	Detects and redacts PII from text.

	Uses regex patterns with confidence scoring to identify
	various types of personally identifiable information.
	"""

	# PII Regex patterns with confidence levels
	PATTERNS: Dict[PIIType, List[tuple]] = {
		PIIType.EMAIL: [
			(re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'), 0.95),
		],
		PIIType.PHONE: [
			# US formats
			(re.compile(r'\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b'), 0.85),
			# International
			(re.compile(r'\b\+\d{1,3}[-.\s]?\d{4,14}\b'), 0.80),
		],
		PIIType.SSN: [
			(re.compile(r'\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b'), 0.90),
		],
		PIIType.CREDIT_CARD: [
			# Visa, MC, Amex, Discover patterns
			(re.compile(r'\b(?:4\d{3}|5[1-5]\d{2}|3[47]\d{2}|6(?:011|5\d{2}))[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b'), 0.90),
		],
		PIIType.IP_ADDRESS: [
			(re.compile(r'\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\b'), 0.85),
		],
		PIIType.DATE_OF_BIRTH: [
			# Explicit DOB markers
			(re.compile(r'(?:dob|date\s+of\s+birth|born\s+on)[\s:]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})', re.IGNORECASE), 0.90),
			(re.compile(r'(?:dob|date\s+of\s+birth|born\s+on)[\s:]*(\w+\s+\d{1,2},?\s+\d{4})', re.IGNORECASE), 0.90),
		],
		PIIType.ADDRESS: [
			# Street address patterns
			(
				re.compile(
					r'\b\d{1,5}\s+\w+(?:\s+\w+)*\s+(?:st|street|ave|avenue|blvd|boulevard|dr|drive|rd|road|ln|lane|ct|court|way|pl|place)\b',
					re.IGNORECASE,
				),
				0.70,
			),
		],
	}

	# Redaction labels
	REDACTION_LABELS: Dict[PIIType, str] = {
		PIIType.EMAIL: '[REDACTED_EMAIL]',
		PIIType.PHONE: '[REDACTED_PHONE]',
		PIIType.SSN: '[REDACTED_SSN]',
		PIIType.CREDIT_CARD: '[REDACTED_CC]',
		PIIType.IP_ADDRESS: '[REDACTED_IP]',
		PIIType.DATE_OF_BIRTH: '[REDACTED_DOB]',
		PIIType.ADDRESS: '[REDACTED_ADDRESS]',
	}

	def __init__(
		self,
		types_to_detect: Optional[List[PIIType]] = None,
		min_confidence: float = 0.7,
	):
		"""
		Args:
		    types_to_detect: Which PII types to scan for. None = all types.
		    min_confidence: Minimum confidence threshold for matches (0.0-1.0).
		"""
		self.types_to_detect = types_to_detect or list(PIIType)
		self.min_confidence = min_confidence

	def detect(self, text: str) -> PIIDetectionResult:
		"""
		Scan text for PII without redacting.

		Returns PIIDetectionResult with all matches found.
		"""
		if not text:
			return PIIDetectionResult(has_pii=False)

		matches: List[PIIMatch] = []

		for pii_type in self.types_to_detect:
			patterns = self.PATTERNS.get(pii_type, [])
			for pattern, confidence in patterns:
				if confidence < self.min_confidence:
					continue

				for match in pattern.finditer(text):
					value = match.group(0)

					# Additional validation for credit cards (Luhn check)
					if pii_type == PIIType.CREDIT_CARD and not self._luhn_check(value):
						continue

					# Skip SSN false positives (e.g., dates)
					if pii_type == PIIType.SSN and self._is_likely_date(value):
						continue

					matches.append(
						PIIMatch(
							pii_type=pii_type,
							value=value,
							start=match.start(),
							end=match.end(),
							confidence=confidence,
						)
					)

		pii_types_found = list(set(m.pii_type for m in matches))

		return PIIDetectionResult(
			has_pii=bool(matches),
			matches=matches,
			pii_types_found=pii_types_found,
		)

	def redact(self, text: str) -> str:
		"""
		Detect PII and replace with redaction labels.

		Returns the redacted text string.
		"""
		if not text:
			return text

		result = self.detect(text)
		if not result.has_pii:
			return text

		# Sort matches by position (reverse) to avoid index shifting
		sorted_matches = sorted(result.matches, key=lambda m: m.start, reverse=True)

		redacted = text
		for match in sorted_matches:
			label = self.REDACTION_LABELS.get(match.pii_type, '[REDACTED]')
			redacted = redacted[: match.start] + label + redacted[match.end :]

		return redacted

	def detect_and_redact(self, text: str) -> PIIDetectionResult:
		"""
		Detect PII and return result with redacted text.
		"""
		result = self.detect(text)
		result.redacted_text = self.redact(text) if result.has_pii else text
		return result

	@staticmethod
	def _luhn_check(card_number: str) -> bool:
		"""Validate credit card number using Luhn algorithm."""
		digits = re.sub(r'[\s-]', '', card_number)
		if not digits.isdigit() or len(digits) < 13:
			return False

		total = 0
		reverse = digits[::-1]
		for i, d in enumerate(reverse):
			n = int(d)
			if i % 2 == 1:
				n *= 2
				if n > 9:
					n -= 9
			total += n
		return total % 10 == 0

	@staticmethod
	def _is_likely_date(value: str) -> bool:
		"""Check if a potential SSN is actually a date format."""
		digits = re.sub(r'[-\s]', '', value)
		if len(digits) != 9:
			return False
		# Common date-like SSNs (month 01-12, day 01-31)
		first_three = int(digits[:3])
		middle_two = int(digits[3:5])
		if first_three <= 12 and middle_two <= 31:
			return True
		return False


# ─── Convenience instances ──────────────────────────────────────

# Default detector for general use
pii_detector = PIIDetector()

# Strict detector for logging (catches more)
strict_pii_detector = PIIDetector(min_confidence=0.5)
