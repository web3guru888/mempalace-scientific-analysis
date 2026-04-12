import logging
from typing import Dict, Any, List

from mempalace_agi.config import IntegrationConfig
from mempalace_agi.palace_discovery_memory import PalaceDiscoveryMemory

logger = logging.getLogger("mempalace_agi")

class DomainSpecialistManager:
    """
    Manages specialist agents for ASTRA investigation domains.
    Provides persistent context and diary tracking per domain.
    """

    def __init__(self, palace_memory: PalaceDiscoveryMemory, config: IntegrationConfig):
        self.palace_memory = palace_memory
        self.config = config

    def _get_agent_name(self, domain: str) -> str:
        """Get the specialist agent name for a domain."""
        wing = getattr(self.config, "normalize_domain", self.config.wing_for_domain)(domain)
        return wing.replace("wing_", "specialist_")

    def write_investigation_diary(self, domain: str, hypothesis_id: str, method: str, results: Dict[str, Any], cycle: int = None) -> str:
        """Write a diary entry summarizing an investigation."""
        agent_name = self._get_agent_name(domain)
        
        if cycle is None:
            cycle = results.get("cycle", "?")
        tests_run = results.get("tests_run", 0)
        significant = results.get("significant", 0)
        summary = results.get("summary", "No significant results")
        
        entry = (
            f"Cycle {cycle}: Investigated {hypothesis_id} "
            f"using {method}. "
            f"Tests run: {tests_run}, "
            f"Significant: {significant}, "
            f"Key finding: {summary}."
        )
        
        logger.info(f"Writing diary for {agent_name}: {entry}")
        
        # Write to palace diary
        drawer_id = self.palace_memory.diary_write(
            agent_name=agent_name,
            entry=entry,
            topic=f"{method}_{hypothesis_id}"
        )
        return drawer_id

    
    def get_all_specialists(self) -> List[Dict[str, Any]]:
        """Get a list of all domain specialists and their stats."""
        specialists = []
        for domain in self.config.domain_wings.keys():
            specialists.append({
                "domain": domain,
                "agent_name": self._get_agent_name(domain),
                "total_entries": len(self.get_domain_context(domain, last_n=100))
            })
        return specialists

    def get_domain_context(self, domain: str, last_n: int = 5) -> List[str]:
        """Read recent diary entries for domain context."""
        agent_name = self._get_agent_name(domain)
        try:
            return self.palace_memory.diary_read(agent_name=agent_name, last_n=last_n)
        except AttributeError:
            # Fallback if PalaceDiscoveryMemory doesn't have diary_read yet
            logger.warning(f"diary_read not supported yet on PalaceDiscoveryMemory for {agent_name}")
            return []

    def summarize_domain(self, domain: str) -> str:
        """Generate a summary of recent domain activity."""
        entries = self.get_domain_context(domain, last_n=10)
        if not entries:
            return f"No recent activity logged for domain: {domain}."
            
        summary = f"Recent activity in {domain} ({len(entries)} entries):\n"
        for i, entry in enumerate(entries, 1):
            summary += f"{i}. {entry}\n"
        return summary

    def get_pre_investigation_context(self, domain: str, hypothesis_id: str) -> Dict[str, Any]:
        """Get context for an upcoming investigation to prevent redundant exploration."""
        context = {
            "domain": domain,
            "hypothesis_id": hypothesis_id,
            "recent_activity": self.get_domain_context(domain, last_n=getattr(self.config, "diary_entries_context", 5)),
        }
        return context

    def format_context_for_investigation(self, domain: str, hypothesis_id: str) -> str:
        """Provide a human-readable context string for the investigation method."""
        context = self.get_pre_investigation_context(domain, hypothesis_id)
        entries = context.get("recent_activity", [])
        
        if not entries:
            return f"Starting fresh investigation of {hypothesis_id} in {domain}. No recent context."
            
        activity_str = "\n".join([f"- {e}" for e in entries])
        return (
            f"Context for investigating {hypothesis_id} in {domain}:\n"
            f"Recent domain activity:\n{activity_str}\n"
            "Use this context to avoid repeating identical tests and to build on recent findings."
        )
