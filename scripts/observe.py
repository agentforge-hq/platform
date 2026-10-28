"""Collect timestamped public availability, catalog, and freshness probes."""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from evaluation.core import EvaluationError, HttpBudget
from evaluation.observation import collect


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--origin', required=True)
    parser.add_argument('--output', type=Path, required=True, help='Append-only redacted JSONL output.')
    parser.add_argument('--samples', type=int, default=1, help='49 hourly samples span at least 48 hours. No job is scheduled.')
    parser.add_argument('--interval-seconds', type=float, default=3600)
    parser.add_argument('--max-requests', type=int, default=300, help='Shared cap including all probes and retries.')
    parser.add_argument('--timeout-seconds', type=float, default=15)
    parser.add_argument('--retries', type=int, default=1)
    args = parser.parse_args()
    if not (1 <= args.samples <= 1000 and math.isfinite(args.interval_seconds)
            and args.interval_seconds >= 60 and 1 <= args.max_requests <= 6000
            and 0 < args.timeout_seconds <= 60 and 0 <= args.retries <= 2):
        parser.error('Bounds: samples 1..1000, interval >=60s, attempts 1..6000, timeout <=60s, retries 0..2.')
    collect(args.origin, args.output, args.samples, args.interval_seconds,
            HttpBudget(args.max_requests, args.timeout_seconds, args.retries, 4))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (EvaluationError, OSError, ValueError, KeyError, TypeError) as error:
        print(f'Observation failed ({type(error).__name__}). No completed observation is claimed.', file=sys.stderr)
        raise SystemExit(1)
