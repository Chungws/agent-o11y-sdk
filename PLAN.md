# Agent Observability SDK — Implementation Plan

## 1. 프로젝트 개요

### 무엇을 만드는가
AI agent 개발 시 agent의 행동을 통일된 방식으로 관측(observe)하고, 두 버전(예: 프롬프트 변경 전/후) 간 차이를 비교(ablation)할 수 있는 SDK + 인프라 + Claude Code 커맨드 세트.

### 왜 만드는가
- Agent는 프롬프트 한 줄만 바꿔도 행동 분포가 달라진다. 기존 단위 테스트로는 이 변화를 포착할 수 없다.
- Agent가 생성하는 산출물(tool call, LLM 응답, 코드, 파일 등)은 종류가 다양하지만, 관측 관점에서는 공통 구조가 있다.
- OpenAI의 Harness Engineering에서 영감을 받았다. 핵심 교훈은 "agent 관점에서 context 안에 없으면 존재하지 않는 것과 같다"는 점이다. 메트릭/로그가 쌓여 있어도 agent가 쿼리할 수단이 없으면 무의미하다.
- 목표는 Claude Code가 PromQL/LogQL로 직접 agent 행동 데이터를 쿼리하고, 버전 간 비교 판정(SHIP/INVESTIGATE/BLOCK)까지 내릴 수 있는 피드백 루프를 만드는 것이다.

### 영감 및 참고 자료
- **OpenAI Harness Engineering**: "애플리케이션의 가독성 향상(Making the application legible)" 챕터. 앱을 git worktree 단위로 부팅 가능하게 만들고, 로그/메트릭/트레이스를 worktree별 ephemeral observability 스택을 통해 agent에 노출. Agent가 완전히 격리된 앱 인스턴스에서 작업하며 해당 관측 데이터도 작업 완료 시 정리.
- **Microsoft AgentRx**: agent trajectory를 step-by-step으로 검증하여 "critical failure step"을 찾는 프레임워크. 9가지 failure taxonomy(hallucination, invalid invocation 등) 제공. → 현재 scope에서는 제외하되, 향후 확장 시 failure taxonomy label과 constraint check를 SDK에 얹을 수 있도록 설계 여지를 남겨둔다.

---

## 2. 아키텍처

### 전체 구조: 3개 레이어

```
[SDK (Python)] → [인프라 (OTel Collector → Prometheus + Loki + Artifact Store)] → [Claude Code Commands]
```

데이터 흐름은 단방향이다. SDK가 시그널을 생성하고, 인프라가 저장하고, Claude Code가 읽기만 한다.

### 레이어 1: SDK (Python)

#### 관측 계층 구조
- **Run**: 하나의 실험 실행 단위. OTel에서 trace에 매핑.
- **Episode**: 하나의 태스크 수행. OTel에서 parent span에 매핑.
- **Step**: 개별 행동 하나. OTel에서 child span에 매핑.
  - Step 타입 예시: `llm_call`, `tool_call`, `custom`
  - 타입이 뭐든 동일한 인터페이스로 계측됨.

#### Context Manager
모든 시그널(메트릭/로그/트레이스/아티팩트)에 자동으로 주입되는 실험 메타데이터:
- `run_id`: 실험 실행 식별자
- `episode_id`: 에피소드 식별자
- `prompt_version`: 프롬프트 버전 (ablation의 핵심 비교축)
- `model`: 사용된 LLM 모델
- `task_type`: 태스크 유형
- `branch`: git branch (선택적, CI 연동 시)
- `commit_sha`: git commit (선택적)
- 사용자 정의 key-value 추가 가능

이 메타데이터는 OTel Resource Attribute로 구현하여 모든 시그널에 일괄 적용한다.

#### 시그널 3종 + 아티팩트

**Metrics (OTel → Prometheus)**
- `agent_step_duration_seconds` (histogram): step 실행 시간 분포. label: step_type, endpoint 등
- `agent_step_count` (counter): step 실행 횟수
- `agent_step_errors` (counter): step 실패 횟수. label: error_type
- `agent_token_usage` (histogram): LLM 호출 시 토큰 사용량 분포. label: direction(input/output)
- `agent_episode_duration_seconds` (histogram): episode 전체 소요 시간
- `agent_episode_steps` (histogram): episode당 step 수 분포
- `agent_custom_score` (histogram): 사용자 정의 점수 (예: 태스크 성공률, 품질 점수 등)
- 이름 prefix는 `agent_`로 통일하여 다른 앱 메트릭과 구분

**Logs (OTel → Loki)**
- 모든 로그에 `trace_id`, `span_id` 포함 → 특정 span의 로그만 필터 가능
- Step 시작/종료 로그 (입력 요약, 출력 요약, 소요 시간)
- 에러 발생 시 상세 로그 (에러 타입, 메시지, 스택트레이스)
- LLM 호출 시 프롬프트/응답 요약 (전문은 아티팩트로)
- severity level 활용: INFO(정상 step), WARN(재시도), ERROR(실패)

**Traces (OTel → Prometheus/Loki correlate용)**
- Run → Episode → Step 계층이 그대로 span 계층으로 표현
- 각 span에 step_type, status, duration 등 attribute 포함
- span attribute에 아티팩트 경로 참조 포함

**Artifacts (별도 저장소)**
- OTel이 다루지 않는 파일성 데이터: LLM 프롬프트/응답 전문, 생성된 코드, diff, 스크린샷 등
- SDK가 저장 인터페이스를 제공: `step.save_artifact(name, data)`
- 내부적으로 `{run_id}/{episode_id}/{step_id}/{name}` 경로로 저장
- 해당 span attribute에 경로를 자동 기록 → trace에서 아티팩트로 drill-down 가능
- 저장소 백엔드는 pluggable: 로컬 파일시스템(기본), S3, MinIO
- SDK는 저장 인터페이스 + OTel 연결만 책임지고, 저장소 구현은 주입받음

#### 프레임워크 어댑터
- SDK 코어는 프레임워크 비종속. "Step 시작/끝"이라는 최소 인터페이스만 제공.
- LangChain, CrewAI 등 주요 프레임워크용 얇은 어댑터를 별도 모듈로 제공.
- 어댑터는 프레임워크의 callback/hook을 SDK의 Run/Episode/Step으로 매핑하는 역할만 수행.
- 직접 구현한 agent 루프에서도 동일하게 동작해야 함.

### 레이어 2: 인프라

#### 구성 요소
- **OTel Collector**: OTLP gRPC(:4317) / HTTP(:4318)로 수신. 메트릭은 Prometheus remote write, 로그는 Loki push로 라우팅.
- **Prometheus**: 메트릭 저장 및 PromQL 쿼리 제공. `resource_to_telemetry_conversion: enabled: true`로 resource attribute를 metric label로 변환.
- **Loki**: 로그 저장 및 LogQL 쿼리 제공. branch, prompt_version 등을 label로 인덱싱.
- **Artifact Store**: 로컬 파일시스템 기본. 마운트된 볼륨 또는 S3 호환 스토리지.
- **Grafana (선택)**: 디버깅용 UI. 필수는 아니지만 초기 개발 시 시각적 확인에 유용.

#### 배포 방식
- docker-compose로 로컬 원클릭 실행.
- 모든 포트는 localhost로 노출 → Claude Code에서 직접 HTTP 접근 가능.

#### 동시 실행을 통한 ablation
- 두 버전을 동시에 실행하여 같은 시간대에 데이터를 쌓는 것이 권장됨.
- 이유: 순차 실행 시 시간대별 외부 요인이 개입하여 Claude Code가 "이 차이가 코드 때문인지 환경 때문인지" 판단할 수 없음.
- 동시 실행 시 동일 time window 쿼리로 공정한 비교 가능.
- 방법: 환경변수(`PROMPT_VERSION=v1` / `PROMPT_VERSION=v2`)로 구분하여 같은 앱을 두 프로세스로 실행. 또는 컨테이너 두 개.

### 레이어 3: Claude Code Commands

#### 쿼리 스크립트
- `scripts/promql_query.py`: Prometheus HTTP API 래퍼. instant/range 쿼리 지원. 결과를 사람이 읽기 쉬운 형태로 포맷 + raw JSON 옵션.
- `scripts/logql_query.py`: Loki HTTP API 래퍼. 로그 조회 + 에러 패턴 집계 지원.
- 외부 라이브러리 의존 없이 urllib만 사용 (Claude Code 환경에서 바로 실행 가능하도록).

#### Custom Commands (.claude/commands/)

**`/query-metrics <promql>`**
- PromQL 실행 + 결과 해석.
- 사용 가능한 메트릭 이름, label, 예시 쿼리를 프롬프트에 포함.

**`/query-logs <logql>`**
- LogQL 실행 + 결과 해석.
- 사용 가능한 label, 예시 쿼리를 프롬프트에 포함.

**`/inspect-artifact <run_id> <episode_id> <step_id>`**
- 특정 step의 아티팩트 파일을 읽어서 내용 확인.
- span attribute에 기록된 경로를 기반으로 파일 접근.

**`/ablation-compare <version-a> <version-b>`**
- 메인 커맨드. 위 세 커맨드를 조합하여 종합 비교 수행.
- 비교 항목:
  - Step duration 분포 (p50, p95, p99)
  - Step/Episode 성공률
  - Episode당 step 수 (적을수록 효율적)
  - 토큰 사용량 분포
  - 에러율 및 에러 패턴 변화
  - 사용자 정의 점수 분포
- 출력: 항목별 비교 테이블 + SHIP/INVESTIGATE/BLOCK 판정
- 판정은 통계적 관점 필요: 단순 평균이 아닌 분포 비교. agent 행동은 stochastic하므로 충분한 episode 수에서의 비교가 전제.

---

## 3. 구현 순서

### Phase 1: 인프라
docker-compose로 OTel Collector + Prometheus + Loki + (Grafana) 실행 환경 구축. 수동으로 OTLP 데이터를 보내서 적재 확인.

### Phase 2: SDK 코어
Run → Episode → Step 계층 구현. Context Manager로 실험 메타데이터 자동 주입. 메트릭/로그/트레이스 생성. 아티팩트 저장 + span 연결. 프레임워크 비종속 인터페이스.

### Phase 3: 쿼리 스크립트
promql_query.py, logql_query.py 구현. 결과 포맷팅.

### Phase 4: Claude Code Commands
/query-metrics, /query-logs, /inspect-artifact, /ablation-compare 구현.

### Phase 5: 검증
성격이 다른 agent 패턴 2-3개로 SDK를 검증:
- 단순 tool-use agent (step 적고 linear)
- multi-turn reasoning agent (step 많고 반복적)
- code generation agent (외부 실행 결과를 피드백으로 받음)
실제로 프롬프트 한 줄 바꿔서 ablation 비교를 수행하고, SDK/커맨드의 부족한 점 발견.

### Phase 6 (향후): 확장
- AgentRx의 failure taxonomy label을 Step 로그에 추가
- Constraint check hook 인터페이스
- 프레임워크 어댑터 (LangChain, CrewAI 등)
- CI/CD 연동: PR 생성 시 자동 ablation 실행 + 코멘트

---

## 4. 설계 원칙

1. **관측 대상이 뭐든 같은 구조**: LLM call이든 tool call이든 파일 생성이든, Step이라는 동일한 인터페이스로 계측된다.
2. **실험 컨텍스트는 자동**: prompt_version, run_id 같은 메타데이터를 개발자가 매번 넣지 않아도 모든 시그널에 자동 주입된다.
3. **파일도 관측 범위 안**: OTel이 못 다루는 파일성 산출물은 별도 저장하되, span attribute로 연결하여 추적 가능성을 보장한다.
4. **프레임워크 비종속**: SDK 코어는 어떤 agent 프레임워크에도 의존하지 않는다.
5. **Claude Code가 읽을 수 있어야 의미가 있다**: 모든 데이터는 HTTP API 또는 파일시스템을 통해 CLI에서 접근 가능해야 한다.
6. **동시 실행 우선**: ablation 비교의 공정성을 위해 두 버전의 동시 실행을 기본 시나리오로 설계한다.
7. **향후 확장 여지**: failure taxonomy, constraint check, CI 연동 등을 나중에 얹을 수 있도록 인터페이스를 열어둔다. 지금 구현하지는 않는다.

---

## 5. 기술 스택

- **SDK**: Python, opentelemetry-sdk, opentelemetry-exporter-otlp-proto-grpc, opentelemetry-api
- **인프라**: Docker Compose, OTel Collector (contrib), Prometheus, Loki, Grafana (선택)
- **아티팩트 저장**: 로컬 파일시스템 (기본), S3 호환 (pluggable)
- **쿼리 스크립트**: Python, urllib만 사용 (외부 의존 없음)
- **Claude Code**: .claude/commands/ 디렉토리의 markdown 커맨드 파일

---

## 6. 디렉토리 구조

```
agent-obs/
├── infra/
│   ├── docker-compose.yml
│   ├── otel-collector-config.yml
│   ├── prometheus.yml
│   └── loki-config.yml
│
├── sdk/
│   ├── pyproject.toml
│   └── agent_obs/
│       ├── __init__.py
│       ├── context.py          # Context Manager
│       ├── run.py              # Run 계층
│       ├── episode.py          # Episode 계층
│       ├── step.py             # Step 계층
│       ├── metrics.py          # 메트릭 초기화 + 기록
│       ├── logs.py             # 구조화 로그
│       ├── traces.py           # 트레이스/span 관리
│       ├── artifacts.py        # 아티팩트 저장 + span 연결
│       └── adapters/           # 프레임워크 어댑터 (향후)
│           └── __init__.py
│
├── scripts/
│   ├── promql_query.py
│   └── logql_query.py
│
├── .claude/
│   └── commands/
│       ├── query-metrics.md
│       ├── query-logs.md
│       ├── inspect-artifact.md
│       └── ablation-compare.md
│
├── examples/
│   ├── simple_tool_agent.py    # 검증용 예시 1
│   ├── reasoning_agent.py      # 검증용 예시 2
│   └── codegen_agent.py        # 검증용 예시 3
│
├── PLAN.md                     # 이 문서
└── README.md
```
