Run a PromQL query against Prometheus and interpret the results.

Execute: `uv run promql-query $ARGUMENTS`

## Available metrics
- `agent_step_count_total` — step 실행 횟수 (label: step_type)
- `agent_step_duration_seconds` — step 소요 시간 분포 (histogram)
- `agent_step_errors_total` — step 실패 횟수 (label: step_type, error_type)
- `agent_token_usage_tokens` — LLM 토큰 사용량 (histogram, label: direction=input|output)
- `agent_episode_duration_seconds` — episode 소요 시간 (histogram)
- `agent_episode_steps` — episode당 step 수 (histogram)
- `agent_custom_score` — 사용자 정의 점수 (histogram, label: score_name)

## Common labels
- `run_id` — 실험 실행 ID
- `prompt_version` — 프롬프트 버전 (ablation 비교축)
- `model`, `task_type`, `step_type`

## Example queries
- `agent_step_count_total{prompt_version="v1"}` — v1의 총 step 수
- `rate(agent_step_count_total[5m])` — 5분 단위 step 실행 rate
- `histogram_quantile(0.95, agent_step_duration_seconds_bucket{prompt_version="v1"})` — p95 latency
- `agent_token_usage_tokens_sum{direction="output"} / agent_token_usage_tokens_count{direction="output"}` — 평균 output token

## Flags
- `--range --start 1h` — 최근 1시간 range query
- `--json` — raw JSON 출력
- `--step 30s` — range query step 간격
