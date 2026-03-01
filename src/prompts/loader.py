"""
Prompt Template Engine
Loads versioned prompt templates from YAML files and renders them with Jinja2-style
variable interpolation.

Usage:
    from src.prompts.loader import prompt
    text = prompt("company.research", company="Stripe", role="SRE")
"""

import logging
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

logger = logging.getLogger(__name__)

_TEMPLATE_DIR = Path(__file__).parent / 'templates'
_cache: Dict[str, Dict] = {}


def _load_yaml(domain: str) -> Dict:
	"""Load and cache a YAML template file."""
	if domain in _cache:
		return _cache[domain]

	path = _TEMPLATE_DIR / f'{domain}.yaml'
	if not path.exists():
		raise FileNotFoundError(f'Prompt template not found: {path}')

	with open(path, 'r', encoding='utf-8') as f:
		data = yaml.safe_load(f)

	_cache[domain] = data
	logger.debug(f'Loaded prompt template: {domain} (v{data.get("version", "?")})')
	return data


def prompt(key: str, **variables: Any) -> str:
	"""
	Render a prompt template.

	Args:
	    key: Dot-separated key like "company.research" or "interview.behavioral"
	    **variables: Template variables to interpolate

	Returns:
	    Rendered prompt string
	"""
	parts = key.split('.', 1)
	if len(parts) != 2:
		raise ValueError(f"Prompt key must be 'domain.name', got: {key}")

	domain, name = parts
	data = _load_yaml(domain)

	prompts = data.get('prompts', {})
	if name not in prompts:
		raise KeyError(f"Prompt '{name}' not found in {domain}.yaml. Available: {list(prompts.keys())}")

	template_str = prompts[name].get('template', '')
	if not template_str:
		raise ValueError(f'Empty template for {key}')

	# Simple {variable} interpolation (safe — no eval)
	try:
		return template_str.format(**variables)
	except KeyError as e:
		raise KeyError(f"Missing variable {e} in prompt '{key}'. Required variables: {_extract_vars(template_str)}")


def get_prompt_metadata(key: str) -> Dict:
	"""Get metadata (version, description, variables) for a prompt."""
	parts = key.split('.', 1)
	domain, name = parts
	data = _load_yaml(domain)
	entry = data.get('prompts', {}).get(name, {})
	return {
		'domain': domain,
		'name': name,
		'version': data.get('version', 'unknown'),
		'description': entry.get('description', ''),
		'variables': entry.get('variables', []),
	}


def list_prompts(domain: Optional[str] = None) -> list:
	"""List all available prompts, optionally filtered by domain."""
	results = []
	search_dir = _TEMPLATE_DIR
	if not search_dir.exists():
		return results

	for yaml_file in sorted(search_dir.glob('*.yaml')):
		d = yaml_file.stem
		if domain and d != domain:
			continue
		data = _load_yaml(d)
		for name in data.get('prompts', {}):
			results.append(f'{d}.{name}')
	return results


def _extract_vars(template: str) -> list:
	"""Extract {variable} names from a template string."""
	import re

	return re.findall(r'\{(\w+)\}', template)


def reload():
	"""Clear template cache (for hot-reload in development)."""
	_cache.clear()
	logger.info('Prompt template cache cleared')
