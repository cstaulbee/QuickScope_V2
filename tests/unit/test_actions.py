"""
Unit tests for workflow actions.
"""

import pytest
from src.actions.workflow_actions import (
    initialize_workflow_maps_from_selection,
    write_trigger_to_active_workflow,
    check_step_has_decision,
    update_live_bpmn_artifact,
    commit_step_to_active_workflow,
    advance_or_close_workflow_based_on_response,
    activate_next_workflow_variant_or_finish,
    normalize_and_expand_decision_rules,
    derive_candidate_data_elements_from_workflows_and_artifacts,
    detect_gaps_and_contradictions,
    normalize_decision_text,
    parse_decision_outcomes,
    normalize_and_parse_decision_data,
)
from src.actions.diagram_generation import (
    build_bpmn_lite_mermaid,
    condense_label,
    clear_condense_cache,
    validate_live_flowchart,
    build_fallback_linear_diagram,
    find_step_by_name,
    normalize_step_label,
)


class TestWorkflowActions:
    """Test workflow action functions."""
    
    def test_initialize_workflow_maps_from_selection(self, sample_slots):
        """Test initializing workflow maps from selection."""
        result = initialize_workflow_maps_from_selection(sample_slots)
        
        assert "workflows" in result
        assert "maps" in result["workflows"]
        assert len(result["workflows"]["maps"]) == 2
        assert result["workflows"]["maps"][0]["workflow_name"] == "Standard order"
        assert result["workflow_capture_state"]["active_workflow_id"] == "wf_1"
    
    def test_commit_step_to_active_workflow(self, sample_slots):
        """Test committing a step to active workflow."""
        # Setup
        sample_slots["workflows"]["maps"] = [{
            "workflow_id": "wf_1",
            "workflow_name": "Standard Order",
            "lanes": [],
            "steps": []
        }]
        sample_slots["workflow_capture_state"]["active_workflow_id"] = "wf_1"
        sample_slots["workflow_capture_state"]["active_step_buffer"] = {
            "description": "Pick items",
            "owner_role": "Picker",
            "inputs": ["Pick list"],
            "outputs": ["Picked items"]
        }
        
        result = commit_step_to_active_workflow(sample_slots)
        
        assert len(result["workflows"]["maps"][0]["steps"]) == 1
        assert result["workflows"]["maps"][0]["steps"][0]["description"] == "Pick items"
        assert "Picker" in result["workflows"]["maps"][0]["lanes"]
        assert result["workflow_capture_state"]["active_step_buffer"] == {}
    
    def test_advance_or_close_workflow_done(self, sample_slots):
        """Test closing workflow on 'done' response."""
        # Setup
        sample_slots["workflows"]["maps"] = [{
            "workflow_id": "wf_1",
            "workflow_name": "Standard Order",
            "end_condition": None
        }]
        sample_slots["workflow_capture_state"]["active_workflow_id"] = "wf_1"
        
        result, code = advance_or_close_workflow_based_on_response(
            sample_slots,
            "Process is done when carrier picks up"
        )
        
        assert code == "workflow_closed"
        assert result["workflows"]["maps"][0]["end_condition"] is not None
    
    def test_advance_or_close_workflow_continue(self, sample_slots):
        """Test continuing workflow on non-done response."""
        result, code = advance_or_close_workflow_based_on_response(
            sample_slots,
            "Next we pack the items"
        )
        
        assert code == "continue_same_workflow"
    
    def test_activate_next_workflow_variant(self, sample_slots):
        """Test that variant function always returns all_variants_done (simplified single-workflow mode)."""
        # Setup workflow
        sample_slots["workflows"]["maps"] = [
            {"workflow_id": "wf_1", "workflow_name": "Standard"}
        ]
        sample_slots["workflow_capture_state"]["active_workflow_id"] = "wf_1"
        
        result, code = activate_next_workflow_variant_or_finish(sample_slots)
        
        # Should always return all_variants_done now (single workflow only)
        assert code == "all_variants_done"
    
    def test_activate_next_workflow_all_done(self, sample_slots):
        """Test when all workflows are done (legacy test)."""
        # Setup one workflow as active
        sample_slots["workflows"]["maps"] = [
            {"workflow_id": "wf_1", "workflow_name": "Standard"}
        ]
        sample_slots["workflow_capture_state"]["active_workflow_id"] = "wf_1"
        
        result, code = activate_next_workflow_variant_or_finish(sample_slots)
        
        assert code == "all_variants_done"
    
    def test_normalize_and_expand_decision_rules(self):
        """Test normalizing decision rules."""
        slots = {
            "process_parameters": {
                "decision_rules": [
                    "Approve if value under $1000",
                    "Escalate if missing signature"
                ]
            }
        }
        
        result = normalize_and_expand_decision_rules(slots)
        
        assert len(result["process_parameters"]["decision_rules"]) == 2
        assert result["process_parameters"]["decision_rules"][0]["rule_id"] == "rule_1"
        assert "Approve if value under $1000" in result["process_parameters"]["decision_rules"][0]["decision_point"]
    
    def test_derive_candidate_data_elements(self, sample_slots, sample_workflow):
        """Test deriving data elements from workflows."""
        sample_slots["workflows"]["maps"] = [sample_workflow]
        
        result = derive_candidate_data_elements_from_workflows_and_artifacts(sample_slots)
        
        assert "process_parameters" in result
        assert "data_elements" in result["process_parameters"]
        assert len(result["process_parameters"]["data_elements"]) > 0
    
    def test_detect_gaps_and_contradictions(self, sample_slots):
        """Test detecting gaps and contradictions."""
        # Setup workflow without end_condition
        sample_slots["workflows"]["maps"] = [{
            "workflow_id": "wf_1",
            "workflow_name": "Standard Order",
            "end_condition": None
        }]
        
        # Setup SLA contradiction
        sample_slots["reality_checks"] = {
            "service_levels": {
                "slas_exist": True,
                "sla_definitions": []
            }
        }
        
        result = detect_gaps_and_contradictions(sample_slots)
        
        assert len(result["validation"]["gaps"]) > 0
        assert len(result["validation"]["contradictions"]) > 0
        assert "missing end_condition" in result["validation"]["gaps"][0].lower()
    
    def test_write_trigger_to_active_workflow(self, sample_slots):
        """Test writing trigger to active workflow."""
        # Setup
        sample_slots["workflows"]["maps"] = [{
            "workflow_id": "wf_1",
            "workflow_name": "Standard Order",
            "trigger": None,
            "start_condition": None,
            "end_condition": None
        }]
        sample_slots["workflow_capture_state"]["active_workflow_id"] = "wf_1"
        sample_slots["workflow_capture_state"]["workflow_level_buffer"] = {
            "trigger": "Customer places order",
            "start_condition": "Customer info validated",
            "end_condition": None
        }
        
        result = write_trigger_to_active_workflow(sample_slots)
        
        assert result["workflows"]["maps"][0]["trigger"] == "Customer places order"
        assert result["workflows"]["maps"][0]["start_condition"] == "Customer info validated"
        assert result["workflow_capture_state"]["workflow_level_buffer"] == {}
    
    def test_check_step_has_decision_yes(self, sample_slots):
        """Test checking step has decision (yes case)."""
        sample_slots["workflow_capture_state"]["active_step_buffer"] = {
            "decision": "Is order over $500?"
        }
        
        result, code = check_step_has_decision(sample_slots)
        
        assert code == "has_decision"
        assert result["workflow_capture_state"]["active_step_flags"]["has_decision"] is True
    
    def test_check_step_has_decision_no(self, sample_slots):
        """Test checking step has decision (no case)."""
        sample_slots["workflow_capture_state"]["active_step_buffer"] = {
            "decision": "no"
        }
        
        result, code = check_step_has_decision(sample_slots)
        
        assert code == "no_decision"
        assert result["workflow_capture_state"]["active_step_flags"]["has_decision"] is False
    
    def test_update_live_bpmn_artifact(self, sample_slots, tmp_path):
        """Test updating live BPMN artifact."""
        import os
        # Change to tmp directory for test
        original_cwd = os.getcwd()
        os.chdir(tmp_path)
        
        try:
            # Setup
            sample_slots["workflows"]["maps"] = [{
                "workflow_id": "wf_1",
                "workflow_name": "Standard Order",
                "trigger": "Customer places order",
                "start_condition": "Customer validated",
                "end_condition": "Order shipped",
                "steps": [
                    {
                        "description": "Pick items",
                        "owner_role": "Picker",
                        "inputs": ["Pick list"],
                        "outputs": ["Picked items"],
                        "decision": None
                    }
                ]
            }]
            sample_slots["workflow_capture_state"]["active_workflow_id"] = "wf_1"
            
            result = update_live_bpmn_artifact(sample_slots)
            
            assert "live_diagram_path" in result["workflow_capture_state"]
            artifact_path = result["workflow_capture_state"]["live_diagram_path"]
            assert artifact_path == "artifacts/live_bpmn_wf_1.mmd"
            
            # Check file was created
            full_path = tmp_path / artifact_path
            assert full_path.exists()
            
            # Check content
            content = full_path.read_text(encoding="utf-8")
            assert "flowchart TD" in content
            assert "Customer places order" in content
            assert "Pick items" in content
        finally:
            os.chdir(original_cwd)
    
    def test_build_bpmn_lite_mermaid_basic(self):
        """Test building basic BPMN-lite Mermaid diagram."""
        workflow_map = {
            "workflow_id": "wf_1",
            "workflow_name": "Test Process",
            "trigger": "Start event",
            "end_condition": "Done",
            "steps": [
                {
                    "description": "Step 1",
                    "owner_role": "User",
                    "decision": None
                }
            ]
        }
        
        result = build_bpmn_lite_mermaid(workflow_map)
        
        assert "flowchart TD" in result
        assert "wf_1_start" in result
        assert "Start event" in result
        assert "Step 1" in result
        assert "wf_1_end" in result
    
    def test_build_bpmn_lite_mermaid_with_decision(self):
        """Test building BPMN-lite with decision gateway."""
        workflow_map = {
            "workflow_id": "wf_1",
            "workflow_name": "Test Process",
            "trigger": "Start",
            "end_condition": "End",
            "steps": [
                {
                    "description": "Check approval",
                    "owner_role": "Manager",
                    "decision_normalized": "Is approved?",
                    "decision_outcomes_parsed": [
                        {"label": "Approved", "next_ref": "proceed", "target_type": "next"},
                        {"label": "Rejected", "next_ref": "stop", "target_type": "end"}
                    ]
                }
            ]
        }
        
        result = build_bpmn_lite_mermaid(workflow_map, use_llm_condense=False)
        
        assert "{Is approved?" in result
        assert "decision" in result
        assert "Approved" in result or "Rejected" in result


class TestDecisionParsing:
    """Test decision text normalization and outcome parsing."""
    
    def test_normalize_decision_text_with_yes_prefix(self):
        """Test normalizing decision text that starts with 'Yes'."""
        result = normalize_decision_text("Yes, the decision is: Is the order approved?")
        assert result == "Is the order approved?"
    
    def test_normalize_decision_text_no_prefix(self):
        """Test normalizing decision text without prefix."""
        result = normalize_decision_text("Is the client satisfied?")
        assert result == "Is the client satisfied?"
    
    def test_normalize_decision_text_adds_question_mark(self):
        """Test that question mark is added if missing."""
        result = normalize_decision_text("Does the item pass inspection")
        assert result == "Does the item pass inspection?"
    
    def test_normalize_decision_text_empty(self):
        """Test normalizing empty text."""
        result = normalize_decision_text("")
        assert result == ""
    
    def test_parse_decision_outcomes_standard_format(self):
        """Test parsing outcomes in standard format."""
        text = """Approved -> Next: Ship order
Rejected -> End: Cancel order
Needs info -> Next: Request documents"""
        
        results = parse_decision_outcomes(text)
        
        assert len(results) == 3
        assert results[0]["label"] == "Approved"
        assert results[0]["next_ref"] == "Ship order"
        assert results[0]["target_type"] == "next"
        
        assert results[1]["label"] == "Rejected"
        assert results[1]["next_ref"] == "Cancel order"
        assert results[1]["target_type"] == "end"
        
        assert results[2]["label"] == "Needs info"
        assert results[2]["next_ref"] == "Request documents"
        assert results[2]["target_type"] == "next"
    
    def test_parse_decision_outcomes_freeform(self):
        """Test parsing freeform outcome text."""
        text = "Approved → moves to shipping\nRejected → returns to requester"
        
        results = parse_decision_outcomes(text)
        
        assert len(results) == 2
        assert results[0]["label"] == "Approved"
        assert "shipping" in results[0]["next_ref"].lower()
        assert results[0]["target_type"] == "next"
    
    def test_parse_decision_outcomes_empty(self):
        """Test parsing empty outcomes."""
        results = parse_decision_outcomes("")
        assert results == []
    
    def test_normalize_and_parse_decision_data(self):
        """Test full normalization and parsing action."""
        slots = {
            "workflow_capture_state": {
                "active_step_buffer": {
                    "decision": "Yes, the decision is: Is it approved?",
                    "decision_outcomes": "Approved -> Next: Ship\nRejected -> End: Cancel"
                }
            }
        }
        
        result = normalize_and_parse_decision_data(slots)
        
        buffer = result["workflow_capture_state"]["active_step_buffer"]
        assert buffer["decision_normalized"] == "Is it approved?"
        assert len(buffer["decision_outcomes_parsed"]) == 2
        assert buffer["decision_outcomes_parsed"][0]["label"] == "Approved"


class TestDiagramGeneration:
    """Test diagram generation with branching and validation."""
    
    def setup_method(self):
        """Clear cache before each test."""
        clear_condense_cache()
    
    def test_condense_label_short_text(self):
        """Test condensing text that's already short enough."""
        result = condense_label("Short text", max_length=60)
        assert result == "Short text"
    
    def test_condense_label_long_text(self):
        """Test condensing long text."""
        long_text = "This is a very long text that should be condensed because it exceeds the maximum length"
        result = condense_label(long_text, max_length=50)
        assert len(result) <= 50
    
    def test_condense_label_caching(self):
        """Test that condensing uses cache."""
        text = "Some text to condense"
        result1 = condense_label(text, max_length=10, context="test")
        result2 = condense_label(text, max_length=10, context="test")
        # Should return same result from cache
        assert result1 == result2
    
    def test_validate_live_flowchart_valid(self):
        """Test validation of a valid flowchart."""
        mermaid = """flowchart TD
    start([Start])
    step1[Task 1]
    decision{Question?}
    end1([End])
    
    start --> step1
    step1 --> decision
    decision -->|Yes| end1
    decision -->|No| end1"""
        
        is_valid, error = validate_live_flowchart(mermaid)
        assert is_valid
        assert error is None
    
    def test_validate_live_flowchart_missing_flowchart(self):
        """Test validation fails without 'flowchart' declaration."""
        mermaid = """graph TD
    start([Start])"""
        
        is_valid, error = validate_live_flowchart(mermaid)
        assert not is_valid
        assert "flowchart" in error.lower()
    
    def test_validate_live_flowchart_with_ellipsis(self):
        """Test validation fails with truncation ellipses."""
        mermaid = """flowchart TD
    start([Start...])
    step1["Long text..."]"""
        
        is_valid, error = validate_live_flowchart(mermaid)
        assert not is_valid
        assert "truncated" in error.lower()
    
    def test_validate_live_flowchart_decision_one_edge(self):
        """Test validation fails for decision with <2 edges."""
        mermaid = """flowchart TD
    start([Start])
    decision{Question?}
    end1([End])
    
    start --> decision
    decision --> end1"""
        
        is_valid, error = validate_live_flowchart(mermaid)
        assert not is_valid
        assert "fewer than 2" in error.lower()
    
    def test_normalize_step_label(self):
        """Test step label normalization."""
        assert normalize_step_label("Ship Order") == "ship order"
        assert normalize_step_label("Check-in: Process") == "checkin process"
        assert normalize_step_label("  Multiple   Spaces  ") == "multiple spaces"
    
    def test_find_step_by_name_exact_match(self):
        """Test finding step by exact name match."""
        steps = [
            {"step_name": "Receive order"},
            {"step_name": "Ship order"},
            {"step_name": "Close order"}
        ]
        
        result = find_step_by_name("Ship order", steps)
        assert result == "step2"
    
    def test_find_step_by_name_fuzzy_match(self):
        """Test finding step by fuzzy match."""
        steps = [
            {"step_name": "Receive customer order"},
            {"step_name": "Ship the order out"},
        ]
        
        # Should match "Ship the order out" because it has higher word overlap
        # Both have "order", but second has "ship" which is more specific
        result = find_step_by_name("Ship", steps)
        assert result == "step2"
    
    def test_find_step_by_name_no_match(self):
        """Test finding step when no match exists."""
        steps = [
            {"step_name": "Receive order"},
            {"step_name": "Ship order"},
        ]
        
        result = find_step_by_name("Process payment", steps)
        assert result is None
    
    def test_build_bpmn_with_parsed_outcomes(self):
        """Test building diagram with parsed decision outcomes."""
        workflow_map = {
            "workflow_id": "wf_1",
            "workflow_name": "Test",
            "trigger": "Start",
            "end_condition": "Done",
            "steps": [
                {
                    "step_name": "Check approval",
                    "owner_role": "Manager",
                    "decision_normalized": "Is it approved?",
                    "decision_outcomes_parsed": [
                        {"label": "Approved", "next_ref": "Ship order", "target_type": "next"},
                        {"label": "Rejected", "next_ref": "Cancelled", "target_type": "end"}
                    ]
                },
                {
                    "step_name": "Ship order",
                    "owner_role": "Shipper"
                }
            ]
        }
        
        result = build_bpmn_lite_mermaid(workflow_map, use_llm_condense=False)
        
        assert "flowchart TD" in result
        assert "Is it approved?" in result
        assert "Approved" in result
        assert "Rejected" in result
        # Should link approved to Ship order step
        assert "wf_1_step2" in result
    
    def test_build_bpmn_with_placeholder(self):
        """Test building diagram with placeholder for unresolved next step."""
        workflow_map = {
            "workflow_id": "wf_1",
            "workflow_name": "Test",
            "trigger": "Start",
            "end_condition": "Done",
            "steps": [
                {
                    "step_name": "Check status",
                    "decision_normalized": "Is complete?",
                    "decision_outcomes_parsed": [
                        {"label": "Yes", "next_ref": "Unknown step", "target_type": "next"},
                        {"label": "No", "next_ref": "Wait", "target_type": "next"}
                    ]
                }
            ]
        }
        
        result = build_bpmn_lite_mermaid(workflow_map, use_llm_condense=False)
        
        assert "Pending:" in result
        assert "Unknown step" in result
    
    def test_build_fallback_linear_diagram(self):
        """Test building fallback linear diagram."""
        workflow_map = {
            "workflow_id": "wf_1",
            "workflow_name": "Test",
            "trigger": "Start here",
            "end_condition": "End here",
            "steps": [
                {
                    "step_name": "Step 1",
                    "owner_role": "User",
                    "decision_normalized": "Is approved?"
                },
                {
                    "step_name": "Step 2",
                    "owner_role": "Admin"
                }
            ]
        }
        
        result = build_fallback_linear_diagram(workflow_map)
        
        assert "flowchart TD" in result
        assert "Step 1" in result
        assert "Step 2" in result
        # Should have decision as note
        assert "Decision:" in result or "note" in result.lower()
        # Should be linear (no decision gateway)
        assert "{" not in result  # No decision gateway syntax

