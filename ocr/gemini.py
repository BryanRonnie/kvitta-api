import base64
import os
from typing import Dict, List
import requests

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

if not GEMINI_API_KEY:
    print("WARNING: GEMINI_API_KEY environment variable not set - Gemini OCR will not work")

def _gemini_generate_content(parts: List[Dict], temperature: float = 0.6, max_output_tokens: int = 4096) -> str:
    from fastapi import HTTPException as FastAPIHTTPException

    if not GEMINI_API_KEY:
        raise FastAPIHTTPException(
            status_code=500,
            detail="GEMINI_API_KEY not configured on server"
        )

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": parts
            }
        ],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_output_tokens
        }
    }

    try:
        response = requests.post(url, json=payload, timeout=120)
        if response.status_code != 200:
            raise FastAPIHTTPException(
                status_code=500,
                detail=f"Gemini API request failed: {response.text}"
            )

        data = response.json()
        candidates = data.get("candidates", [])
        if not candidates:
            return ""

        content = candidates[0].get("content", {})
        parts_out = content.get("parts", [])
        return "".join(part.get("text", "") for part in parts_out if isinstance(part, dict))
    except FastAPIHTTPException:
        raise
    except Exception as e:
        raise FastAPIHTTPException(
            status_code=500,
            detail=f"Gemini API request failed: {str(e)}"
        )


def _gemini_extract_text_from_image(image_bytes: bytes, mime_type: str) -> str:
    prompt = (
        "Extract all visible text from this image. "
        "Return text only and preserve line breaks where possible."
    )
    parts = [
        {"text": prompt},
        {
            "inlineData": {
                "mimeType": mime_type,
                "data": base64.b64encode(image_bytes).decode("utf-8")
            }
        }
    ]
    return _gemini_generate_content(parts, temperature=0.0, max_output_tokens=2048)

@app.post("/gemini-ocr/extract-text")
async def extract_text_gemini(
    items_images: Optional[List[UploadFile]] = File(None),
    charges_image: Optional[UploadFile] = File(None),
    run_llm: bool = True,
    llm_temperature: float = 0.6,
    llm_max_tokens: int = 4096
):
    """
    Extract text from receipt using Gemini and run PROMPT_ITEMS / PROMPT_CHARGES.

    Input/Output format mirrors /nvidia-ocr/extract-text.
    """
    if not GEMINI_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="GEMINI_API_KEY not configured on server"
        )

    if not items_images or not charges_image:
        raise HTTPException(
            status_code=400,
            detail="Must provide (items_images + charges_image)"
        )

    try:
        items_texts = []
        for item_image in items_images:
            image_data = await item_image.read()
            mime_type = item_image.content_type or "image/jpeg"
            items_texts.append(_gemini_extract_text_from_image(image_data, mime_type))

        charges_data = await charges_image.read()
        charges_mime = charges_image.content_type or "image/jpeg"
        charges_text = _gemini_extract_text_from_image(charges_data, charges_mime)

        full_items_text = "\n\n".join(items_texts)
        full_text = f"ITEMS:\n{full_items_text}\n\nCHARGES:\n{charges_text}"

        response_body = {
            "success": True,
            "full_text": full_text,
            "items_text": full_items_text,
            "charges_text": charges_text,
        }

        if run_llm and full_items_text.strip():
            items_response = _gemini_generate_content(
                [{"text": f"{PROMPT_ITEMS}\n{full_items_text}"}],
                temperature=llm_temperature,
                max_output_tokens=llm_max_tokens
            )
            response_body["items_analysis"] = {
                "response": items_response
            }

        if run_llm and charges_text.strip():
            charges_response = _gemini_generate_content(
                [{"text": f"{PROMPT_CHARGES}\n{charges_text}"}],
                temperature=llm_temperature,
                max_output_tokens=llm_max_tokens
            )
            response_body["charges_analysis"] = {
                "response": charges_response
            }

        return JSONResponse(response_body)

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Gemini OCR processing failed: {str(e)}"
        )
