import pytest
from unittest.mock import Mock

from mempalace_agi.config import IntegrationConfig
from mempalace_agi.domain_specialists import DomainSpecialistManager

@pytest.fixture
def mock_palace():
    palace = Mock()
    palace.diary_write.return_value = "drawer_id"
    palace.diary_read.return_value = ["1", "2"]
    return palace

@pytest.fixture
def config():
    return IntegrationConfig()

def test_write_investigation_diary(mock_palace, config):
    manager = DomainSpecialistManager(mock_palace, config)
    
    manager.write_investigation_diary(
        domain="Astrophysics", 
        hypothesis_id="H01", 
        method="hubble", 
        results={"cycle": 5, "tests_run": 10, "significant": 2, "summary": "Found x"}
    )
    
    mock_palace.diary_write.assert_called_once_with(
        agent_name="specialist_astrophysics",
        entry="Cycle 5: Investigated H01 using hubble. Tests run: 10, Significant: 2, Key finding: Found x.",
        topic="hubble_H01"
    )

def test_get_domain_context(mock_palace, config):
    manager = DomainSpecialistManager(mock_palace, config)
    
    result = manager.get_domain_context("Astrophysics", last_n=3)
    
    assert result == ["1", "2"]
    mock_palace.diary_read.assert_called_once_with(agent_name="specialist_astrophysics", last_n=3)

def test_summarize_domain(mock_palace, config):
    manager = DomainSpecialistManager(mock_palace, config)
    mock_palace.diary_read.return_value = ["Found x", "Found y"]
    
    summary = manager.summarize_domain("Astrophysics")
    
    assert "Found x" in summary
    assert "Found y" in summary
    assert "Recent activity in Astrophysics (2 entries)" in summary

def test_format_context_for_investigation(mock_palace, config):
    manager = DomainSpecialistManager(mock_palace, config)
    mock_palace.diary_read.return_value = ["Prior test"]
    
    formatted = manager.format_context_for_investigation("Astrophysics", "H99")
    
    assert "Context for investigating H99 in Astrophysics" in formatted
    assert "Prior test" in formatted
