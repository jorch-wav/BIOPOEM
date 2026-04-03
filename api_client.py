#!/usr/bin/env python3
# VERSION: 1.0.2 - Last updated: 2025-11-19
# Updated to Claude 4.5 Sonnet (claude-sonnet-4-5)
"""
BIOPOEM API Integration Module
Handles communication with OpenAI GPT-4 and Anthropic Claude APIs
"""

import os
import json
import time
from datetime import datetime
from typing import Optional, Dict, Any

# API client imports (install these on Raspberry Pi)
try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False


class PoemAPIClient:
    """Handles API calls to generate poems"""
    
    def __init__(self, api_type="openai", api_key=None, model=None):
        """
        Initialize API client
        
        Args:
            api_type: "openai" or "anthropic"
            api_key: API key (or set via environment variable)
            model: Model name (default: gpt-4 or claude-sonnet-4-5)
        """
        self.api_type = api_type.lower()
        
        # Get API key from parameter or environment
        if api_key:
            self.api_key = api_key
        elif self.api_type == "openai":
            self.api_key = os.getenv("OPENAI_API_KEY")
        elif self.api_type == "anthropic":
            self.api_key = os.getenv("ANTHROPIC_API_KEY")
        else:
            raise ValueError(f"Unknown API type: {api_type}")
        
        if not self.api_key:
            raise ValueError(f"API key not provided. Set {self.api_type.upper()}_API_KEY environment variable")
        
        # Set default models
        if model:
            self.model = model
        elif self.api_type == "openai":
            self.model = "gpt-4"  # or "gpt-4-turbo-preview"
        elif self.api_type == "anthropic":
            self.model = "claude-sonnet-4-5"
        
        # Initialize client
        if self.api_type == "openai":
            if not OPENAI_AVAILABLE:
                raise ImportError("OpenAI library not installed. Run: pip install openai")
            self.client = openai.OpenAI(api_key=self.api_key)
        elif self.api_type == "anthropic":
            if not ANTHROPIC_AVAILABLE:
                raise ImportError("Anthropic library not installed. Run: pip install anthropic")
            self.client = anthropic.Anthropic(api_key=self.api_key)
    
    def validate_poem_length(self, poem_text: str, max_lines: int = 15) -> tuple:
        """
        Validate poem doesn't exceed max line count
        
        Args:
            poem_text: The poem text to validate
            max_lines: Maximum allowed lines (default 15)
        
        Returns:
            tuple: (is_valid, message, line_count)
        """
        lines = [l.strip() for l in poem_text.split('\n') if l.strip()]
        line_count = len(lines)
        
        if line_count > max_lines:
            return False, f"Poem has {line_count} lines (max: {max_lines})", line_count
        
        return True, "OK", line_count
    
    def generate_poem(self, prompt: str, max_retries: int = 3) -> Dict[str, Any]:
        """
        Generate poem from prompt
        
        Args:
            prompt: Complete prompt for poem generation
            max_retries: Number of retry attempts on failure
        
        Returns:
            dict with 'poem', 'success', 'error', 'metadata'
        """
        
        for attempt in range(max_retries):
            try:
                if self.api_type == "openai":
                    return self._generate_openai(prompt)
                elif self.api_type == "anthropic":
                    return self._generate_anthropic(prompt)
            
            except Exception as e:
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 2  # Exponential backoff
                    print(f"⚠️  Attempt {attempt + 1} failed: {e}")
                    print(f"   Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    return {
                        "success": False,
                        "poem": None,
                        "error": str(e),
                        "metadata": {
                            "attempts": attempt + 1,
                            "api_type": self.api_type,
                            "model": self.model
                        }
                    }
        
        return {
            "success": False,
            "poem": None,
            "error": "Max retries exceeded",
            "metadata": {"attempts": max_retries}
        }
    
    def _generate_openai(self, prompt: str) -> Dict[str, Any]:
        """Generate using OpenAI API"""
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": "You are a poet channeling the voice of a living plant. You write with authenticity, grounded in sensor data, while channeling various poetic traditions. You output only the poem itself - no titles, no explanations, no meta-commentary."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.85,  # Creative but not chaotic
            max_tokens=2000,
            presence_penalty=0.3,
            frequency_penalty=0.2   # Reduce repetition
        )
        
        poem_text = response.choices[0].message.content.strip()
        
        # Validate poem length
        is_valid, msg, line_count = self.validate_poem_length(poem_text)
        
        metadata = {
            "api_type": "openai",
            "model": self.model,
            "tokens_used": response.usage.total_tokens,
            "finish_reason": response.choices[0].finish_reason,
            "line_count": line_count,
            "length_validation": msg
        }
        
        if not is_valid:
            print(f"[VALIDATION WARNING] {msg}")
            # Still return the poem but flag it
            metadata["validation_failed"] = True
        
        return {
            "success": True,
            "poem": poem_text,
            "error": None,
            "metadata": metadata
        }
    
    def _generate_anthropic(self, prompt: str) -> Dict[str, Any]:
        """Generate using Anthropic Claude API"""
        
        message = self.client.messages.create(
            model=self.model,
            max_tokens=2000,
            temperature=0.85,
            system="You are a poet channeling the voice of a living plant. You write with authenticity, grounded in sensor data, while channeling various poetic traditions. You output only the poem itself - no titles, no explanations, no meta-commentary.",
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )
        
        poem_text = message.content[0].text.strip()
        
        # Validate poem length
        is_valid, msg, line_count = self.validate_poem_length(poem_text)
        
        metadata = {
            "api_type": "anthropic",
            "model": self.model,
            "tokens_input": message.usage.input_tokens,
            "tokens_output": message.usage.output_tokens,
            "stop_reason": message.stop_reason,
            "line_count": line_count,
            "length_validation": msg
        }
        
        if not is_valid:
            print(f"[VALIDATION WARNING] {msg}")
            # Still return the poem but flag it
            metadata["validation_failed"] = True
        
        return {
            "success": True,
            "poem": poem_text,
            "error": None,
            "metadata": metadata
        }



class ComparisonAPIClient:
    """Generate poems from both OpenAI and Anthropic simultaneously for comparison"""
    
    def __init__(self, openai_key=None, anthropic_key=None):
        """
        Initialize comparison client
        
        Args:
            openai_key: OpenAI API key
            anthropic_key: Anthropic API key
        """
        # Initialize both clients
        self.openai_client = PoemAPIClient("openai", api_key=openai_key, model="gpt-4")
        self.anthropic_client = PoemAPIClient("anthropic", api_key=anthropic_key, model="claude-sonnet-4-5")
    
    def generate_both(self, prompt: str, max_retries: int = 3):
        """
        Generate poems from both APIs
        
        Args:
            prompt: Complete prompt
            max_retries: Retries per API
        
        Returns:
            tuple: (claude_result, gpt_result) - each is a dict with poem and metadata
        """
        print("🤖 Generating poems from both APIs...")
        
        # Generate from Claude
        print("  → Claude Sonnet 3.5...")
        claude_result = self.anthropic_client.generate_poem(prompt, max_retries=max_retries)
        
        # Generate from ChatGPT
        print("  → ChatGPT GPT-4...")
        gpt_result = self.openai_client.generate_poem(prompt, max_retries=max_retries)
        
        return (claude_result, gpt_result)


class AlternatingAPIClient:
    """Alternate between OpenAI and Anthropic for variety"""
    
    def __init__(self, openai_key=None, anthropic_key=None, state_file="api_state.json"):
        """
        Initialize alternating client
        
        Args:
            openai_key: OpenAI API key
            anthropic_key: Anthropic API key
            state_file: File to track which API was used last
        """
        self.state_file = state_file
        
        # Initialize both clients
        self.openai_client = PoemAPIClient("openai", api_key=openai_key)
        self.anthropic_client = PoemAPIClient("anthropic", api_key=anthropic_key)
        
        # Load state
        self.state = self._load_state()
    
    def _load_state(self):
        """Load API usage state"""
        if os.path.exists(self.state_file):
            with open(self.state_file, 'r') as f:
                return json.load(f)
        return {"last_used": None, "openai_count": 0, "anthropic_count": 0}
    
    def _save_state(self):
        """Save API usage state"""
        with open(self.state_file, 'w') as f:
            json.dump(self.state, f, indent=2)
    
    def generate_poem(self, prompt: str, max_retries: int = 3) -> Dict[str, Any]:
        """
        Generate poem, alternating between APIs
        
        Args:
            prompt: Complete prompt
            max_retries: Retries per API
        
        Returns:
            dict with poem and metadata
        """
        
        # Determine which API to use
        if self.state["last_used"] == "openai":
            primary = self.anthropic_client
            fallback = self.openai_client
            primary_name = "anthropic"
            fallback_name = "openai"
        else:
            primary = self.openai_client
            fallback = self.anthropic_client
            primary_name = "openai"
            fallback_name = "anthropic"
        
        print(f"🤖 Using {primary_name.upper()} API...")
        
        # Try primary API
        result = primary.generate_poem(prompt, max_retries=max_retries)
        
        if result["success"]:
            # Update state
            self.state["last_used"] = primary_name
            self.state[f"{primary_name}_count"] += 1
            self._save_state()
            return result
        
        # Fallback to other API
        print(f"⚠️  {primary_name.upper()} failed, trying {fallback_name.upper()}...")
        result = fallback.generate_poem(prompt, max_retries=max_retries)
        
        if result["success"]:
            self.state["last_used"] = fallback_name
            self.state[f"{fallback_name}_count"] += 1
            self._save_state()
        
        return result


# Configuration helper
def load_api_config(config_file="api_config.json"):
    """
    Load API configuration from file
    
    Expected format:
    {
        "api_type": "openai" | "anthropic" | "alternating",
        "openai_key": "sk-...",
        "anthropic_key": "sk-ant-...",
        "openai_model": "gpt-4",
        "anthropic_model": "claude-sonnet-4-5"
    }
    """
    if os.path.exists(config_file):
        with open(config_file, 'r') as f:
            return json.load(f)
    
    # Return defaults (will try environment variables)
    return {
        "api_type": os.getenv("BIOPOEM_API_TYPE", "openai"),
        "openai_key": os.getenv("OPENAI_API_KEY"),
        "anthropic_key": os.getenv("ANTHROPIC_API_KEY")
    }


# Example usage
if __name__ == "__main__":
    print("\n" + "="*70)
    print("  BIOPOEM API Client - Test")
    print("="*70 + "\n")
    
    # Test prompt
    test_prompt = """Generate a poem from the perspective of a living plant.

Current state: Thirsty (52% soil moisture)
Voltage: 0.84V (low, strained)
Temperature: 19°C
Light: 4 lux (nighttime)

Style: Write in the style of Mary Oliver - attentive, grounded, present.

Write a short poem (10 lines) from the plant's perspective about waiting for water.
"""
    
    print("Test Prompt:")
    print("-" * 70)
    print(test_prompt)
    print("-" * 70 + "\n")
    
    # Try to load config
    config = load_api_config()
    
    if config.get("openai_key") or os.getenv("OPENAI_API_KEY"):
        print("✅ OpenAI API key found")
        print("Testing OpenAI API...\n")
        
        try:
            client = PoemAPIClient("openai")
            result = client.generate_poem(test_prompt)
            
            if result["success"]:
                print("✅ Success!\n")
                print("GENERATED POEM:")
                print("-" * 70)
                print(result["poem"])
                print("-" * 70)
                print(f"\nTokens used: {result['metadata'].get('tokens_used', 'N/A')}")
            else:
                print(f"❌ Failed: {result['error']}")
        
        except Exception as e:
            print(f"❌ Error: {e}")
    
    else:
        print("⚠️  No API key found")
        print("\nTo test, set environment variable:")
        print("  export OPENAI_API_KEY='sk-...'")
        print("  export ANTHROPIC_API_KEY='sk-ant-...'")
        print("\nOr create api_config.json:")
        print("""  {
    "api_type": "openai",
    "openai_key": "sk-..."
  }""")
    
    print()
