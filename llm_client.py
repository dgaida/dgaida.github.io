import os
from typing import List, Dict
from groq import Groq

class LLMClient:
    def __init__(self, api_choice: str = "groq", model: str = "llama-3.3-70b-versatile"):
        self.api_choice = api_choice
        self.llm = model
        self.client = Groq(api_key=os.environ.get("GROQ_API_KEY", "dummy_key"))

    def chat_completion(self, messages: List[Dict[str, str]]) -> str:
        if os.environ.get("GROQ_API_KEY") is None:
            # Return a dummy response if no API key is provided, for testing purposes
            if "summary" in messages[0]["content"].lower():
                return "This is a dummy summary of the thesis. It consists of two sentences. It is in English."
            return '{"author": "Test Author", "title": "Test Title", "bachelor_master": "Bachelor"}'

        response = self.client.chat.completions.create(
            messages=messages,
            model=self.llm,
        )
        return response.choices[0].message.content
