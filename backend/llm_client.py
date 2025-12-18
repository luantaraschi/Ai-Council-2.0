"""LLM Client for direct API calls to OpenAI and Google Gemini."""

import httpx
from typing import List, Dict, Any, Optional
from .config import OPENAI_API_KEY, GOOGLE_API_KEY


async def query_openai(model_name: str, messages: List[Dict[str, str]], timeout: float = 120.0) -> Optional[Dict[str, Any]]:
    """
    Query OpenAI API directly.
    
    Args:
        model_name: Model name without provider prefix (e.g., "gpt-5")
        messages: List of message dicts with 'role' and 'content'
        timeout: Request timeout in seconds
    
    Returns:
        Response dict with 'content', or None if failed
    """
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    
    payload = {
        "model": model_name,
        "messages": messages,
    }
    
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            
            data = response.json()
            message = data['choices'][0]['message']
            
            return {
                'content': message.get('content'),
                'reasoning_details': message.get('reasoning_details')
            }
    
    except httpx.HTTPStatusError as e:
        print(f"OpenAI API error for {model_name}: {e.response.status_code} - {e.response.text}")
        return None
    except Exception as e:
        print(f"Error querying OpenAI model {model_name}: {e}")
        return None


async def query_gemini(model_name: str, messages: List[Dict[str, str]], timeout: float = 120.0) -> Optional[Dict[str, Any]]:
    """
    Query Google Gemini API directly.
    
    Args:
        model_name: Model name without provider prefix (e.g., "gemini-3-pro-preview")
        messages: List of message dicts with 'role' and 'content'
        timeout: Request timeout in seconds
    
    Returns:
        Response dict with 'content', or None if failed
    """
    # Convert OpenAI-style messages to Gemini format
    contents = []
    system_instruction = None
    
    for msg in messages:
        role = msg['role']
        content = msg['content']
        
        if role == 'system':
            system_instruction = content
        elif role == 'user':
            contents.append({
                "role": "user",
                "parts": [{"text": content}]
            })
        elif role == 'assistant':
            contents.append({
                "role": "model",
                "parts": [{"text": content}]
            })
    
    payload = {
        "contents": contents,
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 8192,
        }
    }
    
    if system_instruction:
        payload["systemInstruction"] = {
            "parts": [{"text": system_instruction}]
        }
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={GOOGLE_API_KEY}"
    
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                url,
                headers={"Content-Type": "application/json"},
                json=payload
            )
            response.raise_for_status()
            
            data = response.json()
            
            # Extract text from Gemini response
            if 'candidates' in data and len(data['candidates']) > 0:
                candidate = data['candidates'][0]
                if 'content' in candidate and 'parts' in candidate['content']:
                    text_parts = [part.get('text', '') for part in candidate['content']['parts']]
                    return {
                        'content': ''.join(text_parts),
                        'reasoning_details': None
                    }
            
            return None
    
    except Exception as e:
        print(f"Error querying Gemini model {model_name}: {e}")
        return None


async def query_model(
    model: str,
    messages: List[Dict[str, str]],
    timeout: float = 120.0
) -> Optional[Dict[str, Any]]:
    """
    Query a model via the appropriate API based on provider prefix.
    
    Args:
        model: Model identifier with provider prefix (e.g., "openai/gpt-5", "google/gemini-3-pro-preview")
        messages: List of message dicts with 'role' and 'content'
        timeout: Request timeout in seconds
    
    Returns:
        Response dict with 'content' and optional 'reasoning_details', or None if failed
    """
    if model.startswith("openai/"):
        model_name = model.replace("openai/", "")
        return await query_openai(model_name, messages, timeout)
    elif model.startswith("google/"):
        model_name = model.replace("google/", "")
        return await query_gemini(model_name, messages, timeout)
    else:
        print(f"Unknown provider for model: {model}")
        return None


async def query_models_parallel(
    models: List[str],
    messages: List[Dict[str, str]]
) -> Dict[str, Optional[Dict[str, Any]]]:
    """
    Query multiple models in parallel.
    
    Args:
        models: List of model identifiers with provider prefixes
        messages: List of message dicts to send to each model
    
    Returns:
        Dict mapping model identifier to response dict (or None if failed)
    """
    import asyncio
    
    # Create tasks for all models
    tasks = [query_model(model, messages) for model in models]
    
    # Wait for all to complete
    responses = await asyncio.gather(*tasks)
    
    # Map models to their responses
    return {model: response for model, response in zip(models, responses)}
