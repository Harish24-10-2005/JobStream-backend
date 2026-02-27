"""
Agent Evaluation Framework

Runs structured evaluations against AI agents to measure quality,
consistency, and reliability. Supports:
  - Test case definitions (input → expected output assertions)
  - Scoring metrics (accuracy, relevance, latency, cost)
  - Batch execution with parallelism control
  - JSON/Markdown report generation

Usage:
  python -m evals.runner --agent resume --suite basic
"""
import asyncio
import json
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


# ── Data Models ──────────────────────────────────────────────────

@dataclass
class EvalCase:
    """Single evaluation test case."""
    id: str
    name: str
    input: dict
    expected: dict  # expected output fields or patterns
    tags: list[str] = field(default_factory=list)
    timeout: float = 30.0

@dataclass
class EvalResult:
    """Result from running a single eval case."""
    case_id: str
    case_name: str
    passed: bool
    score: float  # 0.0 - 1.0
    latency_ms: float
    details: dict = field(default_factory=dict)
    error: Optional[str] = None

@dataclass
class EvalSuiteResult:
    """Aggregate results from an eval suite."""
    suite_name: str
    agent_name: str
    total: int
    passed: int
    failed: int
    avg_score: float
    avg_latency_ms: float
    results: list[EvalResult] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    @property
    def pass_rate(self) -> float:
        return self.passed / self.total if self.total > 0 else 0.0
    
    def to_dict(self) -> dict:
        return asdict(self)


# ── Scorers ──────────────────────────────────────────────────────

class Scorer(ABC):
    """Base class for evaluation scorers."""
    name: str = "base"
    
    @abstractmethod
    def score(self, output: Any, expected: dict) -> tuple[float, dict]:
        """Return (score 0-1, details dict)."""
        ...

class ExactMatchScorer(Scorer):
    """Checks if output contains all expected key-value pairs."""
    name = "exact_match"
    
    def score(self, output: Any, expected: dict) -> tuple[float, dict]:
        if not isinstance(output, dict):
            return 0.0, {"error": "Output is not a dict"}
        
        matches = 0
        total = len(expected)
        mismatches = {}
        
        for key, exp_val in expected.items():
            actual = output.get(key)
            if actual == exp_val:
                matches += 1
            else:
                mismatches[key] = {"expected": exp_val, "actual": actual}
        
        score = matches / total if total > 0 else 1.0
        return score, {"matches": matches, "total": total, "mismatches": mismatches}

class ContainsScorer(Scorer):
    """Checks if output string contains expected substrings."""
    name = "contains"
    
    def score(self, output: Any, expected: dict) -> tuple[float, dict]:
        text = str(output).lower()
        contains_list = expected.get("contains", [])
        if not contains_list:
            return 1.0, {}
        
        found = [s for s in contains_list if s.lower() in text]
        score = len(found) / len(contains_list)
        return score, {"found": found, "missing": [s for s in contains_list if s not in found]}

class SchemaScorer(Scorer):
    """Checks if output has expected keys (structural validation)."""
    name = "schema"
    
    def score(self, output: Any, expected: dict) -> tuple[float, dict]:
        required_keys = expected.get("required_keys", [])
        if not required_keys or not isinstance(output, dict):
            return 0.0 if required_keys else 1.0, {}
        
        present = [k for k in required_keys if k in output]
        score = len(present) / len(required_keys)
        return score, {"present": present, "missing": [k for k in required_keys if k not in output]}

class ThresholdScorer(Scorer):
    """Checks if a numeric value in output meets a threshold."""
    name = "threshold"
    
    def score(self, output: Any, expected: dict) -> tuple[float, dict]:
        field_name = expected.get("field", "score")
        threshold = expected.get("min", 0.5)
        
        if isinstance(output, dict):
            value = output.get(field_name, 0)
        else:
            value = float(output) if output else 0
        
        passed = value >= threshold
        return (1.0 if passed else 0.0), {"value": value, "threshold": threshold}


# ── Eval Runner ──────────────────────────────────────────────────

class EvalRunner:
    """
    Runs evaluation suites against agent functions.
    
    Usage:
        runner = EvalRunner("resume_agent", agent_fn, scorer=ContainsScorer())
        results = await runner.run(cases)
        runner.save_report(results, Path("evals/reports/"))
    """
    
    def __init__(
        self,
        agent_name: str,
        agent_fn: Callable,
        scorer: Scorer = None,
        max_parallel: int = 3,
    ):
        self.agent_name = agent_name
        self.agent_fn = agent_fn
        self.scorer = scorer or ExactMatchScorer()
        self.max_parallel = max_parallel
    
    async def run_case(self, case: EvalCase) -> EvalResult:
        """Run a single eval case."""
        start = time.perf_counter()
        try:
            # Call the agent
            if asyncio.iscoroutinefunction(self.agent_fn):
                output = await asyncio.wait_for(
                    self.agent_fn(case.input),
                    timeout=case.timeout
                )
            else:
                output = self.agent_fn(case.input)
            
            latency = (time.perf_counter() - start) * 1000
            
            # Score the output
            score, details = self.scorer.score(output, case.expected)
            
            return EvalResult(
                case_id=case.id,
                case_name=case.name,
                passed=score >= 0.7,  # 70% threshold for pass
                score=score,
                latency_ms=round(latency, 2),
                details=details,
            )
        except asyncio.TimeoutError:
            latency = (time.perf_counter() - start) * 1000
            return EvalResult(
                case_id=case.id,
                case_name=case.name,
                passed=False,
                score=0.0,
                latency_ms=round(latency, 2),
                error=f"Timeout after {case.timeout}s",
            )
        except Exception as e:
            latency = (time.perf_counter() - start) * 1000
            return EvalResult(
                case_id=case.id,
                case_name=case.name,
                passed=False,
                score=0.0,
                latency_ms=round(latency, 2),
                error=str(e),
            )
    
    async def run(self, cases: list[EvalCase], suite_name: str = "default") -> EvalSuiteResult:
        """Run all cases with parallelism control."""
        semaphore = asyncio.Semaphore(self.max_parallel)
        
        async def limited(case):
            async with semaphore:
                return await self.run_case(case)
        
        results = await asyncio.gather(*[limited(c) for c in cases])
        
        passed = sum(1 for r in results if r.passed)
        scores = [r.score for r in results]
        latencies = [r.latency_ms for r in results]
        
        return EvalSuiteResult(
            suite_name=suite_name,
            agent_name=self.agent_name,
            total=len(results),
            passed=passed,
            failed=len(results) - passed,
            avg_score=sum(scores) / len(scores) if scores else 0.0,
            avg_latency_ms=sum(latencies) / len(latencies) if latencies else 0.0,
            results=list(results),
        )
    
    def save_report(self, suite_result: EvalSuiteResult, output_dir: Path):
        """Save JSON and markdown reports."""
        output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # JSON report
        json_path = output_dir / f"{self.agent_name}_{timestamp}.json"
        with open(json_path, "w") as f:
            json.dump(suite_result.to_dict(), f, indent=2, default=str)
        
        # Markdown report
        md_path = output_dir / f"{self.agent_name}_{timestamp}.md"
        lines = [
            f"# Eval Report: {self.agent_name}",
            f"**Suite**: {suite_result.suite_name}  ",
            f"**Date**: {suite_result.timestamp}  ",
            f"**Pass Rate**: {suite_result.passed}/{suite_result.total} ({suite_result.pass_rate:.0%})  ",
            f"**Avg Score**: {suite_result.avg_score:.2f}  ",
            f"**Avg Latency**: {suite_result.avg_latency_ms:.0f}ms  ",
            "",
            "| # | Case | Score | Latency | Pass | Error |",
            "|---|------|-------|---------|------|-------|",
        ]
        for i, r in enumerate(suite_result.results, 1):
            status = "✅" if r.passed else "❌"
            error = r.error or ""
            lines.append(f"| {i} | {r.case_name} | {r.score:.2f} | {r.latency_ms:.0f}ms | {status} | {error} |")
        
        with open(md_path, "w") as f:
            f.write("\n".join(lines))
        
        logger.info(f"Eval reports saved to {output_dir}")
        return json_path, md_path


# ── CLI Entry Point ──────────────────────────────────────────────

def load_cases_from_json(path: Path) -> list[EvalCase]:
    """Load eval cases from a JSON file."""
    with open(path) as f:
        data = json.load(f)
    return [EvalCase(**c) for c in data.get("cases", data if isinstance(data, list) else [])]
