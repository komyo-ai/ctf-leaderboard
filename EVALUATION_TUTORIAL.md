# Purple Agent Evaluation Tutorial

This tutorial guides you through setting up automated evaluations for your purple agent against green agents in the AgentBeats platform.

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Setting Up GitHub Secrets](#setting-up-github-secrets)
4. [Creating an Evaluation](#creating-an-evaluation)
5. [Configuring the Workflow](#configuring-the-workflow)
6. [Testing Your Evaluation](#testing-your-evaluation)
7. [Retrieving Results](#retrieving-results)
8. [Troubleshooting](#troubleshooting)

---

## Overview

**What is an evaluation?**

An evaluation tests your purple agent against a specific green agent (benchmark). The evaluation workflow:

1. Pulls your purple agent Docker image from GHCR
2. Pulls the green agent Docker image from GHCR
3. Starts all required containers with proper networking
4. Runs the green agent's evaluation logic
5. Collects results as JSON artifacts
6. Optionally comments results on your PR

**Key concepts:**

- **Green Agent**: The evaluation orchestrator (benchmark) that tests your agent
- **Purple Agent**: Your agent being evaluated
- **Evaluation Directory**: A folder in `evaluations/` containing configuration for a specific evaluation
- **Workflow File**: GitHub Actions workflow in `.github/workflows/` that runs the evaluation

---

## Prerequisites

Before setting up an evaluation, ensure you have:

### 1. Purple Agent Published to GHCR

Your purple agent must be built and published to GitHub Container Registry (GHCR). This should include:

- A Docker image with your agent code
- Published to `ghcr.io/YOUR_USERNAME/YOUR_AGENT_NAME`
- Tagged with a specific version or digest

**Example:**
```bash
# Build your agent
docker build -t ghcr.io/myusername/purple-debater:v1.0.0 ./sample-debate-purple-agent

# Push to GHCR
docker push ghcr.io/myusername/purple-debater:v1.0.0

# Get the digest for pinning
docker inspect --format='{{index .RepoDigests 0}}' ghcr.io/myusername/purple-debater:v1.0.0
# Output: ghcr.io/myusername/purple-debater@sha256:abc123def456...
```

### 2. Green Agent Information

You need to know:

- Green agent image location (GHCR URL)
- Green agent image digest (for reproducibility)
- What environment variables the green agent expects
- What ports the green agent uses
- How to invoke the green agent's evaluation command

**Where to find this:** Green agent specifications are typically provided by the AgentBeats platform or benchmark maintainers.

### 3. API Keys

Most agents require API keys for LLM services. You'll need:

- API keys for any services your purple agent uses (e.g., Gemini, OpenAI)
- API keys for any services the green agent uses
- These must be stored as GitHub Secrets (see next section)

---

## Setting Up GitHub Secrets

API keys and other sensitive credentials must be stored as GitHub Secrets and passed to Docker containers as environment variables.

### Step 1: Create GitHub Secrets

1. Go to your repository on GitHub
2. Click **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Add each secret:

**Common secrets you'll need:**

| Secret Name | Description | Example Value |
|-------------|-------------|---------------|
| `GEMINI_API_KEY` | Google Gemini API key | `AIzaSyD...` |
| `OPENAI_API_KEY` | OpenAI API key | `sk-proj-...` |
| `ANTHROPIC_API_KEY` | Anthropic Claude API key | `sk-ant-...` |

### Step 2: Reference Secrets in Workflow

In your workflow file, secrets are accessed via `${{ secrets.SECRET_NAME }}` and passed to containers:

```yaml
- name: Start purple agent
  run: |
    docker run -d \
      --name purple-agent \
      -e GEMINI_API_KEY="${{ secrets.GEMINI_API_KEY }}" \
      purple-agent:local
```

### Step 3: Verify Secret Configuration

**Important security notes:**

- Never print secrets in logs
- Secrets are masked in GitHub Actions output
- Each secret is scoped to your repository
- Collaborators with write access can use secrets in workflows

**Testing secrets:**

You can verify a secret is set (without revealing its value):

```yaml
- name: Check if API key is set
  run: |
    if [ -z "${{ secrets.GEMINI_API_KEY }}" ]; then
      echo "ERROR: GEMINI_API_KEY is not set"
      exit 1
    else
      echo "✓ GEMINI_API_KEY is configured"
    fi
```

---

## Creating an Evaluation

### Step 1: Create Evaluation Directory

Create a directory under `evaluations/` for your evaluation:

```bash
mkdir -p evaluations/my-evaluation
```

**Naming convention:** Use descriptive names like:
- `debate-evaluation`
- `qa-retrieval-evaluation`
- `code-generation-evaluation`

### Step 2: Add Documentation (Optional)

Create a README to document what this evaluation tests:

```bash
touch evaluations/my-evaluation/README.md
```

**Example README:**

```markdown
# My Evaluation

**Green Agent:** `ghcr.io/agentbeats/green-my-benchmark@sha256:...`

**Purpose:** Tests the purple agent's ability to [describe capability]

**Configuration:**
- Topic: [example topic]
- Rounds: 3
- Timeout: 5 minutes

**Expected Output:**
- JSON file with scores and reasoning
- Scores range from 0-100
```

### Step 3: Add Configuration Files (Optional)

Depending on the green agent, you may need configuration files:

- `config.json` - Evaluation parameters
- `prompts.txt` - Test prompts
- `expected_outputs.json` - Expected results for validation

**Check the green agent documentation** to see what configuration it expects.

---

## Configuring the Workflow

### Step 1: Copy the Template

Start with the skeleton template:

```bash
cp .github/workflows/eval-template.yml .github/workflows/eval-my-evaluation.yml
```

### Step 2: Replace Placeholders

Open the workflow file and replace all `[PLACEHOLDER]` values:

#### Basic Information

```yaml
name: Evaluation - My Evaluation  # [EVALUATION_NAME]

on:
  pull_request:
    branches: [ main ]
    paths:
      - 'evaluations/my-evaluation/**'  # [EVALUATION_DIR]
      - '.github/workflows/eval-my-evaluation.yml'
```

#### Green Agent Configuration

```yaml
- name: Pull green agent image
  run: |
    docker pull ghcr.io/agentbeats/green-my-benchmark@sha256:abc123def456...
    docker tag ghcr.io/agentbeats/green-my-benchmark@sha256:abc123def456... green-agent:local
```

**How to get the digest:**
```bash
docker pull ghcr.io/agentbeats/green-my-benchmark:v1.0.0
docker inspect --format='{{index .RepoDigests 0}}' ghcr.io/agentbeats/green-my-benchmark:v1.0.0
```

#### Purple Agent Configuration

```yaml
- name: Pull purple agent image
  run: |
    docker pull ghcr.io/myusername/purple-agent@sha256:def456abc789...
    docker tag ghcr.io/myusername/purple-agent@sha256:def456abc789... purple-agent:local
```

#### Start Purple Agent(s)

```yaml
- name: Start purple agent
  run: |
    docker run -d \
      --name purple-agent \
      --network eval-network \
      -p 8080:8080 \
      -e GEMINI_API_KEY="${{ secrets.GEMINI_API_KEY }}" \
      purple-agent:local
```

**Key points:**

- Use `--network eval-network` for container communication
- Expose ports with `-p HOST_PORT:CONTAINER_PORT`
- Pass secrets with `-e VAR_NAME="${{ secrets.SECRET_NAME }}"`
- Use descriptive container names

**Multiple agents:** If your evaluation needs multiple purple agents (like debate with pro/con), start multiple containers:

```yaml
- name: Start pro debater
  run: |
    docker run -d \
      --name purple-debater-pro \
      --network eval-network \
      -p 9019:9019 \
      -e GEMINI_API_KEY="${{ secrets.GEMINI_API_KEY }}" \
      purple-debater:local \
      python debater.py --host 0.0.0.0 --port 9019

- name: Start con debater
  run: |
    docker run -d \
      --name purple-debater-con \
      --network eval-network \
      -p 9018:9018 \
      -e GEMINI_API_KEY="${{ secrets.GEMINI_API_KEY }}" \
      purple-debater:local \
      python debater.py --host 0.0.0.0 --port 9018
```

#### Health Checks

Update the health check to match your purple agent's endpoint if it has one:

```yaml
- name: Wait for purple agent to be healthy
  run: |
    echo "Waiting for purple agent to be ready..."
    for i in {1..30}; do
      HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:8080/health" 2>/dev/null || echo "000")

      if [ "$HTTP_CODE" != "000" ] && [ "$HTTP_CODE" != "502" ] && [ "$HTTP_CODE" != "503" ]; then
        echo "✓ Purple agent is healthy (HTTP $HTTP_CODE)"
        break
      fi

      if [ $i -eq 30 ]; then
        echo "✗ Purple agent failed to become healthy"
        docker logs purple-agent
        exit 1
      fi

      echo "Waiting... (attempt $i/30, HTTP $HTTP_CODE)"
      sleep 2
    done
```

**Common health endpoints:**
- `/health` - Dedicated health check
- `/` - Root endpoint (A2A agents)
- `/api/v1/status` - Status endpoint

**Note:** A2A agents may return HTTP 405 on GET requests to root, which is acceptable (server is up).

#### Run Green Agent Evaluation

This is the most important step - running the actual evaluation:

```yaml
- name: Run evaluation
  run: |
    echo "Running evaluation..."

    docker run --rm \
      --name green-agent \
      --network eval-network \
      -e CONFIG_PARAM="value" \
      -e PURPLE_AGENT_URL="http://purple-agent:8080" \
      -e GEMINI_API_KEY="${{ secrets.GEMINI_API_KEY }}" \
      green-agent:local \
      python /app/run_evaluation.py \
      | tee evaluation-results.json
```

**Key points:**

- Use `--rm` to auto-remove container after completion
- Use `--network eval-network` to communicate with purple agents
- Pass purple agent URLs using **container names** (not localhost)
- Pipe output to `tee` to save results and display them
- Check green agent documentation for exact command and environment variables

**Container name resolution:** Inside the Docker network, containers can reach each other using container names:
- `http://purple-agent:8080` ✅
- `http://localhost:8080` ❌ (would point to green agent's own localhost)

#### Cleanup

Update cleanup to remove all containers you started:

```yaml
- name: Stop and remove containers
  if: always()
  run: |
    echo "Cleaning up containers..."
    docker stop purple-agent || true
    docker rm purple-agent || true
    docker network rm eval-network || true
```

For multiple containers:

```yaml
- name: Stop and remove containers
  if: always()
  run: |
    echo "Cleaning up containers..."
    docker stop purple-debater-pro purple-debater-con || true
    docker rm purple-debater-pro purple-debater-con || true
    docker network rm eval-network || true
```

### Step 3: Review the Complete Workflow

See `.github/workflows/eval-debate.yml` for a complete working example.

---

## Testing Your Evaluation

### Test Locally (Recommended)

Before pushing, test your evaluation locally to catch issues:

#### 1. Build/pull images locally

```bash
# Pull or build your purple agent
docker build -t purple-agent:local ./your-agent-directory

# Pull green agent (if publicly available)
docker pull ghcr.io/agentbeats/green-agent:v1.0.0
docker tag ghcr.io/agentbeats/green-agent:v1.0.0 green-agent:local
```

#### 2. Create network

```bash
docker network create eval-network
```

#### 3. Start purple agent(s)

```bash
docker run -d \
  --name purple-agent \
  --network eval-network \
  -p 8080:8080 \
  -e GEMINI_API_KEY="your-api-key-here" \
  purple-agent:local
```

#### 4. Check health

```bash
curl http://localhost:8080/health
# or
curl http://localhost:8080/
```

#### 5. Run green agent

```bash
docker run --rm \
  --name green-agent \
  --network eval-network \
  -e PURPLE_AGENT_URL="http://purple-agent:8080" \
  -e GEMINI_API_KEY="your-api-key-here" \
  green-agent:local \
  python /app/run_evaluation.py
```

#### 6. Cleanup

```bash
docker stop purple-agent
docker rm purple-agent
docker network rm eval-network
```

### Test in GitHub Actions

#### Option 1: Manual Trigger

1. Push your workflow file
2. Go to **Actions** tab in GitHub
3. Select your workflow
4. Click **Run workflow**
5. Select branch and click **Run workflow**

#### Option 2: Create Draft PR

1. Create a new branch
2. Make a small change in your evaluation directory
3. Push and create a PR (mark as draft)
4. Check the Actions tab to see if workflow runs
5. Review logs and artifacts

---

## Retrieving Results

### From GitHub Actions UI

1. Go to your repository on GitHub
2. Click the **Actions** tab
3. Select the workflow run
4. Scroll to **Artifacts** section at the bottom
5. Download `evaluation-results-[NAME]` artifact
6. Extract and view `evaluation-results.json`

### From PR Comments (if configured)

The debate workflow includes an example that posts results as a PR comment:

```yaml
- name: Comment results on PR
  if: github.event_name == 'pull_request' && always()
  uses: actions/github-script@v7
  with:
    script: |
      # Parse results and post formatted comment
```

You can customize this to format results for your evaluation.

### Understanding Results

Results are in JSON format. Example structure:

```json
{
  "evaluation": "debate",
  "timestamp": "2024-01-15T10:30:00Z",
  "status": "completed",
  "results": {
    "score": 85,
    "reasoning": "Agent demonstrated strong argumentation...",
    "details": {
      "accuracy": 0.92,
      "coherence": 0.88,
      "creativity": 0.81
    }
  }
}
```

**Key fields:**

- `status`: `completed`, `failed`, or `error`
- `score`: Overall score (usually 0-100)
- `reasoning`: Human-readable explanation
- `details`: Breakdown of specific metrics

---

## Troubleshooting

### Common Issues

#### 1. Purple agent container fails to start

**Symptoms:** Container exits immediately or health check fails

**Debugging:**

```bash
# Check container logs
docker logs purple-agent

# Common issues:
# - Missing environment variables (API keys)
# - Port already in use
# - Code errors in agent startup
```

**Solutions:**

- Verify all required environment variables are set
- Check for port conflicts (use different ports if needed)
- Test agent locally outside Docker first
- Check Dockerfile CMD/ENTRYPOINT is correct

#### 2. Containers can't communicate

**Symptoms:** Green agent can't reach purple agent

**Debugging:**

```bash
# Verify both containers are on same network
docker network inspect eval-network

# Try to ping from green agent container
docker exec green-agent curl http://purple-agent:8080/
```

**Solutions:**

- Ensure all containers use `--network eval-network`
- Use container names (not localhost) in URLs
- Check firewall/security settings

#### 3. API key not working

**Symptoms:** Agent errors about authentication or API access

**Debugging:**

Check GitHub Actions logs carefully (secrets are masked):

```
Error: API key is invalid or missing
```

**Solutions:**

- Verify secret is created in GitHub Settings → Secrets
- Check secret name matches exactly in workflow (`secrets.GEMINI_API_KEY`)
- Ensure secret is passed to correct container
- Test with API key locally to confirm it works

#### 4. Evaluation times out

**Symptoms:** Workflow exceeds time limit

**Solutions:**

- Add timeout to workflow:
  ```yaml
  jobs:
    evaluate:
      timeout-minutes: 30  # Adjust as needed
  ```
- Reduce evaluation complexity (fewer rounds, shorter prompts)
- Check if containers are stuck waiting for each other

#### 5. Results file not created

**Symptoms:** Artifact upload fails or file is empty

**Debugging:**

```yaml
- name: Debug - list files
  run: |
    ls -la
    cat evaluation-results.json || echo "File not found"
```

**Solutions:**

- Ensure green agent writes to correct location
- Check green agent logs for errors
- Verify output redirection: `| tee evaluation-results.json`
- Use absolute paths if needed

### Getting Help

If you're stuck:

1. **Check the example:** Review `.github/workflows/eval-debate.yml`
2. **Enable debug logging:** Add this to workflow:
   ```yaml
   env:
     ACTIONS_STEP_DEBUG: true
   ```
3. **Review container logs:** Add log dumps in workflow:
   ```yaml
   - name: Show container logs on failure
     if: failure()
     run: docker logs purple-agent
   ```
4. **Test locally first:** Much faster iteration than waiting for CI

---

## Next Steps

Once your evaluation is working:

1. **Run on every PR:** The workflow will automatically evaluate changes
2. **Track improvements:** Compare scores across PRs and commits
3. **Submit to leaderboard:** (Feature coming soon) Submit your best results to the AgentBeats leaderboard
4. **Add more evaluations:** Create additional workflows for different benchmarks

---

## Quick Reference

### Workflow File Checklist

- [ ] Workflow name is descriptive
- [ ] Path filter includes evaluation directory
- [ ] Green agent image and digest are correct
- [ ] Purple agent image and digest are correct
- [ ] All required secrets are configured in GitHub
- [ ] Container network is created
- [ ] Purple agent containers start with correct environment variables
- [ ] Health checks wait for all containers
- [ ] Green agent command is correct
- [ ] Results are captured to `evaluation-results.json`
- [ ] Cleanup runs even on failure (`if: always()`)
- [ ] Artifact upload is configured

### Useful Commands

```bash
# Get image digest
docker inspect --format='{{index .RepoDigests 0}}' IMAGE_NAME

# Test container locally
docker run --rm -p 8080:8080 -e API_KEY=test IMAGE_NAME

# Check container logs
docker logs CONTAINER_NAME

# Inspect network
docker network inspect eval-network

# Manual cleanup
docker stop $(docker ps -aq) && docker rm $(docker ps -aq)
docker network prune
```

---

## Appendix: Example Workflows

### Simple Single-Agent Evaluation

```yaml
name: Evaluation - QA Test

on:
  pull_request:
    paths:
      - 'evaluations/qa-test/**'
  workflow_dispatch:

jobs:
  evaluate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Pull images
        run: |
          docker pull ghcr.io/agentbeats/green-qa@sha256:abc123...
          docker pull ghcr.io/me/purple-qa@sha256:def456...

      - run: docker network create eval-network

      - name: Start purple agent
        run: |
          docker run -d --name purple-qa --network eval-network \
            -p 8080:8080 -e OPENAI_API_KEY="${{ secrets.OPENAI_API_KEY }}" \
            ghcr.io/me/purple-qa@sha256:def456...

      - name: Wait for health
        run: |
          for i in {1..30}; do
            curl -f http://localhost:8080/health && break
            sleep 2
          done

      - name: Run evaluation
        run: |
          docker run --rm --network eval-network \
            -e AGENT_URL=http://purple-qa:8080 \
            ghcr.io/agentbeats/green-qa@sha256:abc123... \
            | tee results.json

      - if: always()
        run: docker stop purple-qa && docker rm purple-qa

      - uses: actions/upload-artifact@v4
        with:
          name: qa-results
          path: results.json
```

### Multi-Agent Evaluation

See `.github/workflows/eval-debate.yml` for a complete example with multiple purple agent containers.

---

**Need more help?** Check the AgentBeats documentation or open an issue in the repository.
