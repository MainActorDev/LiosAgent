import os
from typing import Optional
from langchain_core.language_models.chat_models import BaseChatModel

def get_llm(role: str = "default") -> BaseChatModel:
    """
    LLM Factory Pattern to easily swap the AI backend based on the .env
    Supports 'role-based' routing (e.g., planning, coding) so you can use
    different models for different nodes in the LangGraph.
    """
    # Check for role-specific config (e.g., LLM_PROVIDER_PLANNING), fallback to global default
    provider_env_var = f"LLM_PROVIDER_{role.upper()}"
    model_env_var = f"LLM_MODEL_{role.upper()}"
    
    provider = os.getenv(provider_env_var, os.getenv("LLM_PROVIDER", "glm")).lower()
    model_name = os.getenv(model_env_var, os.getenv("LLM_MODEL_NAME", "glm-5.1"))
    
    if provider == "glm":
        # Many GLM endpoints (like ZhipuAI) offer OpenAI compatibility
        from langchain_openai import ChatOpenAI
        
        # Get base URL, default to ZhipuAI endpoint if not provided
        base_url = os.getenv("GLM_API_BASE", "https://open.bigmodel.cn/api/paas/v4/")
        api_key = os.getenv("GLM_API_KEY")
        
        if not api_key:
            raise ValueError("GLM_API_KEY environment variable is not set. Please add it to your .env")
            
        print(f"🔧 Initializing GLM Model: {model_name}")
        return ChatOpenAI(
            model=model_name,
            api_key=api_key,
            base_url=base_url,
            max_tokens=4096,
            temperature=0.0,
            timeout=60.0,
            max_retries=1
        )
        
    elif provider == "openai":
        from langchain_openai import ChatOpenAI
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY is missing.")
        return ChatOpenAI(model=model_name, api_key=api_key, temperature=0.0)
        
    else:
        raise NotImplementedError(f"Provider {provider} not yet supported in factory.")
