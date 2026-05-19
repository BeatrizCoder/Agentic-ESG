"""Service modules for Knowledge, Memory, Prompt, and Skill management."""

import json
import logging
import os
import re
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
import glob

from .config import ENABLE_MEMORY, ENABLE_CREWAI_KNOWLEDGE, ENABLE_PROMPT_TEMPLATES, KNOWLEDGE_DIR, PROMPTS_DIR, MEMORY_FILE, SKILLS_DIR

logger = logging.getLogger(__name__)


class KnowledgeService:
    def __init__(self):
        self.knowledge_dir = Path("knowledge")
        self.documents = {}
        self.max_snippets = int(os.environ.get("MAX_KNOWLEDGE_SNIPPETS", "3"))
        self.max_snippet_chars = int(os.environ.get("MAX_SNIPPET_CHARS", "800"))
        self._load_documents()

    def _load_documents(self):
        if not self.knowledge_dir.exists():
            logger.warning("Knowledge directory not found")
            return

        for md_file in self.knowledge_dir.glob("*.md"):
            category = md_file.stem.replace("_", " ").title()
            content = md_file.read_text(encoding="utf-8")
            sections = self._parse_sections(content)
            self.documents[md_file.stem] = {
                "file": md_file.name,
                "category": category,
                "sections": sections,
                "full_content": content
            }

        logger.info("KnowledgeService: loaded %d knowledge documents", len(self.documents))

    def _parse_sections(self, content: str) -> list[dict]:
        sections = []
        current_title = "General"
        current_content = []

        for line in content.split("\n"):
            if line.startswith("## "):
                if current_content:
                    sections.append({
                        "title": current_title,
                        "content": "\n".join(current_content).strip()
                    })
                current_title = line[3:].strip()
                current_content = []
            elif not line.startswith("# "):
                current_content.append(line)

        if current_content:
            sections.append({
                "title": current_title,
                "content": "\n".join(current_content).strip()
            })

        return sections

    def _relevance_score(self, text: str, inquiry: str, keywords: list[str]) -> float:
        text_lower = text.lower()
        inquiry_lower = inquiry.lower()
        score = 0.0

        for kw in keywords:
            if kw.lower() in text_lower:
                score += 2.0

        inquiry_words = [w for w in inquiry_lower.split() if len(w) > 3]
        for word in inquiry_words:
            if word in text_lower:
                score += 1.0

        return score

    def get_articles(self, category: str, inquiry: str = "") -> list[str]:
        snippets = self.get_snippets(category, inquiry)
        return [s["title"] for s in snippets]

    def get_snippets(self, category: str, inquiry: str = "") -> list[dict]:
        category_map = {
            "Order Issues": "order_issues",
            "Billing": "billing",
            "Account Access": "account_access",
            "Technical Issue": "technical_issues",
            "General Support": "general_support",
        }

        file_key = category_map.get(category, "general_support")
        keywords = [w for w in inquiry.lower().split() if len(w) > 3]
        scored_sections = []

        if file_key in self.documents:
            doc = self.documents[file_key]
            for section in doc["sections"]:
                combined = f"{section['title']} {section['content']}"
                score = self._relevance_score(combined, inquiry, keywords)
                if score > 0 or not inquiry:
                    scored_sections.append({
                        "title": section["title"],
                        "content": section["content"][:self.max_snippet_chars],
                        "source": doc["file"],
                        "relevance_score": round(score, 2)
                    })

        if "escalation_policy" in self.documents:
            doc = self.documents["escalation_policy"]
            for section in doc["sections"]:
                combined = f"{section['title']} {section['content']}"
                score = self._relevance_score(combined, inquiry, keywords)
                if score > 0:
                    scored_sections.append({
                        "title": section["title"],
                        "content": section["content"][:self.max_snippet_chars],
                        "source": doc["file"],
                        "relevance_score": round(score, 2)
                    })

        scored_sections.sort(key=lambda x: x["relevance_score"], reverse=True)
        return scored_sections[:self.max_snippets]

    def should_escalate(self, category: str, inquiry: str) -> bool:
        if "escalation_policy" not in self.documents:
            return False

        doc = self.documents["escalation_policy"]
        full_text = doc["full_content"].lower()
        inquiry_lower = inquiry.lower()

        for line in full_text.split("\n"):
            if "," in line and len(line) < 200:
                keywords = [k.strip() for k in line.split(",")]
                for kw in keywords:
                    if len(kw) > 3 and kw in inquiry_lower:
                        return True
        return False


class MemoryService:
    """Service for storing and retrieving conversation memory."""

    def __init__(self):
        self.memory_file = MEMORY_FILE
        self.memory_data: List[Dict[str, Any]] = []
        if ENABLE_MEMORY:
            self._load_memory()

    def _load_memory(self) -> None:
        """Load memory from file."""
        if os.path.exists(self.memory_file):
            try:
                with open(self.memory_file, 'r', encoding='utf-8') as f:
                    self.memory_data = json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                self.memory_data = []

    def _save_memory(self) -> None:
        """Save memory to file."""
        if ENABLE_MEMORY:
            with open(self.memory_file, 'w', encoding='utf-8') as f:
                json.dump(self.memory_data, f, indent=2, default=str)

    def store_interaction(self, inquiry: str, category: str, sentiment: str,
                         escalation_required: bool, final_response: str,
                         reference_id: Optional[str] = None) -> None:
        """Store an interaction in memory."""
        if not ENABLE_MEMORY:
            return

        interaction = {
            "timestamp": datetime.now().isoformat(),
            "inquiry": inquiry,
            "category": category,
            "sentiment": sentiment,
            "escalation_required": escalation_required,
            "final_response": final_response,
            "reference_id": reference_id
        }

        self.memory_data.append(interaction)
        self._save_memory()

    def get_recent_interactions(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent interactions from memory."""
        if not ENABLE_MEMORY:
            return []
        return self.memory_data[-limit:]


class PromptService:
    """Service for managing prompt templates."""

    def __init__(self):
        self.prompts_dir = PROMPTS_DIR
        self.prompt_templates: Dict[str, str] = {}
        if ENABLE_PROMPT_TEMPLATES:
            self._load_prompts()

    def _load_prompts(self) -> None:
        """Load prompt templates from files."""
        if not os.path.exists(self.prompts_dir):
            return

        for md_file in glob.glob(os.path.join(self.prompts_dir, "*.md")):
            filename = os.path.basename(md_file).replace('.md', '')
            with open(md_file, 'r', encoding='utf-8') as f:
                self.prompt_templates[filename] = f.read()

    def get_prompt(self, prompt_name: str, variables: Optional[Dict[str, Any]] = None) -> str:
        """Get a prompt template with variables injected."""
        if not ENABLE_PROMPT_TEMPLATES:
            return ""

        template = self.prompt_templates.get(prompt_name, "")
        if not template or not variables:
            return template

        # Simple variable injection
        for key, value in variables.items():
            placeholder = f"{{{key}}}"
            template = template.replace(placeholder, str(value))

        return template

    def list_available_prompts(self) -> List[str]:
        """List available prompt templates."""
        return list(self.prompt_templates.keys())


class SkillService:
    """Service for managing agent skills."""

    def __init__(self):
        self.skills_dir = SKILLS_DIR
        self.skills_data: Dict[str, str] = {}
        self.agent_skills: Dict[str, List[str]] = {}
        self._load_skills()
        self._setup_agent_skills()

    def _load_skills(self) -> None:
        """Load skills from local files."""
        if not os.path.exists(self.skills_dir):
            return

        for md_file in glob.glob(os.path.join(self.skills_dir, "*.md")):
            filename = os.path.basename(md_file).replace('.md', '')
            with open(md_file, 'r', encoding='utf-8') as f:
                self.skills_data[filename] = f.read()

    def _setup_agent_skills(self) -> None:
        """Set up skill associations for agents."""
        # Default skill mappings
        self.agent_skills = {
            "classifier_agent": ["customer_support_analysis"],
            "sentiment_agent": ["customer_support_analysis"],
            "knowledge_agent": ["customer_support_analysis"],
            "response_agent": ["empathetic_response", "safety_validation"],
            "escalation_agent": ["escalation_decision", "safety_validation"]
        }

    def get_skills_for_agent(self, agent_name: str) -> List[str]:
        """Get skills associated with an agent."""
        return self.agent_skills.get(agent_name, [])

    def get_skill_content(self, skill_name: str) -> str:
        """Get the content of a specific skill."""
        return self.skills_data.get(skill_name, "")

    def list_available_skills(self) -> List[str]:
        """List all available skills."""
        return list(self.skills_data.keys())

    def validate_response_with_skills(self, response: str, agent_name: str) -> Dict[str, Any]:
        """Validate a response using relevant skills."""
        skills = self.get_skills_for_agent(agent_name)
        validation_results = {}

        for skill in skills:
            if skill == "safety_validation":
                # Basic safety check
                unsafe_patterns = ["password", "credit card", "social security"]
                has_unsafe_content = any(pattern in response.lower() for pattern in unsafe_patterns)
                validation_results["safety_check"] = not has_unsafe_content
            elif skill == "empathetic_response":
                # Basic empathy check
                empathetic_phrases = ["sorry", "understand", "help", "assist"]
                has_empathy = any(phrase in response.lower() for phrase in empathetic_phrases)
                validation_results["empathy_check"] = has_empathy

        return {
            "skills_used": skills,
            "validation_results": validation_results,
            "overall_valid": all(validation_results.values())
        }