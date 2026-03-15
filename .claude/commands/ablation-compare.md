Compare two prompt versions (ablation test) and make a SHIP/INVESTIGATE/BLOCK recommendation.

Arguments: `$ARGUMENTS` (format: `version-a version-b`, e.g. `v1 v2`)

## Comparison procedure

### 1. Parse arguments
Extract the two version identifiers from the arguments.

### 2. Query metrics for both versions
Run these PromQL queries for each version (replace `{ver}` with the version):

```
# Step count
agent_step_count_total{prompt_version="{ver}"}

# Step duration p50, p95, p99
histogram_quantile(0.5, agent_step_duration_seconds_bucket{prompt_version="{ver}"})
histogram_quantile(0.95, agent_step_duration_seconds_bucket{prompt_version="{ver}"})
histogram_quantile(0.99, agent_step_duration_seconds_bucket{prompt_version="{ver}"})

# Error rate
agent_step_errors_total{prompt_version="{ver}"} / agent_step_count_total{prompt_version="{ver}"}

# Episode step count (efficiency)
histogram_quantile(0.5, agent_episode_steps_bucket{prompt_version="{ver}"})

# Token usage
agent_token_usage_tokens_sum{prompt_version="{ver}"}

# Custom scores
agent_custom_score_sum{prompt_version="{ver}"} / agent_custom_score_count{prompt_version="{ver}"}
```

### 3. Query logs for errors
```bash
python scripts/logql_query.py '{service_name="agent-obs", prompt_version="{ver}", severity_text="ERROR"}' --start 24h
```

### 4. Build comparison table

| Metric | {version-a} | {version-b} | Delta |
|--------|------------|------------|-------|
| Total steps | | | |
| Step duration p50 | | | |
| Step duration p95 | | | |
| Error rate | | | |
| Episode steps (median) | | | |
| Total tokens | | | |
| Avg custom score | | | |
| Error count | | | |

### 5. Recommendation

Apply these rules:
- **SHIP**: version-b is equal or better on all key metrics (error rate, duration, score)
- **INVESTIGATE**: version-b is better on some metrics but worse on others, or the sample size is too small for confident comparison (< 30 episodes)
- **BLOCK**: version-b has higher error rate, significantly worse latency (>20% p95 regression), or lower quality scores

Output the recommendation with a brief justification citing specific metric deltas.
