def call_nvidia_nemotron_vision(
    image_files_base64: List[tuple[str, str]],
    prompt: str
) -> str:
    """
    Call NVIDIA Nemotron vision model with base64-encoded images.
    
    Args:
        image_files_base64: List of tuples (mime_type, base64_data)
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
        "model": "nvidia/nemotron-nano-12b-v2-vl",
        "messages": [
            {
                "role": "system",
                "content": "/no_think"
            },
            {
                "role": "user",
                "content": content
            }
        ],
        "max_tokens": 4096,
        "temperature": 1,
        "top_p": 1.0,
        "frequency_penalty": 0.0,
        "presence_penalty": 0.0,
    }

    try:
        resp = requests.post(invoke_url, headers=headers, json=payload, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        choices = data.get("choices", [])
        if not choices:
            raise ValueError("No choices returned from Nemotron API")
        message = choices[0].get("message", {})
        content = message.get("content")
        if not content:
            raise ValueError("Empty content from Nemotron API")
        return content
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Nemotron API error: {str(e)}")
