"""
Unit tests for interview nodes.
"""

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from src.state.interview_state import InterviewState
from src.nodes.interview_nodes import (
    _should_clarify,
    ingest_user_answer_node,
)


class TestShouldClarify:
    """Test clarify_if condition checking."""
    
    def test_empty_or_too_short_empty(self):
        """Test empty_or_too_short with empty string."""
        assert _should_clarify("", "empty_or_too_short") is True
        assert _should_clarify("   ", "empty_or_too_short") is True
    
    def test_empty_or_too_short_short(self):
        """Test empty_or_too_short with short string."""
        assert _should_clarify("yes", "empty_or_too_short") is True
        assert _should_clarify("ok", "empty_or_too_short") is True
    
    def test_empty_or_too_short_long_enough(self):
        """Test empty_or_too_short with long enough string."""
        assert _should_clarify("This is a proper answer", "empty_or_too_short") is False
    
    def test_vague_vague_words(self):
        """Test vague condition with vague words."""
        assert _should_clarify("maybe", "vague") is True
        assert _should_clarify("I think so", "vague") is True
        assert _should_clarify("not sure", "vague") is True
        assert _should_clarify("kind of", "vague") is True
    
    def test_vague_clear_answer(self):
        """Test vague condition with clear answer."""
        assert _should_clarify("The customer places an order through the website", "vague") is False
    
    def test_unclear_yes_no_clear_yes(self):
        """Test unclear_yes_no with clear yes."""
        assert _should_clarify("yes", "unclear_yes_no") is False
        assert _should_clarify("Yes, that's correct", "unclear_yes_no") is False
    
    def test_unclear_yes_no_clear_no(self):
        """Test unclear_yes_no with clear no."""
        assert _should_clarify("no", "unclear_yes_no") is False
        assert _should_clarify("No, that's wrong", "unclear_yes_no") is False
    
    def test_unclear_yes_no_unclear(self):
        """Test unclear_yes_no with unclear response."""
        assert _should_clarify("well maybe", "unclear_yes_no") is True
        assert _should_clarify("I don't know", "unclear_yes_no") is True


class TestIngestUserAnswerNode:
    """Test ingest_user_answer_node with clarify_if logic."""
    
    def test_ingest_with_clarification_needed(self):
        """Test that clarification is triggered when answer is too short."""
        state: InterviewState = {
            "messages": [HumanMessage(content="yes")],
            "flow_id": "intake_sipoc_v1",
            "active_stage_id": "test_stage",
            "slots": {},
            "pending": {
                "save_to": "test.field",
                "clarify_if": [
                    {
                        "condition": "empty_or_too_short",
                        "follow_up": "Please provide more detail."
                    }
                ],
                "question_index": 0
            },
            "workflow_capture_state": {},
            "error": None,
            "retry_count": 0,
            "auto_advance_count": 0,
            "max_auto_advance_steps": 50,
            "question_cursor": {}
        }
        
        # Mock the flow loader to return a questions stage
        from src.nodes.interview_nodes import _flow_loader
        original_get_stage = _flow_loader.get_stage
        
        def mock_get_stage(flow_id, stage_id):
            return {
                "id": "test_stage",
                "type": "questions",
                "questions": [{"id": "q1", "ask": "Test?", "save_to": "test.field"}],
                "next": "end"
            }
        
        _flow_loader.get_stage = mock_get_stage
        
        try:
            result = ingest_user_answer_node(state)
            
            # Should trigger clarification
            assert "messages" in result
            assert len(result["messages"]) == 1
            assert "more detail" in result["messages"][0].content.lower()
            
            # Should set clarification state
            assert result["pending"]["is_clarifying"] is True
            assert result["pending"]["original_answer"] == "yes"
        finally:
            _flow_loader.get_stage = original_get_stage
    
    def test_ingest_with_clarification_answer(self):
        """Test that clarification answer is combined with original."""
        state: InterviewState = {
            "messages": [HumanMessage(content="The customer submits through the portal")],
            "flow_id": "intake_sipoc_v1",
            "active_stage_id": "test_stage",
            "slots": {},
            "pending": {
                "save_to": "test.field",
                "is_clarifying": True,
                "original_answer": "yes",
                "question_index": 0
            },
            "workflow_capture_state": {},
            "error": None,
            "retry_count": 0,
            "auto_advance_count": 0,
            "max_auto_advance_steps": 50,
            "question_cursor": {}
        }
        
        from src.nodes.interview_nodes import _flow_loader
        original_get_stage = _flow_loader.get_stage
        
        def mock_get_stage(flow_id, stage_id):
            return {
                "id": "test_stage",
                "type": "questions",
                "questions": [{"id": "q1", "ask": "Test?", "save_to": "test.field"}],
                "next": "end"
            }
        
        _flow_loader.get_stage = mock_get_stage
        
        try:
            result = ingest_user_answer_node(state)
            
            # Should combine answers
            assert "test" in result["slots"]
            assert "field" in result["slots"]["test"]
            combined = result["slots"]["test"]["field"]
            assert "yes" in combined
            assert "customer submits" in combined.lower()
            
            # Should clear clarification state
            assert result["pending"] is None
        finally:
            _flow_loader.get_stage = original_get_stage
    
    def test_ingest_no_clarification_needed(self):
        """Test that good answer proceeds without clarification."""
        state: InterviewState = {
            "messages": [HumanMessage(content="The customer places an order through our website")],
            "flow_id": "intake_sipoc_v1",
            "active_stage_id": "test_stage",
            "slots": {},
            "pending": {
                "save_to": "test.field",
                "clarify_if": [
                    {
                        "condition": "empty_or_too_short",
                        "follow_up": "Please provide more detail."
                    }
                ],
                "question_index": 0
            },
            "workflow_capture_state": {},
            "error": None,
            "retry_count": 0,
            "auto_advance_count": 0,
            "max_auto_advance_steps": 50,
            "question_cursor": {}
        }
        
        from src.nodes.interview_nodes import _flow_loader
        original_get_stage = _flow_loader.get_stage
        
        def mock_get_stage(flow_id, stage_id):
            return {
                "id": "test_stage",
                "type": "questions",
                "questions": [{"id": "q1", "ask": "Test?", "save_to": "test.field"}],
                "next": "end"
            }
        
        _flow_loader.get_stage = mock_get_stage
        
        try:
            result = ingest_user_answer_node(state)
            
            # Should save answer without clarification
            assert "test" in result["slots"]
            assert result["slots"]["test"]["field"] == "The customer places an order through our website"
            
            # Should clear pending (move to next question or stage)
            assert result["pending"] is None
        finally:
            _flow_loader.get_stage = original_get_stage
