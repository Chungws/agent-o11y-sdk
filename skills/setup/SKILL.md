---
name: setup
description: Set up agent-obs SDK and observability infrastructure in your project. Installs the SDK, creates docker-compose infra (OTel Collector, Prometheus, Loki, Grafana), and shows usage examples.
user-invocable: true
allowed-tools: Read, Write, Bash, Glob, Edit
---

# Agent Observability Setup

Set up agent-obs in the current project.

## Steps

### 1. Detect package manager

Check which package manager is used:
- If `pyproject.toml` exists with `[tool.uv]` or `uv.lock` → use `uv add agent-obs`
- If `pyproject.toml` exists → use `pip install agent-obs`
- If `requirements.txt` exists → add `agent-obs` to it and run `pip install -r requirements.txt`
- Otherwise → run `pip install agent-obs`

### 2. Create infra directory

Create `infra/` with these files:

**infra/docker-compose.yml:**
```yaml
services:
  otel-collector:
    image: otel/opentelemetry-collector-contrib:latest
    command: ["--config", "/etc/otel/config.yml"]
    volumes:
      - ./otel-collector-config.yml:/etc/otel/config.yml:ro
    ports:
      - "4317:4317"
      - "4318:4318"
    depends_on:
      - prometheus
      - loki

  prometheus:
    image: prom/prometheus:latest
    command:
      - --config.file=/etc/prometheus/prometheus.yml
      - --web.enable-remote-write-receiver
      - --web.enable-lifecycle
      - --web.enable-otlp-receiver
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - prometheus-data:/prometheus
    ports:
      - "9090:9090"

  loki:
    image: grafana/loki:latest
    command: -config.file=/etc/loki/config.yml
    volumes:
      - ./loki-config.yml:/etc/loki/config.yml:ro
      - loki-data:/loki
    ports:
      - "3100:3100"

  grafana:
    image: grafana/grafana:latest
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
      - GF_AUTH_ANONYMOUS_ENABLED=true
      - GF_AUTH_ANONYMOUS_ORG_ROLE=Admin
    volumes:
      - ./grafana-datasources.yml:/etc/grafana/provisioning/datasources/datasources.yml:ro
      - grafana-data:/var/lib/grafana
    ports:
      - "3000:3000"
    depends_on:
      - prometheus
      - loki

volumes:
  prometheus-data:
  loki-data:
  grafana-data:
```

**infra/otel-collector-config.yml:**
```yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
      http:
        endpoint: 0.0.0.0:4318

processors:
  deltatocumulative:

exporters:
  otlp_http/prometheus:
    endpoint: http://prometheus:9090/api/v1/otlp
    tls:
      insecure: true

  otlp_http/loki:
    endpoint: http://loki:3100/otlp
    tls:
      insecure: true

  debug:
    verbosity: basic

service:
  pipelines:
    traces:
      receivers: [otlp]
      exporters: [debug]
    metrics:
      receivers: [otlp]
      processors: [deltatocumulative]
      exporters: [otlp_http/prometheus, debug]
    logs:
      receivers: [otlp]
      exporters: [otlp_http/loki, debug]
```

**infra/prometheus.yml:**
```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

otlp:
  promote_resource_attributes:
    - run_id
    - prompt_version
    - model
    - task_type
    - branch
    - commit_sha
```

**infra/loki-config.yml:**
```yaml
auth_enabled: false

server:
  http_listen_port: 3100

common:
  path_prefix: /loki
  storage:
    filesystem:
      chunks_directory: /loki/chunks
      rules_directory: /loki/rules
  replication_factor: 1
  ring:
    kvstore:
      store: inmemory

schema_config:
  configs:
    - from: "2024-01-01"
      store: tsdb
      object_store: filesystem
      schema: v13
      index:
        prefix: index_
        period: 24h

limits_config:
  allow_structured_metadata: true
  volume_enabled: true
```

**infra/grafana-datasources.yml:**
```yaml
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true

  - name: Loki
    type: loki
    access: proxy
    url: http://loki:3100
```

### 3. Start infrastructure

Run `docker compose -f infra/docker-compose.yml up -d` and verify all 4 containers are running.

### 4. Show usage example

Print this example code:

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
            # Your LLM call here
            step.record_tokens(input_tokens=100, output_tokens=50)
            step.log("completed LLM call")

        with ep.step("tool_call") as step:
            # Your tool call here
            step.record_score("quality", 0.95)
```

### 5. Add .gitignore entries

Append to `.gitignore` if not already present:
```
artifacts/
.coverage
```

Tell the user setup is complete and they can:
- View Grafana at http://localhost:3000
- Query metrics at http://localhost:9090
- Query logs at http://localhost:3100
