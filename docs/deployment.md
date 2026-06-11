# Deployment Guide

## Prerequisites

- Python 3.12+
- Git
- GitHub account with repository access
- Google Gemini API key (free tier available: https://aistudio.google.com/apikey)
- GitHub Personal Access Token (optional, increases API rate limits)

## Quick Start

### 1. Clone and Setup

```bash
git clone https://github.com/yourusername/open-source-radar.git
cd open-source-radar

python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your API keys
```

Required configuration:
```ini
GEMINI_API_KEY=your_gemini_api_key_here
GITHUB_TOKEN=your_github_token_here
```

### 3. Run Locally

```bash
# Dry run (no publishing)
python -m src.main

# With publishing (requires GITHUB_TOKEN)
LOG_LEVEL=INFO python -m src.main
```

### 4. Run Tests

```bash
pytest tests/ -v

# With coverage
pytest tests/ -v --cov=src --cov-report=term-missing
```

## Production Deployment

### Option A: GitHub Actions (Recommended)

The pipeline runs daily via GitHub Actions. Setup:

1. **Add secrets to your repository:**
   - `Settings → Secrets and variables → Actions`
   - Add `GEMINI_API_KEY`
   - Add `GITHUB_TOKEN` (if needed)

2. **Workflows are already included:**
   - `.github/workflows/daily_update.yml` - Runs daily at 6 AM UTC
   - `.github/workflows/weekly_maintenance.yml` - Runs every Monday
   - `.github/workflows/ci.yml` - Runs on every push

3. **Enable workflows:**
   - Go to Actions tab in your repository
   - Enable the workflows

### Option B: Self-Hosted Server

For more control or higher volumes:

```bash
# Systemd service file
cat > /etc/systemd/system/open-source-radar.service << EOF
[Unit]
Description=Open Source Radar Pipeline
After=network.target

[Service]
Type=oneshot
User=radar
WorkingDirectory=/opt/open-source-radar
Environment=PYTHONPATH=/opt/open-source-radar/src
ExecStart=/opt/open-source-radar/.venv/bin/python -m src.main
StandardOutput=journal

[Install]
WantedBy=multi-user.target
EOF

# Timer for daily execution
cat > /etc/systemd/system/open-source-radar.timer << EOF
[Unit]
Description=Run Open Source Radar Daily
Requires=open-source-radar.service

[Timer]
OnCalendar=daily
Persistent=true

[Install]
WantedBy=timers.target
EOF
```

### Option C: Docker (Coming Soon)

```dockerfile
FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
CMD ["python", "-m", "src.main"]
```

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GEMINI_API_KEY` | Yes | - | Google Gemini API key |
| `GITHUB_TOKEN` | No | - | GitHub personal access token |
| `GITHUB_REPO` | No | repo URL | Target GitHub repository |
| `LOG_LEVEL` | No | INFO | Logging level (DEBUG, INFO, WARNING, JSON) |
| `DRY_RUN` | No | false | Run without publishing |
| `AI_EVALUATION_ENABLED` | No | true | Enable/disable AI evaluation |
| `AI_PROVIDER` | No | gemini | AI provider (gemini, openai, anthropic) |
| `OPENAI_API_KEY` | No | - | OpenAI API key |
| `ANTHROPIC_API_KEY` | No | - | Anthropic API key |
| `REDDIT_CLIENT_ID` | No | - | Reddit API credentials |
| `REDDIT_CLIENT_SECRET` | No | - | Reddit API credentials |
| `MAX_IDEAS_PER_SOURCE` | No | 100 | Max ideas to collect per source |
| `REQUESTS_PER_SECOND` | No | 2.0 | API rate limit |

## Monitoring

### GitHub Actions Dashboard
- View workflow runs at `https://github.com/yourusername/open-source-radar/actions`
- Check daily update status
- Review logs for failures

### Local Logs
Logs are written to `logs/` directory with structured JSON format.

### Alerts
When thresholds are exceeded, GitHub issues are automatically created in the repository.

## Troubleshooting

### API Rate Limits
- GitHub: 60 req/hour (unauthenticated), 5000 req/hour (authenticated)
- Reddit: 60 req/minute
- Hacker News: No official limit, but be respectful

### Common Issues

**"No module named 'src'"**
```bash
export PYTHONPATH=/path/to/open-source-radar:$PYTHONPATH
```

**"Gemini API key not configured"**
```bash
# Ensure .env file exists with GEMINI_API_KEY set
```

**"GitHub publish failed"**
```bash
# Ensure GITHUB_TOKEN has repo scope
# Check repository exists and is accessible
```

**Tests failing**
```bash
# Ensure all dependencies are installed
pip install -r requirements.txt
pip install pytest pytest-asyncio pytest-cov
```
