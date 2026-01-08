# QuickScope Interview Bot

LangGraph-powered bot that conducts structured current-state process interviews and generates Mermaid diagrams + documentation.

## Setup

1. **Install dependencies:**
   ```powershell
   # Using Poetry (recommended)
   poetry install
   
   # Or using pip
   pip install -e .
   ```

2. **Configure environment:**
   ```powershell
   cp .env.example .env
   # Edit .env and add your OPENAI_API_KEY
   ```

3. **Run as a CLI bot (recommended):**
   ```powershell
   # Full flow (SIPOC intake + detailed mapping + outputs)
   poetry run quickscope
   
   # Or with Python directly
   python -m src.cli
   ```

3b. **Quick-start: Skip SIPOC and go straight to detailed mapping:**
   ```powershell
   # Best for getting work done fast
   python quickstart_flow_b.py
   ```
   See [QUICKSTART_FLOW_B.md](QUICKSTART_FLOW_B.md) for details.

4. **Optional: Run in LangGraph Studio (dev UI):**
   ```powershell
   langgraph dev
   ```
   - Open the URL shown in terminal (typically http://localhost:8123)
   - Start a new thread and begin chatting

## Project Structure

```
QuickScope_v2/
├── flows/                      # Flow JSON definitions
│   ├── Flow_A_intake_sipoc_v1.json
│   ├── Flow_B_current_state_mapping_v1.json
│   ├── Flow_C_outputs_v1.json
│   └── composed_master_flow.json
├── src/
│   ├── state/                  # State schema
│   ├── engine/                 # Flow runner
│   ├── actions/                # Action functions
│   ├── nodes/                  # LangGraph nodes
│   └── graphs/                 # Graph definitions
├── tests/
│   ├── unit/
│   └── integration/
├── pyproject.toml
├── langgraph.json
└── .env
```

## Usage

The bot conducts one-question-at-a-time interviews following the flow definitions in `flows/`. It:

1. **Captures engagement context & SIPOC** (Flow A)
2. **Maps detailed workflows & data elements** (Flow B)
3. **Generates outputs** (Flow C): Mermaid SIPOC diagram, swimlane diagram, and markdown summary

State is persisted per `thread_id` so you can pause and resume interviews.

### Watch mode (see what the intake bot does)

Run the CLI with `--watch` to print internal trace events (stage transitions, actions executed, routing decisions):

```powershell
poetry run quickscope --watch
```

### Simulate a realistic user (LLM-as-user) for a 1031 Exchange company

This runs the interview against an LLM persona that responds like an ops user at a 1031 exchange company trying to optimize both downleg + upleg, with today’s reality being email + Excel.

```powershell
# Start fresh and watch every bot step
poetry run quickscope --watch simulate --persona 1031_exchange_ops

# Resume from a saved state at any time
poetry run quickscope --watch --state-file .\my_exchange_state.json simulate --persona 1031_exchange_ops
```

## Testing

```powershell
# Run all tests
pytest

# Run with coverage
pytest --cov=src

# Run specific test file
pytest tests/unit/test_flow_runner.py
```

## Development

See `.cursor/*.mdc` files for LangGraph coding rules and patterns.
