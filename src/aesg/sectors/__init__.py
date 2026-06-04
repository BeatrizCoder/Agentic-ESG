"""Sector-specific risk profile loader for Agentic ESG."""

import logging
from pathlib import Path
from typing import Any, Optional

import yaml

logger = logging.getLogger(__name__)

# Sector name mapping for flexible input
SECTOR_MAPPING = {
    "general": "general",
    "agriculture": "agriculture_food",
    "agriculture & food": "agriculture_food",
    "agriculture_food": "agriculture_food",
    "food": "agriculture_food",
    "real estate": "real_estate",
    "real_estate": "real_estate",
    "property": "real_estate",
    "finance": "finance_banking",
    "finance & banking": "finance_banking",
    "finance_banking": "finance_banking",
    "banking": "finance_banking",
    "infrastructure": "infrastructure",
    "manufacturing": "manufacturing",
    "energy": "energy_utilities",
    "energy & utilities": "energy_utilities",
    "energy_utilities": "energy_utilities",
    "utilities": "energy_utilities",
    "retail": "retail_logistics",
    "retail & logistics": "retail_logistics",
    "retail_logistics": "retail_logistics",
    "logistics": "retail_logistics",
}


def load_sector_profile(sector: str) -> dict[str, Any]:
    """
    Load sector-specific risk profile from YAML configuration.
    
    Args:
        sector: Sector name (case-insensitive, flexible matching)
        
    Returns:
        Dictionary containing sector configuration with keys:
        - sector: Sector display name
        - risk_thresholds: Dict with drought_critical, heat_critical, flood_critical
        - primary_frameworks: List of relevant ESG frameworks
        - key_risks: List of sector-specific climate risks
        - focus_articles: List of specific regulatory articles
        - recommendation_tone: String for tailoring recommendations
        
    Raises:
        FileNotFoundError: If sector profile file doesn't exist
        yaml.YAMLError: If YAML parsing fails
    """
    # Normalize sector name
    sector_key = sector.lower().strip()
    sector_file = SECTOR_MAPPING.get(sector_key, "general")
    
    # Construct path to sector YAML file
    sectors_dir = Path(__file__).parent
    yaml_path = sectors_dir / f"{sector_file}.yaml"
    
    if not yaml_path.exists():
        logger.warning(
            "Sector profile not found: %s (requested: %r). Falling back to general.yaml",
            yaml_path, sector
        )
        yaml_path = sectors_dir / "general.yaml"
    
    try:
        with open(yaml_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        
        logger.info("Loaded sector profile: %s from %s", config.get("sector"), yaml_path.name)
        return config
    
    except yaml.YAMLError as e:
        logger.error("Failed to parse sector YAML %s: %s", yaml_path, e)
        raise
    except Exception as e:
        logger.error("Failed to load sector profile %s: %s", yaml_path, e)
        raise


def get_sector_context(sector: str) -> str:
    """
    Generate formatted sector context string for agent prompts.
    
    Args:
        sector: Sector name
        
    Returns:
        Formatted string with sector-specific context for ESG Strategist
    """
    try:
        config = load_sector_profile(sector)
    except Exception as e:
        logger.warning("Could not load sector profile for %r: %s. Using general context.", sector, e)
        config = load_sector_profile("general")
    
    context_parts = [
        f"SECTOR: {config['sector']}",
        "",
        "SECTOR-SPECIFIC RISK THRESHOLDS:",
    ]
    
    thresholds = config.get("risk_thresholds", {})
    if thresholds:
        context_parts.append(f"- Drought becomes CRITICAL when score > {thresholds.get('drought_critical', 45)}")
        context_parts.append(f"- Heat stress becomes CRITICAL when score > {thresholds.get('heat_critical', 50)}")
        context_parts.append(f"- Flood becomes CRITICAL when score > {thresholds.get('flood_critical', 40)}")
    
    context_parts.append("")
    context_parts.append("PRIMARY FRAMEWORKS FOR THIS SECTOR:")
    for framework in config.get("primary_frameworks", []):
        context_parts.append(f"- {framework}")
    
    context_parts.append("")
    context_parts.append("KEY SECTOR-SPECIFIC CLIMATE RISKS:")
    for risk in config.get("key_risks", []):
        context_parts.append(f"- {risk}")
    
    context_parts.append("")
    context_parts.append("FOCUS ARTICLES FOR COMPLIANCE MAPPING:")
    for article in config.get("focus_articles", []):
        context_parts.append(f"- {article}")
    
    context_parts.append("")
    context_parts.append(f"RECOMMENDATION TONE: Tailor recommendations for {config.get('recommendation_tone', 'general operations')}")
    
    return "\n".join(context_parts)


def list_available_sectors() -> list[str]:
    """
    List all available sector profiles.
    
    Returns:
        List of sector display names
    """
    sectors_dir = Path(__file__).parent
    yaml_files = sectors_dir.glob("*.yaml")
    
    sectors = []
    for yaml_file in yaml_files:
        try:
            with open(yaml_file, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
                sectors.append(config.get("sector", yaml_file.stem))
        except Exception as e:
            logger.warning("Could not read sector from %s: %s", yaml_file, e)
    
    return sorted(sectors)


__all__ = [
    "load_sector_profile",
    "get_sector_context",
    "list_available_sectors",
    "SECTOR_MAPPING",
]

# Made with Bob
