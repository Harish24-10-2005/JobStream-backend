import os
import platform
import shutil
from typing import List, Literal, Optional

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def get_default_chrome_path() -> str:
	"""Attempts to find the Chrome executable path based on the OS."""
	system = platform.system()
	if system == 'Windows':
		paths = [
			os.path.expandvars(r'%ProgramFiles%\Google\Chrome\Application\chrome.exe'),
			os.path.expandvars(r'%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe'),
			os.path.expandvars(r'%LocalAppData%\Google\Chrome\Application\chrome.exe'),
		]
		for path in paths:
			if os.path.exists(path):
				return path
	elif system == 'Darwin':  # MacOS
		path = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
		if os.path.exists(path):
			return path
	elif system == 'Linux':
		# Look for typical linux paths
		for path in ['/usr/bin/google-chrome', '/usr/bin/chromium-browser']:
			if os.path.exists(path):
				return path

	# Fallback to shutil.which if available in PATH
	path = shutil.which('google-chrome') or shutil.which('chrome')
	return path or ''


def get_default_user_data_dir() -> str:
	"""Returns a default user data directory for Chrome."""
	# Use a localized directory within the project or a standard temp location
	# to avoid conflicts with the user's main Chrome profile.
	# Using a project-local directory is safer for automation.
	return os.path.abspath(os.path.join(os.getcwd(), 'chrome_data'))


class Settings(BaseSettings):
	"""
	Application Settings managed by Pydantic.
	Reads from environment variables and .env file.
	"""

	# ============================================
	# Environment & Application Settings
	# ============================================
	environment: Literal['development', 'staging', 'production'] = Field('development', alias='ENVIRONMENT')
	debug: bool = Field(False, alias='DEBUG')
	log_level: str = Field('INFO', alias='LOG_LEVEL')

	# ============================================
	# Server Configuration
	# ============================================
	host: str = Field('0.0.0.0', alias='HOST')
	port: int = Field(8000, alias='PORT')
	cors_origins: str = Field('http://localhost:3000,http://127.0.0.1:3000', alias='CORS_ORIGINS')

	# ============================================
	# Rate Limiting
	# ============================================
	rate_limit_enabled: bool = Field(True, alias='RATE_LIMIT_ENABLED')
	rate_limit_requests: int = Field(100, alias='RATE_LIMIT_REQUESTS')
	rate_limit_period: int = Field(60, alias='RATE_LIMIT_PERIOD')  # seconds

	# ============================================
	# Credit Guardrails (Query/Token Budgets)
	# ============================================
	credit_system_enabled: bool = Field(False, alias='CREDIT_SYSTEM_ENABLED')
	credit_daily_query_limit: int = Field(200, alias='CREDIT_DAILY_QUERY_LIMIT')
	credit_daily_token_limit: int = Field(150000, alias='CREDIT_DAILY_TOKEN_LIMIT')

	# ============================================
	# Redis (Production)
	# ============================================
	redis_url: Optional[str] = Field(None, alias='REDIS_URL')
	upstash_redis_rest_url: Optional[str] = Field(None, alias='UPSTASH_REDIS_REST_URL')
	upstash_redis_rest_token: Optional[SecretStr] = Field(None, alias='UPSTASH_REDIS_REST_TOKEN')

	# ============================================
	# Celery Task Queue Configuration
	# ============================================
	celery_broker_url: Optional[str] = Field(None, alias='CELERY_BROKER_URL')
	celery_result_backend: Optional[str] = Field(None, alias='CELERY_RESULT_BACKEND')

	@property
	def celery_broker(self) -> str:
		"""Get Celery broker URL, fallback to redis_url."""
		return self.celery_broker_url or self.redis_url or 'redis://localhost:6379/0'

	@property
	def celery_backend(self) -> str:
		"""Get Celery result backend URL, fallback to redis_url."""
		return self.celery_result_backend or self.redis_url or 'redis://localhost:6379/0'

	# ============================================
	# Request Limits
	# ============================================
	max_request_size: int = Field(10 * 1024 * 1024, alias='MAX_REQUEST_SIZE')  # 10MB

	# ============================================
	# Security Hardening
	# ============================================
	ws_auth_required: bool = Field(False, alias='WS_AUTH_REQUIRED')
	admin_api_key: Optional[SecretStr] = Field(None, alias='ADMIN_API_KEY')

	# AI Models - Groq
	groq_api_key: SecretStr = Field(..., alias='GROQ_API_KEY')
	groq_api_key_fallback: Optional[SecretStr] = Field(None, alias='GROQ_API_KEY1')
	groq_model: str = Field('llama-3.1-8b-instant', alias='GROQ_MODEL')

	# AI Models - OpenRouter
	openrouter_api_key: Optional[SecretStr] = Field(None, alias='OPENROUTER_API_KEY2')
	openrouter_api_key_fallback: Optional[SecretStr] = Field(None, alias='OPENROUTER_API_KEY1')
	openrouter_model: str = Field('qwen/qwen3-coder:free', alias='OPENROUTER_MODEL')

	# AI Models - Gemini
	gemini_api_key: Optional[SecretStr] = Field(None, alias='GEMINI_API_KEY')
	gemini_model: str = Field('gemini-2.0-flash-exp', alias='GEMINI_MODEL1')
	gemini_embedding_model: str = Field('models/gemini-embedding-001', alias='GEMINI_EMBEDDING_MODEL')

	# AI Models - Mistral
	mistral_api_key: Optional[SecretStr] = Field(None, alias='MISTRAL_API_KEY')
	mistral_model: str = Field('mistral-small-2506', alias='MISTRAL_MODEL')

	# Search
	serpapi_api_key: SecretStr = Field(..., alias='SERPAPI_API_KEY')

	# Browser Settings
	headless: bool = Field(True, alias='BROWSER_HEADLESS')
	chrome_path: str = Field(default_factory=get_default_chrome_path)
	user_data_dir: str = Field(default_factory=get_default_user_data_dir)
	profile_directory: str = Field('Default', alias='CHROME_PROFILE_DIR')

	# Supabase
	supabase_url: str = Field(..., alias='SUPABASE_URL')
	supabase_anon_key: str = Field(..., alias='SUPABASE_ANON_KEY')
	supabase_service_key: Optional[SecretStr] = Field(None, alias='SUPABASE_SERVICE_KEY')
	supabase_jwt_secret: Optional[str] = Field(
		None, alias='SUPABASE_JWT_SECRET'
	)  # Found in Supabase Dashboard > Project Settings > API > JWT Secret

	# Encryption (for credentials)
	encryption_key: Optional[SecretStr] = Field(None, alias='ENCRYPTION_KEY')

	# Observability - Arize Phoenix
	phoenix_collector_endpoint: Optional[str] = Field(None, alias='PHOENIX_COLLECTOR_ENDPOINT')

	model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

	@model_validator(mode='after')
	def derive_redis_url_from_upstash(self):
		"""
		Allow Upstash REST credentials as first-class config.
		If REDIS_URL is not provided, derive a TLS Redis URL from:
		  - UPSTASH_REDIS_REST_URL (https://<host>)
		  - UPSTASH_REDIS_REST_TOKEN
		Derived format: rediss://default:<token>@<host>:6379/0
		"""
		if self.redis_url:
			return self

		if self.upstash_redis_rest_url and self.upstash_redis_rest_token:
			url = self.upstash_redis_rest_url.strip()
			host = (
				url.replace('https://', '')
				.replace('http://', '')
				.split('/', 1)[0]
			)
			token = self.upstash_redis_rest_token.get_secret_value()
			self.redis_url = f'rediss://default:{token}@{host}:6379/0'
		return self

	def get_openrouter_key(self) -> str:
		if self.openrouter_api_key:
			return self.openrouter_api_key.get_secret_value()
		raise ValueError('OpenRouter API Key not found.')

	def get_openrouter_key1(self) -> str:
		if self.openrouter_api_key_fallback:
			return self.openrouter_api_key_fallback.get_secret_value()
		raise ValueError('OpenRouter API Key not found.')

	def get_encryption_key(self) -> bytes:
		"""Get or generate encryption key for credential storage."""
		if self.encryption_key:
			key = self.encryption_key.get_secret_value()
			# Ensure key is 32 bytes for AES-256
			return key.encode()[:32].ljust(32, b'\0')
		# Derive a key using SUPABASE_JWT_SECRET or fall back to a warning
		import hashlib
		import logging

		logger = logging.getLogger(__name__)
		if self.supabase_jwt_secret:
			logger.warning('No ENCRYPTION_KEY set; deriving from JWT secret. Set ENCRYPTION_KEY for production.')
			return hashlib.sha256(self.supabase_jwt_secret.encode()).digest()
		if self.environment == 'production':
			raise ValueError('ENCRYPTION_KEY is required in production. Set ENCRYPTION_KEY or SUPABASE_JWT_SECRET.')
		logger.error('No ENCRYPTION_KEY or SUPABASE_JWT_SECRET set! Using insecure default key (development only).')
		return hashlib.sha256(b'jobstream-insecure-default-key').digest()

	# ============================================
	# Production Helper Properties
	# ============================================

	@property
	def is_production(self) -> bool:
		"""Check if running in production environment."""
		return self.environment == 'production'

	@property
	def is_development(self) -> bool:
		"""Check if running in development environment."""
		return self.environment == 'development'

	def get_cors_origins(self) -> List[str]:
		"""Parse CORS origins from comma-separated string."""
		if not self.cors_origins:
			return []
		return [origin.strip() for origin in self.cors_origins.split(',') if origin.strip()]

	def get_log_level(self) -> int:
		"""Convert log level string to logging constant."""
		import logging

		levels = {
			'DEBUG': logging.DEBUG,
			'INFO': logging.INFO,
			'WARNING': logging.WARNING,
			'ERROR': logging.ERROR,
			'CRITICAL': logging.CRITICAL,
		}
		return levels.get(self.log_level.upper(), logging.INFO)

	@field_validator('log_level')
	@classmethod
	def validate_log_level(cls, v: str) -> str:
		"""Validate log level is a valid option."""
		valid_levels = {'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'}
		if v.upper() not in valid_levels:
			raise ValueError(f'Invalid log level: {v}. Must be one of {valid_levels}')
		return v.upper()

	@field_validator('debug', mode='before')
	@classmethod
	def coerce_debug_bool(cls, v):
		"""Accept common non-boolean env strings without crashing startup/tests."""
		if isinstance(v, bool):
			return v
		if isinstance(v, str):
			value = v.strip().lower()
			if value in {'1', 'true', 'yes', 'on', 'debug', 'development', 'dev'}:
				return True
			if value in {'0', 'false', 'no', 'off', 'release', 'production', 'prod'}:
				return False
		return v

	@field_validator('rate_limit_requests')
	@classmethod
	def validate_rate_limit_requests(cls, v: int) -> int:
		"""Validate rate limit requests is positive."""
		if v <= 0:
			raise ValueError('rate_limit_requests must be positive')
		return v

	@field_validator('rate_limit_period')
	@classmethod
	def validate_rate_limit_period(cls, v: int) -> int:
		"""Validate rate limit period is positive."""
		if v <= 0:
			raise ValueError('rate_limit_period must be positive')
		return v

	@field_validator('credit_daily_query_limit')
	@classmethod
	def validate_credit_daily_query_limit(cls, v: int) -> int:
		if v <= 0:
			raise ValueError('credit_daily_query_limit must be positive')
		return v

	@field_validator('credit_daily_token_limit')
	@classmethod
	def validate_credit_daily_token_limit(cls, v: int) -> int:
		if v <= 0:
			raise ValueError('credit_daily_token_limit must be positive')
		return v


settings = Settings()
