def calculate_metrics(results):
    """
    Calculate evaluation metrics for the hospital voice-agent backend.

    Rubric weights:
        Task Success       = 35%
        Tool Correctness   = 25%
        State Consistency  = 15%
        Truthfulness       = 15%
        Efficiency         = 10%

    Functional correctness is independent of latency.
    Efficiency is measured separately using the latency target
    defined by run_eval.py.
    """

    if not results:
        return {
            "total_tests": 0,
            "passed_tests": 0,
            "failed_tests": 0,
            "task_success": 0,
            "tool_correctness": 0,
            "state_consistency": 0,
            "truthfulness": 0,
            "efficiency": 0,
            "average_latency_ms": 0,
            "p95_latency_ms": 0,
            "overall_score": 0,
        }

    total = len(results)

    # =========================================================
    # FUNCTIONAL METRICS
    # =========================================================

    task_success = (
        sum(
            bool(r.get("task_success", False))
            for r in results
        )
        / total
        * 100
    )

    tool_correctness = (
        sum(
            bool(r.get("tool_correctness", False))
            for r in results
        )
        / total
        * 100
    )

    state_consistency = (
        sum(
            bool(r.get("state_consistency", False))
            for r in results
        )
        / total
        * 100
    )

    truthfulness = (
        sum(
            bool(r.get("truthfulness", False))
            for r in results
        )
        / total
        * 100
    )

    efficiency = (
        sum(
            bool(r.get("efficiency", False))
            for r in results
        )
        / total
        * 100
    )

    # =========================================================
    # PASS / FAIL
    # =========================================================
    #
    # "passed" represents functional correctness.
    # Latency does not make a functionally correct test fail.
    # Latency is captured separately through efficiency.
    #

    passed_tests = sum(
        bool(r.get("passed", False))
        for r in results
    )

    failed_tests = total - passed_tests

    # =========================================================
    # LATENCY
    # =========================================================

    latencies = [
        float(r["latency_ms"])
        for r in results
        if r.get("latency_ms") is not None
    ]

    if latencies:

        average_latency = (
            sum(latencies) / len(latencies)
        )

        sorted_latencies = sorted(latencies)

        # Nearest-rank P95.
        #
        # This is intentionally simple and deterministic
        # for the small evaluation dataset.
        rank = max(
            1,
            int(
                0.95 * len(sorted_latencies)
                + 0.999999
            )
        )

        p95_latency = sorted_latencies[
            rank - 1
        ]

    else:

        average_latency = 0
        p95_latency = 0

    # =========================================================
    # WEIGHTED OVERALL SCORE
    # =========================================================

    overall_score = (
        0.35 * task_success
        + 0.25 * tool_correctness
        + 0.15 * state_consistency
        + 0.15 * truthfulness
        + 0.10 * efficiency
    )

    # =========================================================
    # FINAL METRICS
    # =========================================================

    return {
        "total_tests": total,

        "passed_tests": passed_tests,

        "failed_tests": failed_tests,

        "task_success": round(
            task_success,
            2
        ),

        "tool_correctness": round(
            tool_correctness,
            2
        ),

        "state_consistency": round(
            state_consistency,
            2
        ),

        "truthfulness": round(
            truthfulness,
            2
        ),

        "efficiency": round(
            efficiency,
            2
        ),

        "average_latency_ms": round(
            average_latency,
            2
        ),

        "p95_latency_ms": round(
            p95_latency,
            2
        ),

        "overall_score": round(
            overall_score,
            2
        ),
    }