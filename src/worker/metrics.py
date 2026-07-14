from prometheus_client import Counter, Histogram

REPLAY_JOBS_TOTAL = Counter(
    "replay_jobs_total",
    "Replay jobs finished by the worker",
    ["status"],
)
REPLAY_STEPS_TOTAL = Counter(
    "replay_steps_total",
    "Replay steps executed by the worker",
    ["status"],
)
REPLAY_INJECTIONS_TOTAL = Counter(
    "replay_injections_total",
    "Failure injections applied during replay",
    ["kind"],
)
REPLAY_STEP_LATENCY_MS = Histogram(
    "replay_step_latency_milliseconds",
    "Mock step execution latency in milliseconds",
    buckets=(1, 5, 10, 25, 50, 100, 250, 500, 1000, 5000),
)
REPLAY_JOB_DURATION_SECONDS = Histogram(
    "replay_job_duration_seconds",
    "End-to-end replay job duration in seconds",
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 30),
)
