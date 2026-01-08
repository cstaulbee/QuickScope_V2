"""
Unit tests for flow runner engine.
"""

import pytest
from src.engine.flow_runner import (
    FlowLoader,
    TemplateRenderer,
    SlotWriter,
    StageAdvancer,
    FlowRunnerError
)


class TestFlowLoader:
    """Test FlowLoader class."""
    
    def test_load_flow_intake_sipoc(self):
        """Test loading intake_sipoc flow."""
        loader = FlowLoader()
        flow = loader.load_flow("intake_sipoc_v1")
        
        assert flow["flow_id"] == "intake_sipoc_v1"
        assert "stages" in flow
        assert len(flow["stages"]) > 0
    
    def test_load_flow_unknown(self):
        """Test loading unknown flow raises error."""
        loader = FlowLoader()
        
        with pytest.raises(FlowRunnerError):
            loader.load_flow("unknown_flow_xyz")
    
    def test_get_stage(self):
        """Test getting a specific stage."""
        loader = FlowLoader()
        stage = loader.get_stage("intake_sipoc_v1", "welcome")
        
        assert stage["id"] == "welcome"
        assert stage["type"] == "message"
    
    def test_get_stage_not_found(self):
        """Test getting non-existent stage raises error."""
        loader = FlowLoader()
        
        with pytest.raises(FlowRunnerError):
            loader.get_stage("intake_sipoc_v1", "nonexistent_stage")
    
    def test_get_initial_slots(self):
        """Test getting initial slots template."""
        loader = FlowLoader()
        slots = loader.get_initial_slots("intake_sipoc_v1")
        
        assert "engagement" in slots
        assert "process_profile" in slots
        assert "scope" in slots
        assert "sipoc" in slots


class TestTemplateRenderer:
    """Test TemplateRenderer class."""
    
    def test_render_simple(self):
        """Test simple template rendering."""
        slots = {"engagement": {"process_name": "Order Fulfillment"}}
        template = "Process: {{engagement.process_name}}"
        
        result = TemplateRenderer.render(template, slots)
        
        assert result == "Process: Order Fulfillment"
    
    def test_render_nested(self):
        """Test nested path rendering."""
        slots = {
            "scope": {
                "value_statement": "Deliver orders"
            }
        }
        template = "Value: {{scope.value_statement}}"
        
        result = TemplateRenderer.render(template, slots)
        
        assert result == "Value: Deliver orders"
    
    def test_render_array_index(self):
        """Test array indexing in templates."""
        slots = {
            "workflows": {
                "maps": [
                    {"trigger": "Order confirmed"},
                    {"trigger": "Rush request"}
                ]
            }
        }
        template = "First trigger: {{workflows.maps[0].trigger}}"
        
        result = TemplateRenderer.render(template, slots)
        
        assert result == "First trigger: Order confirmed"
    
    def test_render_missing_value(self):
        """Test rendering with missing value shows placeholder."""
        slots = {"engagement": {}}
        template = "Name: {{engagement.missing_field}}"
        
        result = TemplateRenderer.render(template, slots)
        
        assert "[engagement.missing_field]" in result
    
    def test_render_empty_template(self):
        """Test rendering empty template."""
        slots = {}
        result = TemplateRenderer.render("", slots)
        
        assert result == ""


class TestSlotWriter:
    """Test SlotWriter class."""
    
    def test_write_simple(self):
        """Test writing to simple path."""
        slots = {"engagement": {}}
        SlotWriter.write(slots, "engagement.process_name", "Order Fulfillment")
        
        assert slots["engagement"]["process_name"] == "Order Fulfillment"
    
    def test_write_nested(self):
        """Test writing to nested path."""
        slots = {}
        SlotWriter.write(slots, "scope.value_statement", "Deliver orders")
        
        assert slots["scope"]["value_statement"] == "Deliver orders"
    
    def test_write_creates_structure(self):
        """Test writing creates intermediate structure."""
        slots = {}
        SlotWriter.write(slots, "process_profile.volume.avg_per_period", 150)
        
        assert slots["process_profile"]["volume"]["avg_per_period"] == 150
    
    def test_write_array_append(self):
        """Test appending to list."""
        slots = {"sipoc": {"suppliers": []}}
        SlotWriter.write(slots, "sipoc.suppliers", "Inventory system")
        SlotWriter.write(slots, "sipoc.suppliers", "Payment processor")
        
        assert len(slots["sipoc"]["suppliers"]) == 2
        assert "Inventory system" in slots["sipoc"]["suppliers"]
    
    def test_write_array_index(self):
        """Test writing to specific array index."""
        slots = {"workflows": {"maps": [{}]}}
        SlotWriter.write(slots, "workflows.maps[0].trigger", "Order confirmed")
        
        assert slots["workflows"]["maps"][0]["trigger"] == "Order confirmed"


class TestStageAdvancer:
    """Test StageAdvancer class."""
    
    def test_get_next_stage_message(self):
        """Test advancing from message stage."""
        stage = {"id": "welcome", "type": "message", "next": "engagement_context"}
        slots = {}
        
        next_id = StageAdvancer.get_next_stage(stage, slots)
        
        assert next_id == "engagement_context"
    
    def test_get_next_stage_confirm_yes(self):
        """Test confirm stage with yes response."""
        stage = {
            "id": "sipoc_confirm",
            "type": "confirm",
            "on_yes": "end",
            "on_no": "sipoc_capture"
        }
        slots = {}
        
        next_id = StageAdvancer.get_next_stage(stage, slots, user_response="yes")
        
        assert next_id == "end"

    def test_get_next_stage_confirm_yes_with_punctuation(self):
        """Test confirm stage with a realistic yes response like 'Yes.'."""
        stage = {
            "id": "sipoc_confirm",
            "type": "confirm",
            "on_yes": "end",
            "on_no": "sipoc_capture"
        }
        slots = {}

        next_id = StageAdvancer.get_next_stage(stage, slots, user_response="Yes.")

        assert next_id == "end"

    def test_get_next_stage_confirm_yes_with_phrase(self):
        """Test confirm stage with phrased yes response (not exact match)."""
        stage = {
            "id": "sipoc_confirm",
            "type": "confirm",
            "on_yes": "end",
            "on_no": "sipoc_capture"
        }
        slots = {}

        next_id = StageAdvancer.get_next_stage(stage, slots, user_response="Yes, that looks accurate")

        assert next_id == "end"

    def test_get_next_stage_confirm_yes_ok_sure_great(self):
        """Common affirmations should be treated as yes."""
        stage = {
            "id": "sipoc_confirm",
            "type": "confirm",
            "on_yes": "end",
            "on_no": "sipoc_capture"
        }
        slots = {}

        assert StageAdvancer.get_next_stage(stage, slots, user_response="ok") == "end"
        assert StageAdvancer.get_next_stage(stage, slots, user_response="sure") == "end"
        assert StageAdvancer.get_next_stage(stage, slots, user_response="great") == "end"
        assert StageAdvancer.get_next_stage(stage, slots, user_response="I guess generally") == "end"
    
    def test_get_next_stage_confirm_no(self):
        """Test confirm stage with no response."""
        stage = {
            "id": "sipoc_confirm",
            "type": "confirm",
            "on_yes": "end",
            "on_no": "sipoc_capture"
        }
        slots = {}
        
        next_id = StageAdvancer.get_next_stage(stage, slots, user_response="no")
        
        assert next_id == "sipoc_capture"

    def test_get_next_stage_confirm_no_with_phrase(self):
        """Test confirm stage with phrased no response (e.g., 'No, ...')."""
        stage = {
            "id": "sipoc_confirm",
            "type": "confirm",
            "on_yes": "end",
            "on_no": "sipoc_capture"
        }
        slots = {}

        next_id = StageAdvancer.get_next_stage(stage, slots, user_response="No, I need to correct something")

        assert next_id == "sipoc_capture"

    def test_get_next_stage_confirm_unclear_stays_on_stage(self):
        """Unclear confirm response should not default to 'no'."""
        stage = {
            "id": "sipoc_confirm",
            "type": "confirm",
            "on_yes": "end",
            "on_no": "sipoc_capture"
        }
        slots = {}

        next_id = StageAdvancer.get_next_stage(stage, slots, user_response="maybe")

        assert next_id == "sipoc_confirm"
    
    def test_get_next_stage_gate_pass(self):
        """Test gate stage that passes."""
        stage = {
            "id": "workflow_count_gate",
            "type": "gate",
            "criteria": [
                {"slot": "workflows.selected_workflows", "min_items": 1, "required": True}
            ],
            "on_pass": "workflow_init",
            "on_fail": "workflow_selection"
        }
        slots = {"workflows": {"selected_workflows": ["Standard order"]}}
        
        next_id = StageAdvancer.get_next_stage(stage, slots)
        
        assert next_id == "workflow_init"
    
    def test_get_next_stage_gate_fail(self):
        """Test gate stage that fails."""
        stage = {
            "id": "workflow_count_gate",
            "type": "gate",
            "criteria": [
                {"slot": "workflows.selected_workflows", "min_items": 1, "required": True}
            ],
            "on_pass": "workflow_init",
            "on_fail": "workflow_selection"
        }
        slots = {"workflows": {"selected_workflows": []}}
        
        next_id = StageAdvancer.get_next_stage(stage, slots)
        
        assert next_id == "workflow_selection"
    
    def test_check_gate_criteria_required(self):
        """Test gate criteria with required field."""
        criteria = [{"slot": "engagement.process_name", "required": True}]
        slots = {"engagement": {"process_name": "Order Fulfillment"}}
        
        result = StageAdvancer._check_gate_criteria(criteria, slots)
        
        assert result is True
    
    def test_check_gate_criteria_missing_required(self):
        """Test gate criteria with missing required field."""
        criteria = [{"slot": "engagement.process_name", "required": True}]
        slots = {"engagement": {}}
        
        result = StageAdvancer._check_gate_criteria(criteria, slots)
        
        assert result is False
