"""Service modules for Knowledge, Memory, Prompt, and Skill management."""

import json
import os
from typing import Dict, List, Any, Optional
from datetime import datetime
import glob
import yaml

from .config import ENABLE_MEMORY, ENABLE_CREWAI_KNOWLEDGE, ENABLE_PROMPT_TEMPLATES, KNOWLEDGE_DIR, PROMPTS_DIR, MEMORY_FILE, SKILLS_DIR


class KnowledgeService:
    """Service for managing knowledge base with local file support."""

    def __init__(self):
        self.knowledge_dir = KNOWLEDGE_DIR
        self.knowledge_data: Dict[str, str] = {}
        self._load_knowledge()
        self._articles: List[Dict[str, Any]] = []
        self._load_yaml_articles()

    def _load_knowledge(self) -> None:
        """Load knowledge from local files."""
        if not os.path.exists(self.knowledge_dir):
            return

        # Load markdown files
        for md_file in glob.glob(os.path.join(self.knowledge_dir, "*.md")):
            filename = os.path.basename(md_file)
            with open(md_file, 'r', encoding='utf-8') as f:
                self.knowledge_data[filename] = f.read()

        # Load JSON files
        for json_file in glob.glob(os.path.join(self.knowledge_dir, "*.json")):
            filename = os.path.basename(json_file)
            with open(json_file, 'r', encoding='utf-8') as f:
                try:
                    data = json.load(f)
                    self.knowledge_data[filename] = json.dumps(data, indent=2)
                except json.JSONDecodeError:
                    continue

    def _load_yaml_articles(self) -> None:
        """Load structured articles from config/knowledge_base.yaml."""
        yaml_path = os.path.join(os.path.dirname(__file__), '..', '..', 'config', 'knowledge_base.yaml')
        yaml_path = os.path.normpath(yaml_path)
        if not os.path.exists(yaml_path):
            return
        with open(yaml_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        self._articles = data.get('articles', [])

    def get_articles(self, category: str, inquiry: str) -> List[str]:
        """Return titles of articles in category whose keywords match the inquiry."""
        inquiry_lower = inquiry.lower()
        matched = []
        for article in self._articles:
            if article.get('category') != category:
                continue
            for kw in article.get('keywords', []):
                if kw.lower() in inquiry_lower:
                    matched.append(article['title'])
                    break
        return matched

    def should_escalate(self, category: str, inquiry: str) -> bool:
        """Return True if any matched article for this inquiry requires always escalating."""
        inquiry_lower = inquiry.lower()
        for article in self._articles:
            if article.get('category') != category:
                continue
            for kw in article.get('keywords', []):
                if kw.lower() in inquiry_lower:
                    if 'always escalate' in str(article.get('escalate_if', '')):
                        return True
                    break
        return False

    def search_knowledge(self, query: str, category: Optional[str] = None) -> Dict[str, Any]:
        """Search knowledge base using keyword matching."""
        query_lower = query.lower()
        query_words = query_lower.split()
        matches = []

        for filename, content in self.knowledge_data.items():
            content_lower = content.lower()
            # Check if any query word appears in the content
            if any(word in content_lower for word in query_words):
                # Extract snippet around the first match
                lines = content.split('\n')
                relevant_lines = []
                for i, line in enumerate(lines):
                    line_lower = line.lower()
                    if any(word in line_lower for word in query_words):
                        # Get context around the match
                        start = max(0, i - 2)
                        end = min(len(lines), i + 3)
                        snippet = '\n'.join(lines[start:end])
                        relevant_lines.append(snippet.strip())
                        break  # Take first match

                if relevant_lines:
                    matches.append({
                        "title": filename,
                        "snippet": relevant_lines[0][:200] + "..." if len(relevant_lines[0]) > 200 else relevant_lines[0]
                    })

        return {
            "articles": [match["title"] for match in matches],
            "snippets": [match["snippet"] for match in matches],
            "count": len(matches),
            "source": "local_files"
        }


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