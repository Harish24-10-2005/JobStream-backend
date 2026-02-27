"""Quick verification of eval framework and metrics."""
import asyncio
from pathlib import Path

async def test():
    # === Eval Framework ===
    from evals.runner import (
        EvalRunner, EvalCase, EvalSuiteResult,
        ExactMatchScorer, ContainsScorer, SchemaScorer, ThresholdScorer,
        load_cases_from_json,
    )
    
    # Test scorers
    exact = ExactMatchScorer()
    score, details = exact.score({"name": "John", "age": 30}, {"name": "John", "age": 30})
    assert score == 1.0, f"ExactMatch failed: {score}"
    print("[PASS] ExactMatchScorer: perfect match = 1.0")
    
    contains = ContainsScorer()
    score, details = contains.score("Python FastAPI Developer", {"contains": ["Python", "FastAPI"]})
    assert score == 1.0, f"Contains failed: {score}"
    print("[PASS] ContainsScorer: all found = 1.0")
    
    schema = SchemaScorer()
    score, details = schema.score({"a": 1, "b": 2}, {"required_keys": ["a", "b", "c"]})
    assert abs(score - 0.667) < 0.01, f"Schema failed: {score}"
    print(f"[PASS] SchemaScorer: 2/3 keys = {score:.3f}")
    
    threshold = ThresholdScorer()
    score, details = threshold.score({"score": 0.85}, {"field": "score", "min": 0.7})
    assert score == 1.0, f"Threshold failed: {score}"
    print("[PASS] ThresholdScorer: above min = 1.0")
    
    # Test EvalRunner with mock agent
    async def mock_agent(input_data):
        return {"tailored_resume": "tailored", "match_score": 85}
    
    runner = EvalRunner("test_agent", mock_agent, scorer=SchemaScorer())
    cases = [
        EvalCase("t1", "Test 1", {"job": "SE"}, {"required_keys": ["tailored_resume", "match_score"]}),
        EvalCase("t2", "Test 2", {"job": "ML"}, {"required_keys": ["tailored_resume"]}),
    ]
    result = await runner.run(cases, "test_suite")
    assert result.total == 2 and result.passed == 2, f"Runner failed: {result.passed}/{result.total}"
    print(f"[PASS] EvalRunner: {result.passed}/{result.total} passed, avg_score={result.avg_score:.2f}")
    
    # Test JSON case loading
    resume_cases = load_cases_from_json(Path("evals/cases/resume_cases.json"))
    assert len(resume_cases) == 3, f"Resume cases: {len(resume_cases)}"
    print(f"[PASS] Case loader: {len(resume_cases)} resume cases loaded")
    
    # === Metrics ===
    from src.core.metrics import get_metrics, MetricsRegistry, track_agent
    
    metrics = get_metrics()
    assert isinstance(metrics, MetricsRegistry)
    
    # Test counter
    metrics.http_requests_total.inc({"method": "GET", "path": "/api/health", "status": "200"})
    metrics.http_requests_total.inc({"method": "GET", "path": "/api/health", "status": "200"})
    print("[PASS] Counter: incremented 2x")
    
    # Test gauge
    metrics.websocket_connections.set(5)
    print("[PASS] Gauge: set to 5")
    
    # Test histogram
    metrics.http_request_duration_seconds.observe(0.05, {"method": "GET", "path": "/", "status": "200"})
    print("[PASS] Histogram: observed 0.05s")
    
    # Test Prometheus output
    output = metrics.to_prometheus()
    assert "http_requests_total" in output
    assert "websocket_connections_active" in output
    print(f"[PASS] Prometheus export: {len(output)} chars")
    
    # Test decorator
    @track_agent("test_agent")
    async def my_agent():
        return {"result": "ok"}
    
    await my_agent()
    print("[PASS] @track_agent decorator works")
    
    print("\n=== ALL EVAL + METRICS TESTS PASSED ===")

asyncio.run(test())
