"""
Unit tests for output generation with mocked LLM.
"""

import pytest
from unittest.mock import Mock, patch
from src.actions.output_generation import (
    MermaidValidator,
    generate_sipoc_mermaid,
    generate_swimlane_mermaid,
    generate_markdown_summary,
    OutputGenerationError
)


class TestMermaidValidator:
    """Test Mermaid validation."""
    
    def test_validate_sipoc_valid(self):
        """Test valid SIPOC diagram."""
        mermaid = """
graph LR
    Supplier --> Input
    Input --> Process
    Process --> Output
    Output --> Customer
"""
        is_valid, error = MermaidValidator.validate_sipoc(mermaid)
        
        assert is_valid is True
        assert error is None
    
    def test_validate_sipoc_empty(self):
        """Test empty SIPOC diagram."""
        is_valid, error = MermaidValidator.validate_sipoc("")
        
        assert is_valid is False
        assert "Empty" in error
    
    def test_validate_sipoc_missing_graph(self):
        """Test SIPOC missing graph declaration."""
        mermaid = "Supplier --> Input"
        is_valid, error = MermaidValidator.validate_sipoc(mermaid)
        
        assert is_valid is False
        assert "graph" in error.lower()
    
    def test_validate_swimlane_valid(self):
        """Test valid swimlane diagram."""
        mermaid = """
flowchart TD
    subgraph Role1
        A[Step 1]
    end
    subgraph Role2
        B[Step 2]
    end
    A --> B
"""
        is_valid, error = MermaidValidator.validate_swimlane(mermaid)
        
        assert is_valid is True
        assert error is None
    
    def test_validate_swimlane_no_subgraph(self):
        """Test swimlane without subgraphs."""
        mermaid = """
graph TD
    A --> B
"""
        is_valid, error = MermaidValidator.validate_swimlane(mermaid)
        
        assert is_valid is False
        assert "subgraph" in error.lower()


class TestOutputGeneration:
    """Test output generation functions with mocked LLM."""
    
    @patch('src.actions.output_generation.ChatOpenAI')
    def test_generate_sipoc_mermaid_success(self, mock_llm_class, sample_slots):
        """Test successful SIPOC generation."""
        # Mock LLM response
        mock_llm = Mock()
        mock_response = Mock()
        mock_response.content = """```mermaid
graph LR
    Supplier[Inventory System] --> Input[Order Details]
    Input --> Process[Fulfill Order]
    Process --> Output[Packaged Order]
    Output --> Customer[End Customer]
```"""
        mock_llm.invoke.return_value = mock_response
        mock_llm_class.return_value = mock_llm
        
        result = generate_sipoc_mermaid(sample_slots)
        
        assert "graph" in result.lower()
        assert "supplier" in result.lower()
        assert "customer" in result.lower()
    
    @patch('src.actions.output_generation.ChatOpenAI')
    def test_generate_sipoc_mermaid_retry_on_invalid(self, mock_llm_class, sample_slots):
        """Test retry on invalid Mermaid."""
        mock_llm = Mock()
        
        # First response invalid, second valid
        invalid_response = Mock()
        invalid_response.content = "Not a valid diagram"
        
        valid_response = Mock()
        valid_response.content = """graph LR
    Supplier --> Input
    Input --> Process
    Process --> Output
    Output --> Customer
"""
        
        mock_llm.invoke.side_effect = [invalid_response, valid_response]
        mock_llm_class.return_value = mock_llm
        
        result = generate_sipoc_mermaid(sample_slots)
        
        assert "graph" in result.lower()
        assert mock_llm.invoke.call_count == 2
    
    @patch('src.actions.output_generation.ChatOpenAI')
    def test_generate_swimlane_mermaid_success(self, mock_llm_class, sample_slots, sample_workflow):
        """Test successful swimlane generation."""
        sample_slots["workflows"]["maps"] = [sample_workflow]
        
        mock_llm = Mock()
        mock_response = Mock()
        mock_response.content = """```mermaid
flowchart TD
    subgraph OrderProcessor
        A[Review Order]
    end
    subgraph Picker
        B[Pick Items]
    end
    A --> B
```"""
        mock_llm.invoke.return_value = mock_response
        mock_llm_class.return_value = mock_llm
        
        result = generate_swimlane_mermaid(sample_slots)
        
        assert "flowchart" in result.lower() or "graph" in result.lower()
        assert "subgraph" in result.lower()
    
    @patch('src.actions.output_generation.ChatOpenAI')
    def test_generate_markdown_summary_success(self, mock_llm_class, sample_slots):
        """Test successful markdown summary generation."""
        mock_llm = Mock()
        mock_response = Mock()
        mock_response.content = """# Order Fulfillment Process

## Overview
This is a current-state documentation of the Order Fulfillment process.

## Scope
The process covers order picking through carrier handoff.

## SIPOC
- Suppliers: Inventory System
- Inputs: Order Details
- Process: Fulfill Order
- Outputs: Packaged Order
- Customers: End Customer

## Key Observations
Process runs 150 times per day on average.
"""
        mock_llm.invoke.return_value = mock_response
        mock_llm_class.return_value = mock_llm
        
        result = generate_markdown_summary(sample_slots)
        
        assert "#" in result
        assert len(result) > 100
    
    @patch('src.actions.output_generation.ChatOpenAI')
    def test_generate_markdown_summary_too_short(self, mock_llm_class, sample_slots):
        """Test markdown summary that's too short raises error."""
        mock_llm = Mock()
        mock_response = Mock()
        mock_response.content = "Too short"
        mock_llm.invoke.return_value = mock_response
        mock_llm_class.return_value = mock_llm
        
        with pytest.raises(OutputGenerationError):
            generate_markdown_summary(sample_slots)
    
    @patch('src.actions.output_generation.ChatOpenAI')
    def test_generate_sipoc_mermaid_max_retries(self, mock_llm_class, sample_slots):
        """Test max retries exhausted raises error."""
        mock_llm = Mock()
        invalid_response = Mock()
        invalid_response.content = "Invalid"
        mock_llm.invoke.return_value = invalid_response
        mock_llm_class.return_value = mock_llm
        
        with pytest.raises(OutputGenerationError):
            generate_sipoc_mermaid(sample_slots)
