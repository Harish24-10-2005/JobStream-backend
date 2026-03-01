"""
Celery App Configuration for JobAI

This module configures the Celery application for background task processing.
Browser automation tasks run in worker processes, not in the FastAPI server.

Run the worker:
    celery -A worker.celery_app worker --loglevel=info --pool=solo

Note: Use --pool=solo on Windows, --pool=prefork on Linux/Mac
"""

from celery import Celery

from src.core.config import settings

# Create Celery app
celery_app = Celery(
	'jobai',
	broker=settings.celery_broker,
	backend=settings.celery_backend,
	include=[
		'src.worker.tasks.applier_task',
	],
)

# Celery Configuration
celery_app.conf.update(
	# Task settings
	task_serializer='json',
	accept_content=['json'],
	result_serializer='json',
	timezone='UTC',
	enable_utc=True,
	# Task execution settings
	task_acks_late=True,  # Acknowledge after task completes
	task_reject_on_worker_lost=True,  # Re-queue if worker dies
	task_time_limit=600,  # 10 minute hard limit
	task_soft_time_limit=540,  # 9 minute soft limit (allows cleanup)
	# Worker settings
	worker_prefetch_multiplier=1,  # Only prefetch 1 task at a time (browser tasks are heavy)
	worker_concurrency=2,  # Max 2 concurrent browser tasks per worker
	# Result settings
	result_expires=3600,  # Results expire after 1 hour
	# Retry settings
	task_default_retry_delay=30,  # 30 seconds between retries
	task_max_retries=3,
	# Beat schedule (if using periodic tasks)
	beat_schedule={},
)

# Task routes (optional - for multiple queues)
celery_app.conf.task_routes = {
	'src.worker.tasks.applier_task.*': {'queue': 'browser'},
}


def get_celery_app() -> Celery:
	"""Get the configured Celery application."""
	return celery_app
