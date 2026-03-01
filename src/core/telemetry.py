import logging
from typing import Optional

from openinference.instrumentation.langchain import LangChainInstrumentor
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from src.core.config import settings

logger = logging.getLogger(__name__)


def setup_telemetry(endpoint: Optional[str] = None):
	"""
	Setup OpenTelemetry instrumentation for LangChain.
	Configures TraceProvider and OTLP Exporter to send traces to Phoenix.
	"""
	otel_endpoint = endpoint or settings.phoenix_collector_endpoint

	if not otel_endpoint:
		logger.info('🔭 Telemetry: Disabled (PHOENIX_COLLECTOR_ENDPOINT not set)')
		return

	try:
		# 1. Configure Trace Provider
		provider = TracerProvider()

		# 2. Configure OTLP Exporter (sends to Phoenix)
		# Append /v1/traces if not present, as OTLPSpanExporter expects the full path usually
		if not otel_endpoint.endswith('/v1/traces'):
			collector_url = f'{otel_endpoint.rstrip("/")}/v1/traces'
		else:
			collector_url = otel_endpoint

		exporter = OTLPSpanExporter(endpoint=collector_url)

		# 3. Add Span Processor
		processor = BatchSpanProcessor(exporter)
		provider.add_span_processor(processor)

		# 4. Set Global Tracer Provider
		trace.set_tracer_provider(provider)

		# 5. Auto-Instrument LangChain
		LangChainInstrumentor().instrument(tracer_provider=provider)

		logger.info(f'🔭 Telemetry: Enabled (Sending traces to {collector_url})')

	except Exception as e:
		logger.error(f'❌ Telemetry Setup Failed: {e}', exc_info=True)
