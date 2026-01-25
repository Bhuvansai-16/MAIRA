from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq

# Gemini - Best tool calling support for DeepAgents
model = ChatGoogleGenerativeAI(model="models/gemini-2.5-pro", temperature=0)

# Alternative models (have tool calling issues with DeepAgents):
model1 = ChatGoogleGenerativeAI(model="models/gemini-2.5-flash-lite")
model2 = ChatGroq(model="openai/gpt-oss-120b", temperature=0)
#model1 = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)  # Tool calling format incompatible
#model2 = ChatGroq(model="llama-3.1-8b-instant", temperature=0)
#model = ChatGroq(model="qwen/qwen3-32b",temperature=0.2)