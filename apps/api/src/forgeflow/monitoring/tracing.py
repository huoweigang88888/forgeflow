"""
ForgeFlow AI - OpenTelemetry Tracing.

Sets up distributed tracing with OpenTelemetry SDK and FastAPI auto-instrumentation.
All HTTP requests and LLM calls are traced for end-to-end visibility.
"""


from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter


def setup_tracing(app: FastAPI, otel_endpoint: str | None = None) -> None:
    """Initialize OpenTelemetry tracing for the FastAPI application.

    Args:
        app: The FastAPI application instance.
        otel_endpoint: OTLP collector endpoint (gRPC). If None, uses console exporter.
    """
    resource = Resource.create({SERVICE_NAME: "forgeflow-api"})

    provider = TracerProvider(resource=resource)

    # Choose exporter based on environment
    if otel_endpoint:
        exporter = OTLPSpanExporter(endpoint=otel_endpoint, insecure=True)
    else:
        # Development: print spans to console
        exporter = ConsoleSpanExporter()

    provider.add_span_processor(
        BatchSpanProcessor(
            exporter,
            max_queue_size=2048,
            max_export_batch_size=512,
            schedule_delay_millis=5000,
        )
    )

    trace.set_tracer_provider(provider)

    # Auto-instrument FastAPI (creates spans for every HTTP request)
    FastAPIInstrumentor.instrument_app(
        app,
        excluded_urls="/api/health,/api/metrics",
    )


# Module-level tracer for manual instrumentation
tracer = trace.get_tracer("forgeflow.api")
