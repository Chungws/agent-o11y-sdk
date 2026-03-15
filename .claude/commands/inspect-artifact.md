Inspect artifacts saved by a specific step.

Read the artifact files at `artifacts/$ARGUMENTS` (format: `{run_id}/{episode_id}/{step_id}`).

## How to find artifact paths
1. Artifact 경로는 span attribute에 기록됨 (`artifact.{name}` 형태)
2. `artifacts/` 디렉토리 아래 `{run_id}/{episode_id}/{step_id}/{name}` 구조

## Steps
1. List files in the given artifact path
2. Read each artifact file and summarize its contents
3. If the artifact is JSON, parse and highlight key fields
4. If it's a prompt/response pair, compare input/output
