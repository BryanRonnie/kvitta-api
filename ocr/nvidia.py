from http.client import HTTPException
from typing import Dict, List

from fastapi.responses import JSONResponse
import requests


def classify_items_batch(line_items: List[Dict], use_llm: str = "mistral") -> List[Dict]:
    """
    Classify all line items in a batch using LLM.
    
    Args:
        line_items: List of line item dicts with 'name_raw' field
        use_llm: Which LLM to use (default: "mistral")
    
    Returns:
        Updated line_items with 'taxable' field added (true/false)
    """
    if not line_items:
        return line_items
    
    # Batch classify using LLM for efficiency
    items_text = "\n".join([f"- {item.get('name_raw', item.get('name', 'unknown'))}" for item in line_items])
    
    prompt = f"""
{ONTARIO_HST_RULES}

Classify each item as taxable (true) or non-taxable (false) based on Ontario HST rules.

ITEMS:
{items_text}

Return ONLY a JSON array with true/false values in the same order:
["true", "false", "false", ...]

No explanation, just the JSON array.
"""
    
    response_text = ""
    
    try:
        # Route to appropriate LLM
        if use_llm == "llama":
            response_text = call_llama_for_taxability(prompt)
        elif use_llm == "nemotron":
            response_text = call_nemotron_for_taxability(prompt)
        # elif use_llm == "mistral":
        #     response_text = call_mistral_for_taxability(prompt)
        # elif use_llm == "gemma":
        #     response_text = call_gemma_for_taxability(prompt)
        # else:
        #     response_text = call_gemini_for_taxability(prompt)
        
        # Parse response
        import json
        import re
        
        # Extract JSON array from response
        match = re.search(r'\[(.*?)\]', response_text, re.DOTALL)
        if match:
            results = json.loads(match.group(0))
            
            # Add taxable field to each item
            for i, item in enumerate(line_items):
                if i < len(results):
                    taxable_str = str(results[i]).lower()
                    item['taxable'] = taxable_str == 'true'
                else:
                    item['taxable'] = False  # Default to non-taxable
        else:
            # Fallback: classify individually
            print("⚠️ Batch classification failed, using fallback")
            for item in line_items:
                item['taxable'] = classify_item_simple_rules(item.get('name_raw', item.get('name', '')))
                
    except Exception as e:
        print(f"❌ LLM classification failed: {e}, using simple rules")
        for item in line_items:
            item['taxable'] = classify_item_simple_rules(item.get('name_raw', item.get('name', '')))
    
    return line_items

def classify_item_simple_rules(item_name: str) -> bool:
    """
    Simple rule-based classification without LLM.
    
    Returns:
        True if taxable, False if non-taxable
    """
    item_lower = item_name.lower()
    
    # Non-taxable keywords (basic groceries)
    non_taxable_keywords = [
        'banana', 'apple', 'orange', 'grape', 'berry', 'fruit',
        'milk', 'egg', 'butter', 'cheese', 'yogurt', 'cream',
        'bread', 'bun', 'bagel', 'pita',
        'rice', 'flour', 'pasta', 'grain', 'oat', 'cereal',
        'chicken', 'beef', 'pork', 'fish', 'meat', 'turkey',
        'carrot', 'lettuce', 'tomato', 'potato', 'onion', 'vegetable',
        'coffee', 'tea',
        'organic', 'fresh', 'selection'  # Store brand indicators
    ]
    
    # Taxable keywords
    taxable_keywords = [
        'chip', 'candy', 'chocolate', 'cookie', 'pastry', 'cake',
        'soda', 'pop', 'juice drink', 'energy drink',
        'alcohol', 'beer', 'wine', 'spirit',
        'prepared', 'ready to eat', 'sandwich', 'salad',
        'cleaning', 'soap', 'detergent', 'shampoo',
        'paper towel', 'tissue', 'toilet paper'
    ]
    
    # Check taxable first (more specific)
    for keyword in taxable_keywords:
        if keyword in item_lower:
            return True
    
    # Check non-taxable
    for keyword in non_taxable_keywords:
        if keyword in item_lower:
            return False
    
    # Default to non-taxable for grocery items (Ontario default)
    return False

def _upload_asset(input_data: bytes, description: str) -> uuid.UUID:
    """
    Uploads an asset to the NVCF API.

    :param input_data: The binary asset to upload
    :param description: A description of the asset
    :return: Asset UUID
    """
    assets_url = "https://api.nvcf.nvidia.com/v2/nvcf/assets"

    headers = {
        "Authorization": HEADER_AUTH,
        "Content-Type": "application/json",
        "accept": "application/json",
    }

    s3_headers = {
        "x-amz-meta-nvcf-asset-description": description,
        "content-type": "image/jpeg",
    }

    payload = {"contentType": "image/jpeg", "description": description}

    response = requests.post(assets_url, headers=headers, json=payload, timeout=30)
    response.raise_for_status()

    asset_url = response.json()["uploadUrl"]
    asset_id = response.json()["assetId"]

    response = requests.put(
        asset_url,
        data=input_data,
        headers=s3_headers,
        timeout=300,
    )
    response.raise_for_status()

    return uuid.UUID(asset_id)


def box_stats(polygon: Dict) -> Dict:
    """Calculate bounding box statistics from polygon coordinates."""
    xs = [polygon["x1"], polygon["x2"], polygon["x3"], polygon["x4"]]
    ys = [polygon["y1"], polygon["y2"], polygon["y3"], polygon["y4"]]
    return {
        "xmin": min(xs),
        "xmax": max(xs),
        "ymin": min(ys),
        "ymax": max(ys),
        "xc": sum(xs) / 4.0,
        "yc": sum(ys) / 4.0,
        "h": max(ys) - min(ys),
    }


def stitch_lines(
    metadata: List[Dict],
    y_overlap_ratio: float = 0.6,
    max_y_gap_factor: float = 0.9
) -> List[str]:
    """
    Stitches detected text boxes into logical lines.

    :param metadata: List of detected text boxes with labels and polygons
    :param y_overlap_ratio: Minimum vertical overlap ratio to consider same line
    :param max_y_gap_factor: Maximum vertical gap factor relative to box height
    :return: List of stitched text lines
    """
    words = []
    for item in metadata:
        polygon = item["polygon"]
        # Skip items where x1 or x4 is below 185 (likely UI elements on the left)
        if polygon.get("x1", float('inf')) < 180 or polygon.get("x4", float('inf')) < 180:
            continue
        
        b = box_stats(polygon)
        words.append({
            "text": item["label"],
            **b
        })

    # Sort top-to-bottom
    words.sort(key=lambda w: w["yc"])

    lines = []

    for w in words:
        placed = False
        for line in lines:
            # reference line vertical center and height
            ref_y = line["yc"]
            ref_h = line["h"]

            y_dist = abs(w["yc"] - ref_y)
            allowed = max(w["h"], ref_h) * max_y_gap_factor

            # vertical overlap test
            overlap = min(w["ymax"], line["ymax"]) - max(w["ymin"], line["ymin"])

            if overlap > min(w["h"], ref_h) * y_overlap_ratio or y_dist <= allowed:
                line["words"].append(w)
                # update line envelope
                line["ymin"] = min(line["ymin"], w["ymin"])
                line["ymax"] = max(line["ymax"], w["ymax"])
                line["yc"] = (line["ymin"] + line["ymax"]) / 2
                line["h"] = line["ymax"] - line["ymin"]
                placed = True
                break

        if not placed:
            lines.append({
                "words": [w],
                "ymin": w["ymin"],
                "ymax": w["ymax"],
                "yc": w["yc"],
                "h": w["h"],
            })

    # Sort words left-to-right inside each line
    stitched = []
    for line in lines:
        line["words"].sort(key=lambda w: w["xmin"])
        stitched.append(" ".join(w["text"] for w in line["words"]))

    return stitched

@app.post("/nvidia-ocr/extract-text")
async def extract_text_nvidia(
    receipt_pdf: Optional[UploadFile] = File(None),
    items_images: Optional[List[UploadFile]] = File(None),
    charges_image: Optional[UploadFile] = File(None),
    run_llm: bool = True,
    llm_temperature: float = 0.6,
    llm_max_tokens: int = 4096
):
    """
    Extract text from receipt using Nvidia OCDRNet model.

    Supports two modes:
    1. PDF mode: receipt_pdf file
    2. Image mode: items_images (multiple) + charges_image (single)

    :param receipt_pdf: PDF file of receipt (optional)
    :param items_images: Multiple images showing items (optional)
    :param charges_image: Single image showing charges/totals (optional)
    :param run_llm: Whether to run LLM analysis on extracted text
    :return: JSON with stitched text lines and optional LLM analysis
    """
    if not NVIDIA_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="NVIDIA_API_KEY not configured on server"
        )

    if receipt_pdf:
        upload_mode = "pdf"
    elif items_images and charges_image:
        upload_mode = "images"
    else:
        raise HTTPException(
            status_code=400,
            detail="Must provide either receipt_pdf OR (items_images + charges_image)"
        )

    try:
        if upload_mode == "pdf":
            # PDF processing not yet implemented
            raise HTTPException(
                status_code=501,
                detail="PDF processing not yet implemented. Use image mode for now."
            )

        # images mode
        items_texts = []
        for item_image in items_images:
            image_data = await item_image.read()

            asset_id = _upload_asset(image_data, "Items Image")

            inputs = {"image": f"{asset_id}", "render_label": False}
            asset_list = f"{asset_id}"

            headers = {
                "Content-Type": "application/json",
                "NVCF-INPUT-ASSET-REFERENCES": asset_list,
                "NVCF-FUNCTION-ASSET-IDS": asset_list,
                "Authorization": HEADER_AUTH,
            }

            response = requests.post(NVAI_URL, headers=headers, json=inputs, timeout=60)
            response.raise_for_status()

            metadata = await _process_ocr_response(response)
            detections = metadata.get("metadata", metadata.get("detections", metadata.get("data", []))) if isinstance(metadata, dict) else metadata
            stitched_lines = stitch_lines(detections)
            items_texts.append("\n".join(stitched_lines))

        charges_data = await charges_image.read()
        asset_id = _upload_asset(charges_data, "Charges Image")

        inputs = {"image": f"{asset_id}", "render_label": False}
        asset_list = f"{asset_id}"

        headers = {
            "Content-Type": "application/json",
            "NVCF-INPUT-ASSET-REFERENCES": asset_list,
            "NVCF-FUNCTION-ASSET-IDS": asset_list,
            "Authorization": HEADER_AUTH,
        }

        response = requests.post(NVAI_URL, headers=headers, json=inputs, timeout=60)
        response.raise_for_status()

        metadata = await _process_ocr_response(response)
        detections = metadata.get("metadata", metadata.get("detections", metadata.get("data", []))) if isinstance(metadata, dict) else metadata
        stitched_lines = stitch_lines(detections)
        charges_text = "\n".join(stitched_lines)

        full_items_text = "\n\n".join(items_texts)
        full_text = f"ITEMS:\n{full_items_text}\n\nCHARGES:\n{charges_text}"

        llm_result = None
        if run_llm and full_items_text.strip():
            llm_result = await reason_with_llm(
                f"{PROMPT_ITEMS}\n{full_items_text}",
                temperature=llm_temperature,
                max_tokens=llm_max_tokens
            )

        charges_llm_result = None
        if run_llm and charges_text.strip():
            charges_llm_result = await reason_with_llm(
                f"{PROMPT_CHARGES}\n{charges_text}",
                temperature=llm_temperature,
                max_tokens=llm_max_tokens
            )

        response_body = {
            "success": True,
            "full_text": full_text,
            "items_text": full_items_text,
            "charges_text": charges_text,
        }

        if llm_result is not None:
            response_body["items_analysis"] = {
                "response": llm_result["response"]
            }

        if charges_llm_result is not None:
            response_body["charges_analysis"] = {
                "response": charges_llm_result["response"]
            }

        return JSONResponse(response_body)

    except requests.exceptions.RequestException as e:
        raise HTTPException(
            status_code=500,
            detail=f"Nvidia API request failed: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"OCR processing failed: {str(e)}"
        )
