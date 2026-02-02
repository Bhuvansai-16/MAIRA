from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from langchain_anthropic import ChatAnthropic


# Gemini - Best tool calling support for DeepAgents
model1 = ChatGoogleGenerativeAI(model="models/gemini-3-pro-preview", temperature=0)
model = ChatGoogleGenerativeAI(model="models/gemini-3-pro-preview", temperature=0)
#model1 = ChatGoogleGenerativeAI(model="models/gemini-3-flash-preview", temperature=0)
#Alternative models (have tool calling issues with DeepAgents):
#model1 = ChatGoogleGenerativeAI(model="models/gemini-2.5-flash-lite")
#model2 = ChatGroq(model="openai/gpt-oss-120b", temperature=0)
#model1 = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)  # Tool calling format incompatible
#model2 = ChatGroq(model="llama-3.1-8b-instant", temperature=0)
#model = ChatGroq(model="qwen/qwen3-32b",temperature=0.2)
#model = ChatAnthropic(model="claude-opus-4-5-20251101",temperature=0.2)
#model1 = ChatAnthropic(model="claude-opus-4-5-20251101",temperature=0.2)