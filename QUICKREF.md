# QuickScope Interview Bot - Quick Reference

## Development Commands

### Setup
```powershell
# Run setup script
.\setup.ps1

# Or manually with Poetry
poetry install

# Or manually with pip
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -e .
```

### Running the Bot
```powershell
# Run as a CLI bot (recommended)
poetry run quickscope
# Or:
python -m src.cli

# Optional: start LangGraph development server (Studio UI)
langgraph dev
```

### Testing
```powershell
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/unit/test_flow_runner.py

# Run specific test
pytest tests/unit/test_flow_runner.py::TestFlowLoader::test_load_flow_intake_sipoc
```

### Code Quality
```powershell
# Format code
black src tests

# Lint code
ruff src tests

# Type checking (if mypy is installed)
mypy src
```

## Project Structure

```
QuickScope_v2/
├── flows/                          # Flow JSON definitions
│   ├── Flow_A_intake_sipoc_v1.json
│   ├── Flow_B_current_state_mapping_v1.json
│   ├── Flow_C_outputs_v1.json
│   └── composed_master_flow.json
├── src/
│   ├── state/
│   │   └── interview_state.py      # State schema
│   ├── engine/
│   │   └── flow_runner.py          # Flow loader, template renderer, stage advancer
│   ├── actions/
│   │   ├── workflow_actions.py     # Deterministic actions
│   │   └── output_generation.py    # LLM-driven output generation
│   ├── nodes/
│   │   └── interview_nodes.py      # Graph node implementations
│   └── graphs/
│       └── interview_graph.py      # Graph definition (exported for langgraph.json)
├── tests/
│   ├── conftest.py                 # Test fixtures
│   ├── unit/
│   │   ├── test_flow_runner.py
│   │   ├── test_actions.py
│   │   └── test_output_generation.py
│   └── integration/
│       └── test_interview_graph.py
├── pyproject.toml                  # Dependencies
├── langgraph.json                  # LangGraph config
├── .env                            # Environment variables (create from env.example)
├── README.md
└── setup.ps1                       # Setup script
```

## Flow Architecture

### Flow A: Intake + SIPOC
- Captures engagement context
- Defines process profile
- Establishes scope boundaries
- Captures high-level SIPOC

### Flow B: Current State Mapping
- Reality checks (cycle time, lead time, wait states)
- Artifacts inventory
- Pain points capture
- Detailed workflow mapping (step-by-step)
- Data elements derivation and validation
- Status model and transitions
- Controls and measures
- Consistency validation

### Flow C: Outputs
- Automation fit assessment (optional)
- Generate Mermaid SIPOC diagram
- Generate Mermaid swimlane diagram
- Generate markdown summary

## How the Bot Works

### Turn-by-Turn Flow
1. **User sends message** → Graph invoked with thread_id
2. **load_flow** → Initialize slots if new session
3. **ingest_user_answer** → Write answer to slots
4. **auto_advance** → Process automatic stages (message/action/gate) until hitting a question/confirm
5. **render_prompt** → Generate next question/confirm
6. **Return to user** → Wait for next message

### State Persistence
- Uses checkpointer (MemorySaver for dev, PostgreSQL for production)
- State persists per thread_id
- Can pause and resume interviews

### Cycle Protection
- `max_auto_advance_steps` (default: 50)
- Prevents infinite loops
- Fails gracefully with error message

## Key Design Patterns

### State (minimal typed)
- Only what must persist
- TypedDict for schema
- Reducers for accumulation (messages)

### Nodes (single responsibility)
- Pure functions where possible
- Async for I/O, sync for CPU
- Error handling at each node

### Edges (explicit routing)
- Simple edges for linear flow
- Conditional edges for branching
- No implicit cycles

### Actions (deterministic)
- No LLM calls in actions (except output_generation)
- Idempotent where possible
- Return updated slots

## Extending the Bot

### Adding a New Flow
1. Create `flows/Flow_X_name.json`
2. Define stages, questions, actions
3. Update FlowLoader with new flow_id mapping
4. Test with `pytest`

### Adding a New Action
1. Implement function in `src/actions/workflow_actions.py`
2. Add to ACTIONS registry
3. Add unit test in `tests/unit/test_actions.py`
4. Reference in flow JSON

### Adding a New Stage Type
1. Update `auto_advance_node` in `src/nodes/interview_nodes.py`
2. Update `StageAdvancer.get_next_stage` in `src/engine/flow_runner.py`
3. Add tests

## Troubleshooting

### Bot not asking questions
- Check `active_stage_id` in state
- Verify stage type is "questions" or "confirm"
- Check `pending` is set correctly

### Answers not saving
- Verify `save_to` path in pending question
- Check SlotWriter is creating structure correctly
- Use pytest to test SlotWriter directly

### Auto-advance not stopping
- Check max_auto_advance_steps limit
- Verify question/confirm stages have type set correctly
- Look for infinite loops in flow JSON

### LLM output generation failing
- Check OPENAI_API_KEY in .env
- Verify slots have required data
- Check MermaidValidator for validation errors
- Look at retry logic in output_generation.py

## Environment Variables

```
# Required
OPENAI_API_KEY=sk-...

ENVIRONMENT=dev
DEBUG=true
MAX_AUTO_ADVANCE_STEPS=50
DEFAULT_FLOW_ID=intake_sipoc_v1
```

## LangGraph Studio Tips

1. **Thread ID**: Each thread is an independent session
2. **State Inspection**: Click "State" tab to see current state
3. **Checkpointer**: State persists across refreshes
4. **Testing**: Use different thread IDs for different test scenarios
5. **Debugging**: Check "Logs" tab for node execution details

## Production Deployment

### Switch to PostgreSQL Checkpointer
```python
from langgraph.checkpoint.postgres import PostgresSaver

checkpointer = PostgresSaver.from_conn_string(
    "postgresql://user:pass@host:5432/dbname"
)
```

### Docker Deployment
See `.cursor/langgraph-deployment.mdc` for Docker configuration examples.
