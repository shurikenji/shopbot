"""
bot/services/ai_translator.py — AI-powered group translation service.
Supports OpenAI, OpenAI Compatible (Ollama, LM Studio, etc.), Anthropic, and Gemini APIs.
"""
from __future__ import annotations

import json
import logging

from db.database import get_db
from db.queries import settings

logger = logging.getLogger(__name__)


class AITranslator:
    def __init__(self):
        self.provider: str = "openai"
        self.api_key: str = ""
        self.model: str = "gpt-4o-mini"
        self.enabled: bool = False
        self.base_url: str = ""  # For OpenAI Compatible APIs

    async def initialize(self) -> None:
        """Load settings from database."""
        self.provider = await settings.get_setting("ai_provider", "openai")
        self.api_key = await settings.get_setting("ai_api_key", "")
        self.model = await settings.get_setting("ai_model", "gpt-4o-mini")
        self.base_url = await settings.get_setting("ai_base_url", "")
        enabled_str = await settings.get_setting("ai_enabled", "false")
        self.enabled = enabled_str.lower() in ("true", "1", "yes")

    @property
    def is_configured(self) -> bool:
        """Check if AI is properly configured."""
        return bool(self.enabled and self.api_key)

    async def translate_groups(
        self, groups: list[dict], api_type: str
    ) -> list[dict]:
        """
        Translate and categorize groups using AI.
        
        Args:
            groups: List of group dicts with 'name' field
            api_type: API type (newapi, rixapi, other)
            
        Returns:
            Groups with added translation fields (name_en, name_vi, category)
        """
        if not self.is_configured:
            logger.info("AI translation disabled or not configured")
            return groups

        # Filter groups that need translation
        groups_needing_translation = []
        for group in groups:
            if not group.get("name_en") and not group.get("name_vi"):
                groups_needing_translation.append(group)

        if not groups_needing_translation:
            logger.info("All groups already have translations")
            return groups

        # Get cached translations
        cached = await self._get_cached_translations(
            [g["name"] for g in groups_needing_translation], api_type
        )

        # Filter out already cached
        to_translate = [g for g in groups_needing_translation if g["name"] not in cached]
        
        if not to_translate:
            # Apply cached translations
            return self._apply_translations(groups, cached, api_type)

        # Call AI for new translations
        new_translations = await self._call_ai(to_translate, api_type)
        
        # Save to cache
        await self._save_translations(new_translations, api_type)
        
        # Merge all translations
        all_translations = {**cached, **new_translations}
        return self._apply_translations(groups, all_translations, api_type)

    async def _get_cached_translations(
        self, group_names: list[str], api_type: str
    ) -> dict[str, dict]:
        """Get cached translations from database."""
        if not group_names:
            return {}
            
        db = await get_db()
        placeholders = ",".join("?" * len(group_names))
        
        cursor = await db.execute(
            f"""SELECT original_name, name_en, name_vi, category, desc_en, desc_vi 
                FROM group_translations 
                WHERE original_name IN ({placeholders}) AND api_type = ?""",
            (*group_names, api_type)
        )
        rows = await cursor.fetchall()
        
        translations = {}
        for row in rows:
            translations[row[0]] = {
                "name_en": row[1],
                "name_vi": row[2],
                "category": row[3],
                "desc_en": row[4],
                "desc_vi": row[5],
            }
        return translations

    async def _save_translations(
        self, translations: dict[str, dict], api_type: str
    ) -> None:
        """Save translations to cache."""
        if not translations:
            return
            
        db = await get_db()
        
        for original_name, trans in translations.items():
            await db.execute(
                """INSERT INTO group_translations 
                   (original_name, api_type, name_en, name_vi, category, desc_en, desc_vi, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now', '+7 hours'))
                   ON CONFLICT(original_name, api_type) DO UPDATE
                   SET name_en = excluded.name_en,
                       name_vi = excluded.name_vi,
                       category = excluded.category,
                       desc_en = excluded.desc_en,
                       desc_vi = excluded.desc_vi,
                       updated_at = excluded.updated_at""",
                (original_name, api_type, trans.get("name_en"), trans.get("name_vi"),
                 trans.get("category"), trans.get("desc_en"), trans.get("desc_vi"))
            )
        await db.commit()
        logger.info(f"Saved {len(translations)} translations to cache")

    def _apply_translations(
        self, groups: list[dict], translations: dict[str, dict], api_type: str
    ) -> list[dict]:
        """Apply translations to groups."""
        result = []
        for group in groups:
            name = group.get("name", "")
            trans = translations.get(name, {})
            
            # Determine label_vi
            label_vi = trans.get("name_vi") or name
            
            result.append({
                **group,
                "name_en": trans.get("name_en") or name,
                "name_vi": label_vi,
                "label_vi": label_vi,
                "category": trans.get("category") or "Other",
                "desc_en": trans.get("desc_en", ""),
                "desc_vi": trans.get("desc_vi", ""),
            })
        return result

    async def _call_ai(self, groups: list[dict], api_type: str) -> dict[str, dict]:
        """Call AI API to translate groups."""
        if not self.api_key:
            return {}

        group_list = "\n".join([f"- {g['name']}" for g in groups])
        
        system_prompt = """You are a helpful assistant that translates and categorizes API group names.
For each group name, provide:
1. English translation (name_en)
2. Vietnamese translation (name_vi)
3. Category (one of: Azure, OpenAI, Claude, Gemini, DeepSeek, Anthropic, Google, Microsoft, Meta, Other)
4. Brief English description (desc_en)
5. Brief Vietnamese description (desc_vi)

Respond in JSON format:
{
  "GroupName": {
    "name_en": "English Name",
    "name_vi": "Tên Tiếng Việt",
    "category": "Category",
    "desc_en": "English description",
    "desc_vi": "Mô tả Tiếng Việt"
  }
}

Categories should be: Azure, OpenAI, Claude, Gemini, DeepSeek, Anthropic, Google, Microsoft, Meta, or Other"""

        user_prompt = f"""Translate and categorize these API groups (api_type: {api_type}):

{group_list}

Respond with JSON only."""

        try:
            if self.provider == "openai":
                return await self._call_openai(system_prompt, user_prompt)
            elif self.provider == "openai_compatible":
                return await self._call_openai_compatible(system_prompt, user_prompt)
            elif self.provider == "anthropic":
                return await self._call_anthropic(system_prompt, user_prompt)
            elif self.provider == "gemini":
                return await self._call_gemini(system_prompt, user_prompt)
            else:
                logger.warning(f"Unknown AI provider: {self.provider}")
                return {}
        except Exception as e:
            logger.error(f"AI translation failed: {e}")
            return {}

    async def _call_openai(self, system_prompt: str, user_prompt: str) -> dict:
        """Call OpenAI API."""
        import aiohttp
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.3,
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    logger.error(f"OpenAI API error: {resp.status} - {text}")
                    return {}
                    
                data = await resp.json()
                content = data["choices"][0]["message"]["content"]
                
                # Extract JSON from response
                return self._parse_ai_response(content)

    async def _call_openai_compatible(self, system_prompt: str, user_prompt: str) -> dict:
        """Call OpenAI Compatible API (Ollama, LM Studio, etc.)."""
        import aiohttp
        
        if not self.base_url:
            logger.error("OpenAI Compatible: base_url not configured")
            return {}
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.3,
        }
        
        # Normalize OpenAI-compatible base URL.
        base_url = self.base_url.rstrip("/")
        if base_url.endswith("/v1"):
            endpoint = f"{base_url}/chat/completions"
        else:
            endpoint = f"{base_url}/v1/chat/completions"
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                endpoint,
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=60)
            ) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    logger.error(f"OpenAI Compatible API error: {resp.status} - {text}")
                    return {}
                    
                data = await resp.json()
                content = data["choices"][0]["message"]["content"]
                
                return self._parse_ai_response(content)

    async def _call_anthropic(self, system_prompt: str, user_prompt: str) -> dict:
        """Call Anthropic API."""
        import aiohttp
        
        headers = {
            "x-api-key": self.api_key,
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
        }
        
        payload = {
            "model": self.model,
            "max_tokens": 1024,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.anthropic.com/v1/messages",
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    logger.error(f"Anthropic API error: {resp.status} - {text}")
                    return {}
                    
                data = await resp.json()
                content = data["content"][0]["text"]
                return self._parse_ai_response(content)

    async def _call_gemini(self, system_prompt: str, user_prompt: str) -> dict:
        """Call Gemini API."""
        import aiohttp
        
        # Convert model name if needed
        model = self.model
        if not model.startswith("gemini-"):
            model = f"gemini-{model}"
            
        headers = {
            "Content-Type": "application/json",
        }
        
        payload = {
            "contents": [
                {"role": "user", "parts": [{"text": f"{system_prompt}\n\n{user_prompt}"}]}
            ],
            "generationConfig": {
                "temperature": 0.3,
                "maxOutputTokens": 1024,
            },
        }
        
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={self.api_key}"
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    logger.error(f"Gemini API error: {resp.status} - {text}")
                    return {}
                    
                data = await resp.json()
                content = data["candidates"][0]["content"]["parts"][0]["text"]
                return self._parse_ai_response(content)

    def _parse_ai_response(self, content: str) -> dict:
        """Parse JSON from AI response."""
        try:
            # Try to find JSON in the response
            start = content.find("{")
            end = content.rfind("}") + 1
            if start >= 0 and end > start:
                json_str = content[start:end]
                return json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI response: {e}")
        return {}

    async def test_connection(self) -> tuple[bool, str]:
        """Test AI connection."""
        if not self.api_key:
            return False, "API key not configured"
            
        try:
            # Simple test prompt
            result = await self._call_ai(
                [{"name": "test"}], "newapi"
            )
            if result:
                return True, "Connected successfully"
            return False, "Failed to get response"
        except Exception as e:
            return False, str(e)


# Global instance
_translator: AITranslator | None = None


async def get_translator() -> AITranslator:
    """Get or create translator instance."""
    global _translator
    if _translator is None:
        _translator = AITranslator()
        await _translator.initialize()
    return _translator
