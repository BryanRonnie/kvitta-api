from http.client import HTTPException
import os
from typing import List

import requests
from fastapi import HTTPException
from typing import List, Optional


def call_nvidia_llama_vision(
    image_files_base64: Optional[List[tuple[str, str]]] = None,
    prompt: str = ""
) -> str:
    """
    Call NVIDIA Llama 3.2 90B Vision Instruct model with base64-encoded images.
    
    Args:
        image_files_base64: Optional list of tuples (mime_type, base64_data)
                           e.g., [("image/png", "iVBORw0KG..."), ("image/jpeg", "...")]
        prompt: Text prompt to send along with images
    
    Returns:
        Model response text
    """
    api_key = os.getenv("NVIDIA_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="NVIDIA_API_KEY not configured."
        )

    invoke_url = "https://integrate.api.nvidia.com/v1/chat/completions"
    
    # Build content array with text + images
    content = [{"type": "text", "text": prompt}]
    if image_files_base64:
        for mime_type_val, base64_data in image_files_base64:
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:{mime_type_val};base64,{base64_data}"
                }
            })
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    
    payload = {
        "model": "meta/llama-3.2-90b-vision-instruct",
        "messages": [
            {
                "role": "user",
                "content": content
            }
        ],
        "max_tokens": 4096,
        "temperature": 1.0,
        "top_p": 1.0,
        "frequency_penalty": 0.0,
        "presence_penalty": 0.0,
    }

    try:
        resp = requests.post(invoke_url, headers=headers, json=payload, timeout=120)
        
        # Log response for debugging
        if resp.status_code != 200:
            error_body = resp.text
            print(f"❌ Llama API error {resp.status_code}: {error_body}")
            raise HTTPException(
                status_code=500, 
                detail=f"Llama Vision API error: {resp.status_code} - {error_body[:500]}"
            )
        
        resp.raise_for_status()
        data = resp.json()
        choices = data.get("choices", [])
        if not choices:
            raise ValueError("No choices returned from Llama API")
        message = choices[0].get("message", {})
        content = message.get("content")
        if not content:
            raise ValueError("Empty content from Llama API")
        return content
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Llama Vision API error: {str(e)}")
