Run a LogQL query against Loki and interpret the results.

Execute: `uv run logql-query $ARGUMENTS`

## Available labels
- `service_name` — 항상 "agent-obs"
- `run_id` — 실험 실행 ID
- `prompt_version` — 프롬프트 버전
- `step_type` — step 타입 (llm_call, tool_call, custom 등)
- `severity_text` — 로그 레벨 (INFO, WARN, ERROR)

## Example queries
- `{service_name="agent-obs"}` — 모든 agent 로그
- `{service_name="agent-obs", run_id="run-1"}` — 특정 실행 로그
- `{service_name="agent-obs", severity_text="ERROR"}` — 에러만
- `{service_name="agent-obs"} |= "timeout"` — "timeout" 포함 로그
- `{service_name="agent-obs"} | json | line_format "{{.body}}"` — JSON 파싱

## Flags
- `--start 2h` — 최근 2시간 조회
- `--limit 50` — 최대 50줄
- `--json` — raw JSON 출력
