"""
Shared test fixtures for unit and integration tests.
"""

import pytest
from typing import Any, Dict

from src.state.interview_state import create_initial_state


@pytest.fixture
def initial_state() -> Dict[str, Any]:
    """Create a fresh initial state for testing."""
    return create_initial_state()


@pytest.fixture
def sample_slots() -> Dict[str, Any]:
    """Sample interview data slots for testing."""
    return {
        "engagement": {
            "process_name": "Order Fulfillment",
            "organization_type": "E-commerce retailer",
            "industry": "Retail",
            "participants_present": ["Warehouse Manager", "Order Processing Team Lead"],
            "primary_sme_role": "Warehouse Manager",
            "discovery_format": "1:1 interview",
            "timebox_minutes": 60
        },
        "process_profile": {
            "process_type": "knowledge work with physical flow",
            "locations_involved": ["Warehouse", "Office"],
            "frequency": "daily",
            "volume": {
                "avg_per_period": 150,
                "period": "day",
                "peak_per_period": 300,
                "peak_period_description": "Holiday season"
            },
            "variability": "80% repeatable",
            "seasonality": "High peak Nov-Dec",
            "typical_record_identifier": "Order number"
        },
        "scope": {
            "value_statement": "Deliver customer orders accurately and on time",
            "start_trigger": "Order confirmed and payment received",
            "end_condition": "Order delivered and customer notified",
            "in_scope": ["Order picking", "Packing", "Shipping label generation", "Carrier handoff"],
            "out_of_scope": ["Returns processing", "Customer service inquiries"],
            "customers_or_recipients": ["End customers"],
            "upstream_dependencies": ["Payment system", "Inventory management"],
            "downstream_dependencies": ["Shipping carriers"]
        },
        "sipoc": {
            "suppliers": ["Inventory system", "Payment processor", "Customer"],
            "inputs": ["Order details", "Payment confirmation", "Inventory location"],
            "process_high_level_steps": [
                "Receive order",
                "Pick items",
                "Pack order",
                "Generate shipping label",
                "Hand off to carrier"
            ],
            "outputs": ["Packaged order", "Tracking number", "Shipment notification"],
            "customers": ["End customer", "Shipping carrier"],
            "assumptions": ["Inventory is accurate", "Carriers pick up daily"]
        },
        "workflows": {
            "selected_workflows": ["Standard order", "Rush order"],
            "maps": []
        },
        "workflow_capture_state": {
            "active_workflow_id": None,
            "active_step_index": 0,
            "active_step_buffer": {}
        }
    }


@pytest.fixture
def sample_workflow() -> Dict[str, Any]:
    """Sample workflow map for testing."""
    return {
        "workflow_id": "wf_1",
        "workflow_name": "Standard Order",
        "trigger": "Order confirmed",
        "start_condition": "Payment received and order in system",
        "end_condition": "Carrier confirms pickup",
        "lanes": ["Order Processor", "Warehouse Picker", "Packer", "Shipping Clerk"],
        "steps": [
            {
                "description": "Review order details",
                "owner_role": "Order Processor",
                "inputs": ["Order confirmation email"],
                "outputs": ["Pick list"],
                "systems_tools_used": ["Order management system"],
                "decision": None,
                "wait_or_delay": "Wait for picker availability",
                "common_exception": "Missing item in inventory"
            },
            {
                "description": "Pick items from shelves",
                "owner_role": "Warehouse Picker",
                "inputs": ["Pick list", "Inventory location data"],
                "outputs": ["Picked items in cart"],
                "systems_tools_used": ["Handheld scanner"],
                "decision": None,
                "wait_or_delay": None,
                "common_exception": "Item not in expected location"
            }
        ],
        "decisions": [],
        "exceptions": ["Item out of stock", "Picker not available"],
        "wait_states": ["Wait for picker availability"],
        "artifacts_touched": ["Order management system", "Handheld scanner", "Pick list"],
        "notes": []
    }


@pytest.fixture
def mock_llm_response():
    """Factory for creating mock LLM responses."""
    class MockResponse:
        def __init__(self, content: str):
            self.content = content
    
    def _make_response(content: str):
        return MockResponse(content)
    
    return _make_response
