from dotenv import load_dotenv
load_dotenv()

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from langchain_anthropic import ChatAnthropic
import os

# =====================================================
# AVAILABLE MODELS (for frontend model selector)
# =====================================================
AVAILABLE_MODELS = {
    "gemini-3.1-pro-preview": {
        "name": "Gemini 3.1 Pro",
        "provider": "google",
        "model_id": "models/gemini-3.1-pro-preview",
        "category": "Most powerful at complex tasks",
        "icon": "gemini"
    },
    "gemini-3-pro-preview": {
        "name": "Gemini 3 Pro",
        "provider": "google",
        "model_id": "models/gemini-3-pro-preview",
        "category": "Most powerful at complex tasks",
        "icon": "gemini"
    },
    "gemini-3-flash-preview": {
        "name": "Gemini 3 Flash",
        "provider": "google",
        "model_id": "models/gemini-3-flash-preview",
        "category": "Fast and cost-efficient",
        "icon": "gemini"
    },
    "gemini-2.5-pro": {
        "name": "Gemini 2.5 Pro",
        "provider": "google",
        "model_id": "models/gemini-2.5-pro",
        "category": "Versatile and highly intelligent",
        "icon": "gemini"
    },
    "gpt-oss-120b": {
        "name": "GPT OSS 120B",
        "provider": "groq",
        "model_id": "openai/gpt-oss-120b",
        "category": "Versatile and highly intelligent",
        "icon": "openai"
    },
    "claude-opus-4.5": {
        "name": "Claude Opus 4.5",
        "provider": "anthropic",
        "model_id": "claude-opus-4-5-20251101",
        "category": "Most powerful at complex tasks",
        "icon": "anthropic"
    },
    "claude-opus-4.6": {
        "name": "Claude Opus 4.6",
        "provider": "anthropic",
        "model_id": "claude-opus-4-6-20251101", # Hypothetical ID
        "category": "Most powerful at complex tasks",
        "icon": "anthropic"
    }
}

# Default model key
DEFAULT_MODEL = "gemini-3-pro-preview"
_current_model_key = DEFAULT_MODEL


# =====================================================
# MODEL INSTANCES - Import these directly in your agents
# =====================================================

# Google Models (max_retries for transient 500 errors)
gemini_3_1_pro = ChatGoogleGenerativeAI(model="models/gemini-3.1-pro-preview", temperature=0, max_retries=3, timeout=90.0)
gemini_3_pro = ChatGoogleGenerativeAI(model="models/gemini-3-pro-preview", temperature=0, max_retries=3, timeout=90.0)
gemini_2_5_pro = ChatGoogleGenerativeAI(model="models/gemini-2.5-pro", temperature=0, max_retries=3, timeout=90.0)
gemini_2_5_flash_lite = ChatGoogleGenerativeAI(model="models/gemini-2.5-flash-lite", temperature=0, max_retries=3, timeout=90.0)
gemini_2_flash = ChatGoogleGenerativeAI(model="models/gemini-2.0-flash", temperature=0, max_retries=3, timeout=90.0)

# Subagent-specific flash model — capped to prevent silent Gemini truncation on heavy queries.
# max_output_tokens=8192 forces an explicit limit (no silent empty response).
# timeout=180 gives long-running subagents enough time to finish.
gemini_3_flash = ChatGoogleGenerativeAI(
    model="models/gemini-3-flash-preview",
    temperature=0,
    max_retries=2,
    timeout=180.0,
    max_output_tokens=8192,
)

# Groq Models
llama_70b = ChatGroq(model="llama-3.3-70b-versatile", temperature=0,timeout=90.0)
llama_8b = ChatGroq(model="llama-3.1-8b-instant", temperature=0,timeout=90.0)
gpt_oss_120b = ChatGroq(model="openai/gpt-oss-120b", temperature=0,timeout=90.0)
kimi_k2 = ChatGroq(model="moonshotai/kimi-k2-instruct-0905", temperature=0,timeout=90.0)

# Anthropic Direct Models
claude_opus_4_5 = ChatAnthropic(model="claude-opus-4-5", temperature=0,timeout=90.0)
claude_opus_4_6 = ChatAnthropic(model="claude-opus-4-6", temperature=0,timeout=90.0) # New
claude_sonnet_4_5 = ChatAnthropic(model="claude-sonnet-4-5", temperature=0,timeout=90.0)
claude_sonnet_4_6 = ChatAnthropic(model="claude-sonnet-4-6", temperature=0,timeout=90.0)


# =====================================================
# MODEL SELECTION STATE
# =====================================================

main_agent_model = gemini_3_pro
# subagent_model always uses the token-capped flash instance by default.
subagent_model = gemini_3_flash


# =====================================================
# HELPER FUNCTIONS (for frontend model selector)
# =====================================================

def get_model_instance(model_key: str = None):
    """Create and return a model instance based on the model key"""
    # Simply use the pre-defined instances based on key mapping
    # This prevents creating new instances repeatedly
    key = model_key or _current_model_key
    if key == "gemini-3.1-pro-preview": return gemini_3_1_pro
    if key == "gemini-3-pro-preview": return gemini_3_pro
    if key == "gemini-3-flash-preview": return gemini_3_flash
    if key == "gemini-2.5-pro": return gemini_2_5_pro
    if key == "gpt-oss-120b": return gpt_oss_120b
    if key == "claude-opus-4.5": return claude_opus_4_5
    if key == "claude-opus-4.6": return claude_opus_4_6
    
    # Fallback to creating new if needed (legacy behavior)
    config = AVAILABLE_MODELS.get(key, AVAILABLE_MODELS.get(DEFAULT_MODEL))
    provider = config["provider"]
    model_id = config["model_id"]
    
    if provider == "google":
        return ChatGoogleGenerativeAI(model=model_id, temperature=0, max_retries=3)
    elif provider == "groq":
        return ChatGroq(model=model_id, temperature=0)
    elif provider == "anthropic":
        return ChatAnthropic(model=model_id, temperature=0)
    return gemini_3_pro


def set_current_model(model_key: str):
    """Set the current active model and update subagent logic"""
    global _current_model_key, main_agent_model, subagent_model
    
    if model_key in AVAILABLE_MODELS:
        _current_model_key = model_key
        
        # Update Main Agent
        main_agent_model = get_model_instance(model_key)
        
        # Update Subagent Logic based on Main Agent.
        # Gemini subagent models always use the token-capped gemini_3_flash instance.
        # 1) Gemini main models → token-capped Flash subagent
        if model_key in ("gemini-3-pro-preview", "gemini-3-flash-preview", "gemini-2.5-pro"):
            subagent_model = gemini_3_flash
        elif model_key == "gemini-3.1-pro-preview":
            subagent_model = gemini_3_pro  # Pro-level subagent for Pro-level main
        # 2) Anthropic main → Sonnet subagent
        elif model_key == "claude-opus-4.6":
            subagent_model = claude_sonnet_4_6
        elif model_key == "claude-opus-4.5":
            subagent_model = claude_sonnet_4_5
        # 3) Groq main → LLaMA subagent
        elif model_key == "gpt-oss-120b":
            subagent_model = llama_70b
        # Default fallback
        else:
            subagent_model = gemini_3_flash
            
        print(f"Model Switched: Main={model_key}, Subagent={type(subagent_model).__name__}")
        return True
    return False



def get_current_model_key():
    """Get the current model key"""
    return _current_model_key


def get_current_model_info():
    """Get info about the current model"""
    return {
        "key": _current_model_key,
        **AVAILABLE_MODELS.get(_current_model_key, AVAILABLE_MODELS[DEFAULT_MODEL])
    }


print("✅ Config loaded - Models ready for import")