import os
import uuid
import zipfile
import json
import tempfile
from typing import List, Dict, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import requests
from openai import OpenAI

# Import auth routes and database
from auth_routes import router as auth_router
from groups_routes import router as groups_router
from database import connect_to_mongo, close_mongo_connection

load_dotenv()

app = FastAPI(title="Kvitta API")

# Allow all CORS for now
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Startup event: Connect to MongoDB
@app.on_event("startup")
async def startup_db_client():
    await connect_to_mongo()

# Shutdown event: Close MongoDB connection
@app.on_event("shutdown")
async def shutdown_db_client():
    await close_mongo_connection()

# Include authentication routes
app.include_router(auth_router)
# Include groups routes
app.include_router(groups_router)

# NVAI endpoint for the ocdrnet NIM
NVAI_URL = "https://ai.api.nvidia.com/v1/cv/nvidia/ocdrnet"
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY")

PROMPT_ITEMS = """
You are an item-reconstruction engine for Instacart receipts.

You are given RAW OCR TEXT extracted from item images.
The OCR text is noisy, fragmented, duplicated, and unordered.

You MUST reconstruct purchasable items.

RULES:
- You MAY group OCR fragments into items.
- You MAY infer item boundaries using quantity and price proximity.
- You MUST NOT invent numeric values.
- You MUST NOT calculate totals or prices.
- If a numeric value is not clearly present, set it to null.

NOTE: OCR may misread the '$' symbol as '8'.
When a numeric value appears in a price context without a '$', treat it as a dollar amount.

PATTERNS:
- Quantity: "N ct", "Nct", "X kg", "X lb"
- Price: "$X each", price near item name
- Ignore UI noise like "|", stray numbers, icons

OUTPUT JSON ONLY:
{
  "line_items": [
    {
      "name_raw": string,
      "quantity": number,
      "unit_price": number | null,
      "line_subtotal": number | null
    }
  ]
}
"""

PROMPT_CHARGES = """
You are a receipt totals extractor.

You are given Charges / Totals image.

RULES:
- DO NOT calculate anything.
- DO NOT infer missing values.
- ONLY copy numbers explicitly labeled.

NOTE: You may misread the '$' symbol as '8'.
When a numeric value appears in a price context without a '$', treat it as a dollar amount.

Extract:
- Item Subtotal
- Service Fee (taxable: true)
- Service Fee Tax
- Checkout Bag Fee (taxable: true)
- Checkout Bag Fee Tax
- Total

DISCOUNT RULE (IMPORTANT):
- The receipt may contain multiple discount-related lines
  (e.g., "Retailer Coupon Discount", "You saved $X.XX").
- OUTPUT EXACTLY ONE discount entry.
- If a TOTAL discount amount is explicitly stated (e.g., "You saved $2.00"),
  use that value.
- Otherwise, use the single most authoritative discount value shown.
- DO NOT sum multiple discounts unless the receipt explicitly provides a total.
- If no discount is clearly stated, return an empty discounts array.

IMPORTANT: Mark Service Fee and Checkout Bag Fee as taxable.

OUTPUT JSON ONLY:
{
  "subtotal_items": number | null,
  "fees": [{ "type": string, "amount": number, "taxable": boolean }],
  "discounts": [
    { "description": string, "amount": number }
  ],
  "total_tax_reported": number | null,
  "grand_total": number | null
}

FEE TAXABILITY RULES:
- Service Fee: taxable = true
- Checkout Bag Fee: taxable = true
- Delivery Fee: taxable = true
- Other fees: taxable = false (unless explicitly taxed on receipt)
"""

if not NVIDIA_API_KEY:
    print("WARNING: NVIDIA_API_KEY environment variable not set - Nvidia OCR will not work")

HEADER_AUTH = f"Bearer {NVIDIA_API_KEY}"

# Initialize OpenAI client for Nvidia LLM reasoning model
openai_client = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=NVIDIA_API_KEY
)


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
    max_y_gap_factor: float = 0.7
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
        b = box_stats(item["polygon"])
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


async def _process_ocr_response(response: requests.Response) -> Dict:
    """
    Process OCR response from Nvidia API.
    Handles both JSON and zip file responses.

    :param response: Response object from Nvidia OCR API
    :return: Metadata dictionary containing detections
    """
    content_type = response.headers.get("content-type", "")

    if "application/json" in content_type:
        return response.json()

    with tempfile.TemporaryDirectory() as temp_dir:
        zip_path = os.path.join(temp_dir, "output.zip")

        with open(zip_path, "wb") as out:
            out.write(response.content)

        with zipfile.ZipFile(zip_path, "r") as z:
            z.extractall(temp_dir)

        files = os.listdir(temp_dir)
        metadata_files = [f for f in files if f.endswith(".response") or f.endswith(".json")]

        if not metadata_files:
            raise HTTPException(
                status_code=500,
                detail=f"No metadata file found in OCR response. Files in zip: {files}"
            )

        metadata_path = os.path.join(temp_dir, metadata_files[0])
        with open(metadata_path, "r") as f:
            return json.load(f)


async def reason_with_llm(
    prompt: str,
    temperature: float = 0.6,
    max_tokens: int = 4096
) -> Dict:
    """
    Use Nvidia Nemotron Nano 9B v2 to analyze and reason about text.

    :param prompt: The prompt to send to the model
    :param temperature: Temperature for generation (0.0-2.0), default 0.6
    :param max_tokens: Maximum tokens to generate, default 4096
    :return: Dictionary with reasoning content and final response
    """
    if not NVIDIA_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="NVIDIA_API_KEY not configured on server"
        )

    try:
        reasoning_content = ""
        final_response = ""

        completion = openai_client.chat.completions.create(
            model="nvidia/nvidia-nemotron-nano-9b-v2",
            messages=[
                {"role": "system", "content": "/think"},
                {"role": "user", "content": prompt}
            ],
            temperature=temperature,
            top_p=0.95,
            max_tokens=max_tokens,
            frequency_penalty=0,
            presence_penalty=0,
            stream=True,
            extra_body={
                "min_thinking_tokens": 500,
                "max_thinking_tokens": 2000
            }
        )

        for chunk in completion:
            if not getattr(chunk, "choices", None):
                continue

            reasoning = getattr(chunk.choices[0].delta, "reasoning_content", None)
            if reasoning:
                reasoning_content += reasoning

            if chunk.choices and chunk.choices[0].delta.content is not None:
                final_response += chunk.choices[0].delta.content

        return {
            "success": True,
            "reasoning": reasoning_content,
            "response": final_response
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"LLM reasoning failed: {str(e)}"
        )


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


@app.post("/nvidia-ocr/reason")
async def llm_reasoning(
    prompt: str,
    temperature: float = 0.6,
    max_tokens: int = 4096
):
    """
    Send a prompt to Nvidia Nemotron Nano 9B v2 with chain-of-thought.

    :param prompt: The prompt/question to analyze
    :param temperature: Model temperature (0.0-2.0), default 0.6
    :param max_tokens: Maximum tokens to generate, default 4096
    :return: JSON with reasoning process and final response
    """
    result = await reason_with_llm(
        prompt,
        temperature=temperature,
        max_tokens=max_tokens
    )
    return JSONResponse(result)


@app.get("/")
async def root():
    return {"message": "Kvitta Nvidia OCR API is running"}
