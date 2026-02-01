# AI-Powered Analysis Agent

The pipeline now includes an optional AI analyzer agent that uses external AI services (OpenAI GPT-4 mini or Claude) to provide deeper insights for CAD engineers.

## Setup

### 1. Install Dependencies

```bash
cd cad_view_agents
pip install openai anthropic python-dotenv
```

Or install from requirements.txt (if you update it to include these packages).

### 2. Configure API Keys

Create a `.env` file in the `cad_view_agents` directory:

```bash
# Enable AI analysis
CAD_USE_AI_ANALYSIS=true

# Choose provider: "openai" or "claude"
CAD_AI_PROVIDER=openai

# Add your API key (use the one matching your provider)
OPENAI_API_KEY=sk-your-key-here
# OR
ANTHROPIC_API_KEY=sk-ant-your-key-here
```

### 3. Load Environment Variables

Update `run.py` or set environment variables before running:

```bash
export CAD_USE_AI_ANALYSIS=true
export CAD_AI_PROVIDER=openai
export OPENAI_API_KEY=sk-your-key-here
./run_freecad.sh "/path/to/file.step"
```

Or add to `run_freecad.sh`:
```bash
source .env 2>/dev/null || true
```

## Features

The AI analyzer provides:

1. **Design Assessment** - Identifies likely use case and component type
2. **Manufacturing Considerations** - Insights about fabrication methods
3. **Design Quality** - Observations about geometry complexity
4. **View Recommendations** - Validation and suggestions for views
5. **Potential Issues** - Design concerns or areas to review

## Output

AI analysis is included in:
- `summary.json` - Under `ai_analysis` field
- `trace.json` - As `ai_analyzer_agent` entry

## Costs

- **OpenAI GPT-4 mini**: ~$0.15 per 1M input tokens, ~$0.60 per 1M output tokens
- **Claude 3.5 Sonnet**: ~$3 per 1M input tokens, ~$15 per 1M output tokens

For typical CAD analysis, expect ~$0.001-0.01 per file analysis with GPT-4 mini.

## Disabling

Set `CAD_USE_AI_ANALYSIS=false` or don't set the environment variable to disable AI analysis.
