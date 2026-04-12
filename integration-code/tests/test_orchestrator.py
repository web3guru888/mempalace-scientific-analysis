import pytest
from unittest.mock import Mock, MagicMock

from mempalace_agi.orchestrator import MemPalaceAGI
from mempalace_agi.config import IntegrationConfig

@pytest.fixture
def orchestration():
    config = IntegrationConfig()
    mock_engine = MagicMock()
    mock_engine.cycle_count = 0
    
    mock_engine.store.active.return_value = [Mock(id="H001", description="test hyp", memory_context=[])]
    mock_engine.current_domain = "Astrophysics"
    
    # Original methods
    mock_engine.orient = Mock()
    mock_engine.investigate = Mock()
    mock_engine.evaluate = Mock()
    
    def run_cycle_mock():
        mock_engine.cycle_count += 1
        mock_engine.orient()
        mock_engine.investigate()
        mock_engine.evaluate()
        
    mock_engine.run_cycle.side_effect = run_cycle_mock
    
    return MemPalaceAGI(config, engine_mock=mock_engine)

def test_orchestrator_initialization(orchestration):
    assert orchestration.palace_memory is not None
    assert orchestration.orient_helper is not None
    assert orchestration.kg_bridge is not None
    assert orchestration.specialists is not None
    
    # Did it patch?
    assert orchestration.engine.discovery_memory == orchestration.palace_memory
    assert orchestration.engine.orient != "mock"
    
def test_run_augmented_cycle(orchestration):
    result = orchestration.run_augmented_cycle()
    
    assert orchestration.engine.cycle_count == 1
    assert result["status"] == "success"
    
    # We patched orient and evaluate, check if they were called
    # Active hyps from the mock should have memory_context attached
    hyp = orchestration.engine.store.active()[0]
    assert hasattr(hyp, "memory_context")
    assert hasattr(hyp, "memory_score_boost")

def test_get_status(orchestration):
    status = orchestration.get_status()
    assert "engine_cycle" in status
    assert "palace_stats" in status
    assert "kg_stats" in status
