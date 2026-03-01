"""
AI Guardrails — Input/Output Safety for Production AI Systems

Provides:
  - Prompt injection detection (pattern-based + heuristic)
  - Output schema validation (ensures agents return valid JSON)
  - Content safety filtering (profanity/toxicity for chat)
  - Configurable guardrail pipeline with chain-of-responsibility pattern

Usage:
    from src.core.guardrails import GuardrailPipeline, InputSanitizer, OutputValidator

    pipeline = GuardrailPipeline([
        InputSanitizer(),
        PromptInjectionDetector(),
        OutputValidator(schema=MySchema),
    ])

    clean_input = await pipeline.run_input("user text")
    validated_output = await pipeline.run_output(raw_llm_output)
"""

import json
import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Type

from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)


# ─── Guardrail Result ───────────────────────────────────────────


class GuardrailAction(str, Enum):
	PASS = 'pass'
	WARN = 'warn'
	BLOCK = 'block'
	SANITIZE = 'sanitize'


@dataclass
class GuardrailResult:
	"""Result from a single guardrail check."""

	action: GuardrailAction
	guardrail_name: str
	original_text: str
	processed_text: str
	warnings: List[str] = field(default_factory=list)
	blocked_reason: Optional[str] = None
	metadata: Dict[str, Any] = field(default_factory=dict)

	@property
	def is_blocked(self) -> bool:
		return self.action == GuardrailAction.BLOCK

	@property
	def is_warning(self) -> bool:
		return self.action == GuardrailAction.WARN


# ─── Base Guardrail ─────────────────────────────────────────────


class BaseGuardrail(ABC):
	"""Abstract base class for all guardrails."""

	name: str = 'base_guardrail'

	@abstractmethod
	def check_sync(self, text: str, context: Dict[str, Any] = None) -> GuardrailResult:
		"""Run the guardrail check synchronously."""
		pass

	async def check(self, text: str, context: Dict[str, Any] = None) -> GuardrailResult:
		"""Run the guardrail check asynchronously (defaults to sync implementation)."""
		return self.check_sync(text, context)


# ─── Prompt Injection Detector ──────────────────────────────────


class PromptInjectionDetector(BaseGuardrail):
	"""
	Detects prompt injection attempts using pattern matching and heuristics.

	Checks for:
	  - System prompt override attempts
	  - Role-play injection ("ignore previous instructions")
	  - Encoding-based attacks (base64 instructions)
	  - Delimiter injection
	"""

	name = 'prompt_injection_detector'

	# High-risk patterns that indicate injection attempts
	INJECTION_PATTERNS = [
		# Direct instruction overrides
		r'ignore\s+(all\s+)?(previous|prior|above)\s+(instructions?|prompts?|rules?)',
		r'disregard\s+(all\s+)?(previous|prior|above)\s+(instructions?|prompts?)',
		r'forget\s+(all\s+)?(previous|prior|above)\s+(instructions?|prompts?)',
		r'override\s+(system|safety)\s+(prompt|instructions?|rules?)',
		# Role-play injection
		r'you\s+are\s+now\s+(a|an)\s+\w+\s+that',
		r'act\s+as\s+(if|though)\s+you',
		r'pretend\s+(you\s+are|to\s+be)\s+(a|an)?\s*(?:different|new)',
		r'from\s+now\s+on[\s,]+you\s+(will|should|must)',
		# System prompt extraction
		r'(show|reveal|display|print|output)\s+(your\s+)?(system\s+)?(prompt|instructions)',
		r'what\s+(are|is)\s+your\s+(system\s+)?(prompt|instructions|rules)',
		r'repeat\s+(the\s+)?(text|words|prompt)\s+above',
		# Delimiter injection
		r'```\s*(system|assistant|user)\s*\n',
		r'<\|?(system|assistant|user|im_start|im_end)\|?>',
		# Jailbreak patterns
		r'(DAN|DUDE|STAN|KEVIN)\s+mode',
		r'developer\s+mode\s+(enabled|activated|on)',
	]

	def __init__(self, sensitivity: str = 'medium'):
		"""
		Args:
		    sensitivity: "low" (only obvious attacks), "medium" (balanced), "high" (aggressive)
		"""
		self.sensitivity = sensitivity
		self._compiled_patterns = [re.compile(p, re.IGNORECASE | re.MULTILINE) for p in self.INJECTION_PATTERNS]

	def check_sync(self, text: str, context: Dict[str, Any] = None) -> GuardrailResult:
		detected_patterns = []

		for pattern in self._compiled_patterns:
			matches = pattern.findall(text)
			if matches:
				detected_patterns.append(pattern.pattern)

		# Heuristic checks
		warnings = []

		# Unusually long input (potential payload)
		if len(text) > 5000:
			warnings.append(f'Unusually long input: {len(text)} chars')

		# High ratio of special characters
		special_ratio = len(re.findall(r'[^a-zA-Z0-9\s.,!?\'"-]', text)) / max(len(text), 1)
		if special_ratio > 0.3:
			warnings.append(f'High special character ratio: {special_ratio:.2f}')

		# Base64-encoded content detection
		base64_pattern = re.compile(r'[A-Za-z0-9+/]{50,}={0,2}')
		if base64_pattern.search(text):
			warnings.append('Possible base64-encoded content detected')

		# Determine action
		if detected_patterns:
			logger.warning(
				f'[Guardrail] Prompt injection detected: {len(detected_patterns)} pattern(s)',
				extra={'patterns': detected_patterns[:3]},
			)
			return GuardrailResult(
				action=GuardrailAction.BLOCK,
				guardrail_name=self.name,
				original_text=text,
				processed_text='',
				blocked_reason=f'Prompt injection detected: {len(detected_patterns)} suspicious pattern(s)',
				metadata={'patterns_matched': len(detected_patterns)},
			)

		if warnings and self.sensitivity == 'high':
			return GuardrailResult(
				action=GuardrailAction.WARN,
				guardrail_name=self.name,
				original_text=text,
				processed_text=text,
				warnings=warnings,
			)

		return GuardrailResult(
			action=GuardrailAction.PASS,
			guardrail_name=self.name,
			original_text=text,
			processed_text=text,
		)


# ─── Input Sanitizer ───────────────────────────────────────────


class InputSanitizer(BaseGuardrail):
	"""
	Sanitizes user input to prevent XSS and injection attacks.
	Strips dangerous HTML/script tags while preserving content.
	"""

	name = 'input_sanitizer'

	# Tags and patterns to strip
	DANGEROUS_PATTERNS = [
		(re.compile(r'<script[^>]*>.*?</script>', re.IGNORECASE | re.DOTALL), ''),
		(re.compile(r'<iframe[^>]*>.*?</iframe>', re.IGNORECASE | re.DOTALL), ''),
		(re.compile(r'<embed[^>]*/?>', re.IGNORECASE), ''),
		(re.compile(r'<object[^>]*>.*?</object>', re.IGNORECASE | re.DOTALL), ''),
		(re.compile(r'javascript:', re.IGNORECASE), ''),
		(re.compile(r'on\w+\s*=', re.IGNORECASE), ''),
		(re.compile(r'data:text/html', re.IGNORECASE), ''),
	]

	def check_sync(self, text: str, context: Dict[str, Any] = None) -> GuardrailResult:
		sanitized = text
		sanitizations = []

		for pattern, replacement in self.DANGEROUS_PATTERNS:
			if pattern.search(sanitized):
				sanitizations.append(f'Removed: {pattern.pattern[:30]}...')
				sanitized = pattern.sub(replacement, sanitized)

		if sanitizations:
			logger.info(f'[Guardrail] Input sanitized: {len(sanitizations)} pattern(s) removed')
			return GuardrailResult(
				action=GuardrailAction.SANITIZE,
				guardrail_name=self.name,
				original_text=text,
				processed_text=sanitized,
				warnings=sanitizations,
				metadata={'sanitizations': len(sanitizations)},
			)

		return GuardrailResult(
			action=GuardrailAction.PASS,
			guardrail_name=self.name,
			original_text=text,
			processed_text=text,
		)


# ─── Output Validator ──────────────────────────────────────────


class OutputValidator(BaseGuardrail):
	"""
	Validates LLM output against a Pydantic schema.
	Attempts JSON repair for common LLM output issues.
	"""

	name = 'output_validator'

	def __init__(self, schema: Type[BaseModel] = None):
		self.schema = schema

	def check_sync(self, text: str, context: Dict[str, Any] = None) -> GuardrailResult:
		if not self.schema:
			return GuardrailResult(
				action=GuardrailAction.PASS,
				guardrail_name=self.name,
				original_text=text,
				processed_text=text,
			)

		# Try to extract JSON from text
		json_text = self._extract_json(text)

		try:
			data = json.loads(json_text)
			validated = self.schema(**data)
			return GuardrailResult(
				action=GuardrailAction.PASS,
				guardrail_name=self.name,
				original_text=text,
				processed_text=validated.model_dump_json(),
			)
		except (json.JSONDecodeError, ValidationError) as e:
			# Try JSON repair
			repaired = self._repair_json(json_text)
			if repaired:
				try:
					data = json.loads(repaired)
					validated = self.schema(**data)
					return GuardrailResult(
						action=GuardrailAction.WARN,
						guardrail_name=self.name,
						original_text=text,
						processed_text=validated.model_dump_json(),
						warnings=['JSON was repaired before validation'],
					)
				except Exception:
					pass

			return GuardrailResult(
				action=GuardrailAction.BLOCK,
				guardrail_name=self.name,
				original_text=text,
				processed_text='',
				blocked_reason=f'Output validation failed: {str(e)[:200]}',
			)

	def _extract_json(self, text: str) -> str:
		"""Extract JSON from markdown code blocks or raw text."""
		# Try markdown code block
		match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
		if match:
			return match.group(1).strip()

		# Try raw JSON object/array
		for start, end in [('{', '}'), ('[', ']')]:
			idx_start = text.find(start)
			idx_end = text.rfind(end)
			if idx_start != -1 and idx_end > idx_start:
				return text[idx_start : idx_end + 1]

		return text

	def _repair_json(self, text: str) -> Optional[str]:
		"""Attempt common JSON repairs."""
		repaired = text

		# Fix trailing commas
		repaired = re.sub(r',\s*([}\]])', r'\1', repaired)

		# Fix single quotes to double quotes
		repaired = repaired.replace("'", '"')

		# Fix unquoted keys
		repaired = re.sub(r'(\{|,)\s*(\w+)\s*:', r'\1 "\2":', repaired)

		try:
			json.loads(repaired)
			return repaired
		except json.JSONDecodeError:
			return None


# ─── Content Safety Filter ─────────────────────────────────────


class ContentSafetyFilter(BaseGuardrail):
	"""
	Filters content for profanity and toxicity.
	Used primarily for salary battle chat and user-facing outputs.
	"""

	name = 'content_safety_filter'

	# Basic profanity list (expandable)
	PROFANITY_PATTERNS = [
		re.compile(r'\b(f+u+c+k+|s+h+i+t+|a+s+s+h+o+l+e+|b+i+t+c+h+|d+a+m+n+)\b', re.IGNORECASE),
	]

	# Threat/harassment patterns
	THREAT_PATTERNS = [
		re.compile(r'(i\s+will\s+)?(kill|hurt|harm|destroy|attack)\s+(you|them|everyone)', re.IGNORECASE),
		re.compile(r'(death\s+threat|bomb\s+threat)', re.IGNORECASE),
	]

	def check_sync(self, text: str, context: Dict[str, Any] = None) -> GuardrailResult:
		warnings = []

		# Check threats (always block)
		for pattern in self.THREAT_PATTERNS:
			if pattern.search(text):
				return GuardrailResult(
					action=GuardrailAction.BLOCK,
					guardrail_name=self.name,
					original_text=text,
					processed_text='',
					blocked_reason='Content contains threatening language',
				)

		# Check profanity (warn)
		for pattern in self.PROFANITY_PATTERNS:
			if pattern.search(text):
				warnings.append('Profanity detected')
				break

		if warnings:
			return GuardrailResult(
				action=GuardrailAction.WARN,
				guardrail_name=self.name,
				original_text=text,
				processed_text=text,
				warnings=warnings,
			)

		return GuardrailResult(
			action=GuardrailAction.PASS,
			guardrail_name=self.name,
			original_text=text,
			processed_text=text,
		)


# ─── Guardrail Pipeline ────────────────────────────────────────


class GuardrailPipeline:
	"""
	Configurable chain-of-responsibility for guardrail checks.

	Runs guardrails in order. If any guardrail BLOCKs, the pipeline
	short-circuits and returns the blocking result.

	Usage:
	    pipeline = GuardrailPipeline([
	        InputSanitizer(),
	        PromptInjectionDetector(),
	    ])
	    result = await pipeline.check("user input")
	    if result.is_blocked:
	        return error_response(result.blocked_reason)
	"""

	def __init__(self, guardrails: List[BaseGuardrail] = None):
		self.guardrails = guardrails or []
		self._results_log: List[GuardrailResult] = []

	def check_sync(self, text: str, context: Dict[str, Any] = None) -> GuardrailResult:
		"""Run all guardrails in sequence synchronously."""
		current_text = text
		all_warnings = []
		self._results_log = []

		for guardrail in self.guardrails:
			try:
				result = guardrail.check_sync(current_text, context)
				self._results_log.append(result)

				if result.is_blocked:
					logger.warning(f'[GuardrailPipeline] BLOCKED by {guardrail.name}: {result.blocked_reason}')
					return result

				if result.warnings:
					all_warnings.extend(result.warnings)

				current_text = result.processed_text

			except Exception as e:
				logger.error(f'[GuardrailPipeline] Guardrail {guardrail.name} error: {e}')
				continue

		return GuardrailResult(
			action=GuardrailAction.WARN if all_warnings else GuardrailAction.PASS,
			guardrail_name='pipeline',
			original_text=text,
			processed_text=current_text,
			warnings=all_warnings,
			metadata={'guardrails_run': len(self.guardrails)},
		)

	async def check(self, text: str, context: Dict[str, Any] = None) -> GuardrailResult:
		"""
		Run all guardrails in sequence asynchronously.
		Returns the first blocking result, or the last pass/warn result.
		"""
		current_text = text
		all_warnings = []
		self._results_log = []

		for guardrail in self.guardrails:
			try:
				result = await guardrail.check(current_text, context)
				self._results_log.append(result)

				if result.is_blocked:
					logger.warning(f'[GuardrailPipeline] BLOCKED by {guardrail.name}: {result.blocked_reason}')
					return result

				if result.warnings:
					all_warnings.extend(result.warnings)

				# Use processed text for next guardrail
				current_text = result.processed_text

			except Exception as e:
				logger.error(f'[GuardrailPipeline] Guardrail {guardrail.name} error: {e}')
				# Continue on error (fail-open for guardrails)
				continue

		# All passed
		return GuardrailResult(
			action=GuardrailAction.WARN if all_warnings else GuardrailAction.PASS,
			guardrail_name='pipeline',
			original_text=text,
			processed_text=current_text,
			warnings=all_warnings,
			metadata={'guardrails_run': len(self.guardrails)},
		)

	@property
	def last_results(self) -> List[GuardrailResult]:
		"""Get results from the last pipeline run."""
		return self._results_log


# ─── Pre-built Pipelines ───────────────────────────────────────


def create_input_pipeline(sensitivity: str = 'medium') -> GuardrailPipeline:
	"""Create a standard input guardrail pipeline."""
	return GuardrailPipeline(
		[
			InputSanitizer(),
			PromptInjectionDetector(sensitivity=sensitivity),
		]
	)


def create_chat_pipeline() -> GuardrailPipeline:
	"""Create a guardrail pipeline for chat/battle inputs."""
	return GuardrailPipeline(
		[
			InputSanitizer(),
			PromptInjectionDetector(sensitivity='medium'),
			ContentSafetyFilter(),
		]
	)


def create_output_pipeline(schema: Type[BaseModel] = None) -> GuardrailPipeline:
	"""Create a standard output guardrail pipeline."""
	guardrails = []
	if schema:
		guardrails.append(OutputValidator(schema=schema))
	return GuardrailPipeline(guardrails)
