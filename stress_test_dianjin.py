"""
Standalone Dianjin reliability stress-test.

Purpose: hammer call_agent_api with many parallel HEAVY calls (long prompts that
force long response streams) to surface Dianjin reliability failures faster. Long
streams are where "stream ended without returning text" / "response ended
prematurely" tend to strike, unlike trivial calls. Any call that fails after all
internal retries is automatically recorded in paper_runs/latest/dianjin_failures.log
(via the existing log_dianjin_failure logic in agent_api.py).

Best run during Dianjin's known bad window (roughly 1-6pm China time).

Run from the AutoResearch project root (same place you run uvicorn):

    python stress_test_dianjin.py

Optional args:
    --waves N        number of sequential waves (default 10)
    --per-wave N     parallel calls per wave (default 10)
    --label TEXT     label used in logs (default "StressTest")
"""
from __future__ import annotations

import argparse
import concurrent.futures
import time

from backend.agent_api import call_agent_api


# A heavy, realistic prompt that forces a long response stream — this is where
# Dianjin's "stream ended without returning text" / "response ended prematurely"
# failures tend to surface, unlike trivial short calls which complete instantly.
HEAVY_PROMPT = (
    "You are a research engineer analyzing a machine learning repository for an "
    "autonomous research pipeline. Below is a detailed scenario. Read it carefully "
    "and produce a thorough, multi-paragraph analysis.\n\n"
    "SCENARIO: A knowledge distillation experiment compares student transformer models "
    "with 2, 4, and 6 layers, distilled from a fixed 12-layer BERT teacher on a text "
    "classification task using the SST-2 dataset. The pipeline clones the repository, "
    "installs dependencies in an isolated environment, and executes the experiment "
    "script, parsing RESULT lines from stdout.\n\n"
    "TASK: Write a detailed analysis covering: (1) what factors would determine whether "
    "increasing student layers improves accuracy, (2) the tradeoffs between model "
    "capacity and overfitting on small datasets, (3) how distillation temperature and "
    "loss weighting affect the student's ability to match the teacher, (4) common "
    "failure modes when running such experiments on CPU with limited epochs, (5) how one "
    "would validate that reported accuracy numbers are genuine and not artifacts of "
    "cached results, and (6) recommendations for making the experiment reproducible. "
    "Write at length, with specific technical reasoning for each point. Aim for a "
    "comprehensive response of several hundred words."
)


def one_call(index: int, label: str) -> tuple[int, bool, str]:
    """Make a single heavy call. Returns (index, succeeded, note)."""
    try:
        text = call_agent_api(HEAVY_PROMPT, label=label)
        ok = bool(text and text.strip())
        return index, ok, (f"{len(text.strip())} chars returned" if ok else "empty response")
    except Exception as exc:
        # call_agent_api raises RuntimeError after exhausting its 3 retries.
        # By this point the failure has ALREADY been written to
        # dianjin_failures.log inside call_agent_api. We just note it here.
        return index, False, f"FAILED: {exc}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Stress-test Dianjin to surface reliability failures.")
    parser.add_argument("--waves", type=int, default=10, help="Number of sequential waves.")
    parser.add_argument("--per-wave", type=int, default=10, help="Parallel calls per wave.")
    parser.add_argument("--label", default="StressTest", help="Label used in logs.")
    args = parser.parse_args()

    total = args.waves * args.per_wave
    print(f"[StressTest] Starting: {args.waves} waves x {args.per_wave} calls = {total} total calls")
    print(f"[StressTest] Genuine failures will be recorded in paper_runs/latest/dianjin_failures.log\n")

    successes = 0
    failures = 0
    start = time.time()

    for wave in range(1, args.waves + 1):
        print(f"[StressTest] --- Wave {wave}/{args.waves} ---")
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.per_wave) as executor:
            futures = [
                executor.submit(one_call, wave * 100 + i, args.label)
                for i in range(args.per_wave)
            ]
            for future in concurrent.futures.as_completed(futures):
                index, ok, note = future.result()
                if ok:
                    successes += 1
                else:
                    failures += 1
                    print(f"[StressTest]   call {index}: {note}")
        print(f"[StressTest] Running totals -> successes: {successes}, failures: {failures}\n")

    elapsed = time.time() - start
    print(f"[StressTest] Done in {int(elapsed)}s. Total successes: {successes}, total failures: {failures}")
    if failures:
        print(f"[StressTest] {failures} failure(s) recorded. Check paper_runs/latest/dianjin_failures.log")
    else:
        print("[StressTest] No genuine failures this run. Try again during Dianjin's peak-hour window (1-6pm China time).")


if __name__ == "__main__":
    main()