# agent-obs

AI agent의 행동을 관측하고, 프롬프트 버전 간 차이를 비교(ablation)하는 SDK.

## Quick Start

### Claude Code Plugin으로 설치

```bash
claude plugin marketplace add github.com/Chungws/agent-o11y-sdk
claude plugin install agent-obs
```

그 다음 `/agent-obs:setup` 실행.

### 수동 설치

```bash
uv add agent-obs
cd infra && docker compose up -d
```

## 사용법

```python
import agent_obs
from agent_obs import ExperimentContext

ctx = ExperimentContext(
    run_id="my-experiment-1",
    prompt_version="v1",
    model="gpt-4",
    task_type="my-task",
)

with agent_obs.init(ctx) as run:
    with run.episode("task-1") as ep:
        with ep.step("llm_call") as step:
            # LLM 호출
            step.record_tokens(input_tokens=100, output_tokens=50)
            step.log("completed")

        with ep.step("tool_call") as step:
            # Tool 실행
            step.record_score("quality", 0.95)
            step.save_artifact("output.json", {"result": "ok"})
```

## 구조

```
Run (trace)
└── Episode (parent span) — 하나의 태스크
    └── Step (child span) — 개별 행동 (llm_call, tool_call, custom)
```

모든 시그널에 `run_id`, `prompt_version` 등 실험 메타데이터가 자동 주입됩니다.

## Ablation 비교

두 프롬프트 버전을 동시 실행:

```bash
python examples/fake_tool_agent.py --version v1 --episodes 30 &
python examples/fake_tool_agent.py --version v2 --episodes 30 &
```

메트릭 조회:

```bash
uv run promql-query 'agent_step_count_total{prompt_version="v1"}'
uv run promql-query 'histogram_quantile(0.95, agent_step_duration_seconds_bucket{prompt_version="v2"})'
uv run logql-query '{service_name="agent-obs", severity_text="ERROR"}'
```

## 인프라

`docker compose up -d`로 실행되는 구성:

| 서비스 | 포트 | 용도 |
|--------|------|------|
| OTel Collector | 4317 (gRPC), 4318 (HTTP) | OTLP 수신 → 라우팅 |
| Prometheus | 9090 | 메트릭 저장 + PromQL |
| Loki | 3100 | 로그 저장 + LogQL |
| Grafana | 3000 | 대시보드 (선택) |

## 메트릭

| 이름 | 타입 | 설명 |
|------|------|------|
| `agent_step_duration_seconds` | histogram | Step 소요 시간 |
| `agent_step_count` | counter | Step 실행 횟수 |
| `agent_step_errors` | counter | Step 실패 횟수 |
| `agent_token_usage` | histogram | 토큰 사용량 |
| `agent_episode_duration_seconds` | histogram | Episode 소요 시간 |
| `agent_episode_steps` | histogram | Episode당 Step 수 |
| `agent_custom_score` | histogram | 사용자 정의 점수 |
