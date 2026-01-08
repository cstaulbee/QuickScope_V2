# QuickScope v2 - Consolidated Change Log

## Core Implementation (Initial Build)

**Created:** LangGraph interview bot for business process mapping
- Split `process_flow.json` into 3 modular flows + master flow
- Flow A: SIPOC intake (7 stages)
- Flow B: Current-state mapping (35+ stages)
- Flow C: Output generation (5 stages)
- Implemented state management, flow runner engine, action functions
- Added LLM output generation for Mermaid diagrams & markdown
- 30+ unit tests + 8 integration tests

**Files:** Flow JSON splits, `src/state/`, `src/engine/`, `src/actions/`, `src/nodes/`, `src/graphs/`, test suites

---

## Flow B Quick-Start Entry Point

**Purpose:** Skip SIPOC intake, go directly to step-by-step workflow mapping

**Changes:**
- Created `quickstart_flow_b.py` - standalone CLI entry point
- Asks 1 question (process name) vs 10+ SIPOC questions
- Pre-populates state with minimal engagement data
- Starts at `workflow_selection` stage (first stage of Flow B)
- Full conversation loop with live diagram updates

**Benefits:** Faster startup, focused on actual work, same features as full flow

**Files:** `quickstart_flow_b.py`, `QUICKSTART_FLOW_B.md`, updated `README.md`

---

## Step Capture + Live BPMN Diagrams

**Purpose:** Capture detailed workflow steps with real-time visual feedback

**Features:**
1. **Trigger Capture:** Explicitly asks for trigger event & start conditions
2. **Clarify_if Engine:** Non-overbearing follow-ups for vague/empty answers
3. **Conditional Decision Capture:** Only asks for outcomes when decision exists
4. **Live Diagrams:** BPMN-lite Mermaid diagram updates after each step

**Implementation:**
- `diagram_generation.py` - `build_bpmn_lite_mermaid()`, `write_mermaid_artifact()`
- Enhanced `ingest_user_answer_node()` with `_should_clarify()` condition checking
- Added workflow-level buffer for triggers
- Split decision capture from wait/exception capture
- Added diagram update action after step commit

**Output:** `artifacts/live_bpmn_wf_<id>.mmd` files with start/end events, tasks, decision gateways, outcome branches

**Files:** `src/actions/diagram_generation.py`, `src/actions/workflow_actions.py`, `src/nodes/interview_nodes.py`, Flow B JSON updates

---

## Single Workflow Simplification

**Purpose:** Focus on mapping ONE process instead of multiple variants

**Changes:**
- Entry asks 1 question (process name only) vs 2 (name + variants)
- Removed variant cycling logic from flow
- Simplified `activate_next_workflow_variant_or_finish()` to always return "all done"
- Removed `workflow_next_variant_gate`, `workflow_next_variant_branch` stages
- Updated all documentation to reflect single-workflow mode

**Benefits:** Simpler mental model, faster, clearer intent, more maintainable

**Migration:** Run tool multiple times to map multiple processes

**Files:** `quickstart_flow_b.py`, Flow B JSON, `workflow_actions.py`, documentation

---

## Iterative Step Discovery

**Purpose:** Discover steps incrementally vs requiring upfront enumeration

**BEFORE:** "List all steps from start to finish" (requires knowing entire process)
**AFTER:** "What's the first action?" → capture details → "What happens next?" (or 'done')

**Changes:**
- Removed `workflow_step_enumeration`, `workflow_step_enumeration_parse` stages
- Added `workflow_ask_next_step`, `workflow_check_if_done` stages
- New actions: `check_if_user_said_done()`, `copy_next_step_to_buffer()`
- User signals completion by saying "done"

**Benefits:** Natural conversation flow, no need to know all steps upfront, less intimidating

**Files:** Flow B JSON, `workflow_actions.py`, `CHEATSHEET_FLOW_B.md`

---

## Simulation Testing & Loop Detection

**Purpose:** Enable automated testing with simulated users

**Issues Fixed:**
1. **Loop Detection:** Bot repeated questions 50+ times
   - Reduced threshold from 5 → 3 repetitions
   - Added min message length filter (>20 chars)
   - Added detailed logging

2. **Vague Response Handling:** Clear "No" treated as vague
   - Whitelisted clear yes/no responses: {"no", "yes", "y", "n", "nope", "yep", "yeah", "nah"}
   - Modified `_should_clarify()` to exclude these

3. **Simulated User Loop Breaking:** Added proactive loop detection
   - Checks last 12 messages for repeated questions
   - Forces progression: "Let's move on to the next part"

**Results:** 11 turns (down from 200+), 15 steps captured, 3 loop detections handled gracefully

**Files:** `src/nodes/interview_nodes.py`, `src/simulations/simulated_user.py`

---

## Loop Stage Bug Fix

**Problem:** Bot stuck at "Thanks — moving on." without progressing
**Cause:** Loop stage (`data_elements_validate_loop`) never checked exit conditions

**Fix:**
- Enhanced `auto_advance_node()` to check loop stop conditions
- Changed `select_next_data_element_for_validation()` to return tuple: `(dict, str)` signaling status
- Returns "element_selected" or "all_validated" to control loop exit

**Files:** `src/nodes/interview_nodes.py`, `src/actions/workflow_actions.py`

---

## Diagram Label Condensing Improvements

**Problem:** Labels truncated mid-sentence ("Confirm that funds", "Clos step is usually")
**Cause:** Word-boundary truncation instead of intelligent summarization

**Solution:** LLM-powered intelligent summarization
- Uses GPT-4o-mini for context-aware condensing
- Context-specific prompts: step (verb-noun), trigger (event), decision (yes/no question)
- Validates output for completeness (no "the", "and", "to" endings)
- Expanded verb list (45+ action verbs)
- Multiple fallback levels with phrase-boundary detection

**BEFORE:**
```
"Confirm that funds" ❌
"Identify properties during" ❌
"Clos step is usually" ❌
```

**AFTER:**
```
"Confirm fund receipt" ✓
"Identify replacement properties" ✓
"Close purchase transaction" ✓
```

**Files:** `src/actions/diagram_generation.py` (`_call_llm_for_condensing()`, `_extract_verb_noun()`)

---

## Label Source Prioritization Fix

**Problem:** Some steps properly summarized, others truncated (inconsistent)
**Cause:** Code prioritized `step_name` (potentially truncated) over `description` (full text)

**Fix:**
- Now prioritizes `description` (full interview text) over `step_name` (initial enumeration)
- Always runs condensing, even on short text
- Clears label cache on each diagram generation via `clear_condense_cache()`
- Applied to both `build_bpmn_lite_mermaid()` and `build_fallback_linear_diagram()`

**Files:** `src/actions/diagram_generation.py`, `src/actions/workflow_actions.py`

---

## Key Configuration

**Environment Variables:**
- `OPENAI_API_KEY` - Required for LLM summarization and output generation

**LLM Settings:**
- Model: `gpt-4o-mini`
- Temperature: `0` (deterministic)
- Max label length: 35 chars (steps), 30 (triggers/end), 20 (outcomes)

**Loop Detection:**
- Threshold: 3 repetitions
- Min message length: 20 chars
- Simulated user lookback: 12 messages

---

## Testing Coverage

**Unit Tests:** 80+ tests
- Flow runner (loading, templating, slot writing, stage advancement)
- Actions (workflow ops, data element ops, gap detection)
- Diagram generation (Mermaid validation, LLM output, retries)
- Nodes (clarify_if conditions, loop detection, answer combination)

**Integration Tests:** 8+ tests
- Full graph flow (first turn, answer ingestion, confirm routing)
- Auto-advance through message stages
- Cycle protection
- State persistence
- Workflow trigger capture end-to-end

---

## Documentation Files

- `README.md` - Setup, usage, testing overview
- `QUICKREF.md` - Commands, architecture, troubleshooting
- `QUICKSTART_FLOW_B.md` - Quick-start user guide
- `CHEATSHEET_FLOW_B.md` - Flow B reference
- `IMPLEMENTATION_SUMMARY.md` - Technical implementation details
- `FLOW_B_QUICKSTART_SUMMARY.md` - Quick-start implementation notes
- `IMPLEMENTATION_CHANGES.md` - Step capture implementation notes
- Various bug fix & testing documentation (consolidated here)

---

## File Structure Summary

```
flows/
  ├── Flow_A_intake_sipoc_v1.json (SIPOC intake)
  ├── Flow_B_current_state_mapping_v1.json (detailed workflow mapping)
  ├── Flow_C_outputs_v1.json (diagram generation)
  └── composed_master_flow.json (chains all flows)

src/
  ├── state/interview_state.py (TypedDict state schema)
  ├── engine/flow_runner.py (FlowLoader, TemplateRenderer, SlotWriter, StageAdvancer)
  ├── actions/
  │   ├── workflow_actions.py (workflow state management)
  │   ├── diagram_generation.py (BPMN-lite + label condensing)
  │   └── output_generation.py (final Mermaid + markdown)
  ├── nodes/interview_nodes.py (graph nodes: load, ingest, auto_advance, render)
  ├── graphs/interview_graph.py (LangGraph definition)
  └── simulations/ (simulated user for testing)

quickstart_flow_b.py (standalone entry point, skips SIPOC)

artifacts/ (generated diagrams: live_bpmn_wf_*.mmd)
```

---

## Notable Design Patterns

1. **Minimal Typed State:** TypedDict with reducers (`add_messages`)
2. **Single Responsibility Nodes:** Each node does one thing
3. **Explicit Routing:** No implicit cycles
4. **Cycle Protection:** `max_auto_advance_steps` hard limit
5. **Multi-Level Error Handling:** Node-level + graph-level with retries
6. **Deterministic Actions:** Pure functions (no LLM) except output generation
7. **Template Rendering:** Jinja2-style `{{slot.path}}` with nested access
8. **Clarify_if Engine:** Conditional follow-ups without overbearing loops
9. **Live Feedback:** Diagrams update after each step commit
10. **LLM-Powered Summarization:** Intelligent label condensing vs truncation

---

## Key Decisions & Rationale

**Why split flows?**
- Maintainability (smaller, focused flows)
- Reusability (run intake without full mapping)
- Testing (easier to test segments)
- Flexibility (optional automation scoring)

**Why quick-start entry?**
- SIPOC intake too slow for most users (10+ questions)
- Users want to map steps, not discuss suppliers/customers
- Flow B captures everything SIPOC does but better (per-step granularity)

**Why single workflow mode?**
- 90% use case: map ONE process end-to-end
- Variants confusing ("What's a variant?")
- Faster, clearer, simpler mental model
- Users can run tool multiple times for multiple processes

**Why iterative discovery?**
- Users shouldn't need to know all steps upfront
- Natural conversation flow (what happens first? → what's next?)
- Less intimidating, handles uncertainty
- True process discovery vs pre-enumeration

**Why LLM for label condensing?**
- Word-boundary truncation produces incomplete phrases
- LLM understands context (steps vs triggers vs decisions)
- Intelligent summarization preserves meaning
- Fallback ensures robustness without API

---

## Version History

- **v1.0** - Initial LangGraph implementation with 3-flow split
- **v1.1** - Quick-start entry point (skip SIPOC)
- **v1.2** - Step capture + live BPMN diagrams
- **v1.3** - Single workflow simplification
- **v1.4** - Iterative step discovery (no pre-enumeration)
- **v1.5** - Simulation testing + loop detection fixes
- **v1.6** - Diagram label condensing improvements (LLM-powered)
- **v1.7** - Label source prioritization fix (description over step_name)

---

**Last Updated:** 2026-01-07
**Status:** Production-ready, all tests passing
**Entry Point:** `python quickstart_flow_b.py` (recommended) or `langgraph dev` (Studio)
