from dotenv import load_dotenv
load_dotenv()

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from langchain_anthropic import ChatAnthropic
from langchain_aws import ChatBedrockConverse
import os

# AWS Credentials
aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID")
aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY")

# =====================================================
# AVAILABLE MODELS (for frontend model selector)
# =====================================================
AVAILABLE_MODELS = {
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
    "gemini-2.5-flash-lite": {
        "name": "Gemini 2.5 Flash Lite",
        "provider": "google",
        "model_id": "models/gemini-2.5-flash-lite",
        "category": "Fast and cost-efficient",
        "icon": "gemini"
    },
    "gemini-2.5-pro": {
        "name": "Gemini 2.5 Pro",
        "provider": "google",
        "model_id": "models/gemini-2.5-pro",
        "category": "Most powerful at complex tasks",
        "icon": "gemini"
    },
    "gemini-2.0-flash": {
        "name": "Gemini 2.0 Flash",
        "provider": "google",
        "model_id": "models/gemini-2.0-flash",
        "category": "Fast and cost-efficient",
        "icon": "gemini"
    },
    "gpt-oss-120b": {
        "name": "GPT OSS 120B",
        "provider": "groq",
        "model_id": "openai/gpt-oss-120b",
        "category": "Versatile and highly intelligent",
        "icon": "openai"
    },
    "llama-3.3-70b-versatile": {
        "name": "LLaMA 3.3 70B Versatile",
        "provider": "groq",
        "model_id": "llama-3.3-70b-versatile",
        "category": "Versatile and highly intelligent",
        "icon": "meta"
    },
    "llama-3.1-8b-instant":{
        "name": "LLaMA 3.1 8B Instant",
        "provider": "groq",
        "model_id": "llama-3.1-8b-instant",
        "category": "Fast and cost-efficient",
        "icon": "meta"
    },
    "kimi-k2-instruct-0905": {
        "name": "Kimi K2 Instruct",
        "provider": "groq",
        "model_id": "moonshotai/kimi-k2-instruct-0905",
        "category": "Most powerful at complex tasks",
        "icon": "moonshotai"
    },
    "claude-opus-4.5": {
        "name": "Claude Opus 4.5",
        "provider": "anthropic",
        "model_id": "claude-opus-4-5-20251101",
        "category": "Most powerful at complex tasks",
        "icon": "anthropic"
    },
    "claude-sonnet-4.5": {
        "name": "Claude Sonnet 4.5",
        "provider": "anthropic",
        "model_id": "claude-sonnet-4-5-20250929",
        "category": "Versatile and highly intelligent",
        "icon": "anthropic"
    },
    "claude-3-5-sonnet-aws": {
        "name": "Claude 3.5 Sonnet AWS",
        "provider": "aws",
        "model_id": "anthropic.claude-3-5-sonnet-20240620-v1:0",
        "category": "Fast and cost-efficient",
        "icon": "anthropic"
    },
    "anthropic.claude-sonnet-4-5-20250929-v1:0": {
        "name": "Claude Sonnet 4.5 AWS",
        "provider": "aws",
        "model_id": "global.anthropic.claude-sonnet-4-5-20250929-v1:0",
        "category": "Versatile and highly intelligent",
        "icon": "anthropic"
    },
    "anthropic.claude-opus-4-6-v1": {
        "name": "Claude Opus 4.6 AWS",
        "provider": "aws",
        "model_id": "global.anthropic.claude-opus-4-6-v1",
        "category": "Most powerful at complex tasks",
        "icon": "anthropic"
    }
}

# Default model key
DEFAULT_MODEL = "anthropic.claude-opus-4-6-v1"
_current_model_key = DEFAULT_MODEL


# =====================================================
# MODEL INSTANCES - Import these directly in your agents
# =====================================================

# Google Models (max_retries for transient 500 errors)
gemini_3_pro = ChatGoogleGenerativeAI(model="models/gemini-3-pro-preview", temperature=0, max_retries=3)
gemini_3_flash = ChatGoogleGenerativeAI(model="models/gemini-3-flash-preview", temperature=0, max_retries=3)
gemini_2_5_pro = ChatGoogleGenerativeAI(model="models/gemini-2.5-pro", temperature=0, max_retries=3)
gemini_2_5_flash_lite = ChatGoogleGenerativeAI(model="models/gemini-2.5-flash-lite", temperature=0, max_retries=3)
gemini_2_flash = ChatGoogleGenerativeAI(model="models/gemini-2.0-flash", temperature=0, max_retries=3)

# Groq Models
llama_70b = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)
llama_8b = ChatGroq(model="llama-3.1-8b-instant", temperature=0)
gpt_oss_120b = ChatGroq(model="openai/gpt-oss-120b", temperature=0)
kimi_k2 = ChatGroq(model="moonshotai/kimi-k2-instruct-0905", temperature=0)

# Anthropic Direct Models
claude_opus_4_5 = ChatAnthropic(model="claude-opus-4-5-20251101", temperature=0.2)
claude_sonnet_4_5 = ChatAnthropic(model="claude-sonnet-4-5-20250929", temperature=0.2)

# AWS Bedrock Models
claude_3_5_sonnet_aws = ChatBedrockConverse(
    model_id="anthropic.claude-3-5-sonnet-20240620-v1:0",
    region_name="us-east-1",
    aws_access_key_id=aws_access_key_id,
    aws_secret_access_key=aws_secret_access_key,
    temperature=0.2,
)

claude_sonnet_4_5_aws = ChatBedrockConverse(
    model_id="global.anthropic.claude-sonnet-4-5-20250929-v1:0",
    region_name="us-east-1",
    aws_access_key_id=aws_access_key_id,
    aws_secret_access_key=aws_secret_access_key,
    temperature=0.2,
)

claude_opus_4_6_aws = ChatBedrockConverse(
    model_id="global.anthropic.claude-opus-4-6-v1",
    region_name="us-east-1",
    aws_access_key_id=aws_access_key_id,
    aws_secret_access_key=aws_secret_access_key,
    temperature=0.2,
)


# =====================================================
# HELPER FUNCTIONS (for frontend model selector)
# =====================================================

def get_model_instance(model_key: str = None):
    """Create and return a model instance based on the model key"""
    key = model_key or _current_model_key
    if key not in AVAILABLE_MODELS:
        key = DEFAULT_MODEL
    
    config = AVAILABLE_MODELS[key]
    provider = config["provider"]
    model_id = config["model_id"]
    
    if provider == "google":
        return ChatGoogleGenerativeAI(model=model_id, temperature=0, max_retries=3)
    elif provider == "groq":
        return ChatGroq(model=model_id, temperature=0)
    elif provider == "anthropic":
        return ChatAnthropic(model=model_id, temperature=0.2)
    elif provider == "aws":
        return ChatBedrockConverse(
            model_id=model_id,
            region_name="us-east-1",
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            temperature=0.2,
        )
    else:
        raise ValueError(f"Unknown provider: {provider}")


def set_current_model(model_key: str):
    """Set the current active model"""
    global _current_model_key
    if model_key in AVAILABLE_MODELS:
        _current_model_key = model_key
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


# =====================================================
# DEFAULT EXPORTS
# =====================================================
# Main agent model (default: Claude Opus 4.6 AWS)
main_agent_model = gemini_3_pro

# Subagent model (default: Claude Sonnet 4.5 AWS)
subagent_model = gemini_3_flash

print("✅ Config loaded - Models ready for import")
