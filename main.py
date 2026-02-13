import os
from typing import List, Dict, Optional
from dotenv import load_dotenv
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from openai import OpenAI
import pytesseract
import cv2
import numpy as np
import base64
from ocr.llama import call_nvidia_llama_vision

# Import auth routes and database
from auth_routes import router as auth_router
from groups_routes import router as groups_router
from folders_routes import router as folders_router
from receipts_routes import router as receipts_router
from database import connect_to_mongo, close_mongo_connection
from ocr.mistral_routes import router as mistral_router

app = FastAPI(title="Kvitta API")

# Load environment variables from .env file
load_dotenv()

NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY")
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

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
# Include folders routes
app.include_router(folders_router)
# Include receipts routes
app.include_router(receipts_router)
# Include Mistral OCR routes
app.include_router(mistral_router)


# NVAI endpoint for the ocdrnet NIM
NVAI_URL = "https://ai.api.nvidia.com/v1/cv/nvidia/ocdrnet"

HEADER_AUTH = f"Bearer {NVIDIA_API_KEY}"

# Initialize OpenAI client for Nvidia LLM reasoning model
openai_client = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=NVIDIA_API_KEY
)

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

IMPORTANT: Use the field name "line_subtotal" (NOT "total_price") for the item total.
The line_subtotal is the total price for that line item (quantity × unit_price).

EXAMPLE OUTPUT:
{
  "line_items": [
    {
      "name_raw": "Organic Bananas",
      "quantity": 2,
      "unit_price": 0.50,
      "line_subtotal": 1.00,
      "taxable":true
    },
    {
      "name_raw": "Whole Milk",
      "quantity": 1,
      "unit_price": 4.99,
      "line_subtotal": 4.99,
      "taxable":false
    }
  ]
}

OUTPUT JSON ONLY:
{
  "line_items": [
    {
      "name_raw": string,
      "quantity": number,
      "unit_price": number | null,
      "line_subtotal": number | null,
      "taxable": boolean
    }
  ]
}
"""

from ocr.instructions import ONTARIO_HST_RULES

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



def detect_rounded_boxes(image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # Adaptive threshold works better for subtle UI differences
    thresh = cv2.adaptiveThreshold(
        gray, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        51, 5
    )

    # Merge broken borders
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
    closed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)

    contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    boxes = []

    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < 30000:   # adjust if needed
            continue

        x, y, w, h = cv2.boundingRect(cnt)

        aspect_ratio = w / float(h)

        # Cards are wide rectangles
        if 2.0 < aspect_ratio < 10:
            boxes.append((x, y, w, h))

    # Sort top to bottom
    boxes = sorted(boxes, key=lambda b: b[1])

    return boxes


def detect_cards_projection(image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # Strong binarization
    _, thresh = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY_INV)

    # Sum pixels per row
    row_sums = np.sum(thresh, axis=1)

    height = image.shape[0]

    # Normalize
    row_sums = row_sums / np.max(row_sums)

    # Detect blank rows (low content)
    blank_rows = row_sums < 0.02

    segments = []
    in_segment = False
    start = 0

    for i in range(height):
        if not blank_rows[i] and not in_segment:
            start = i
            in_segment = True
        elif blank_rows[i] and in_segment:
            end = i
            if end - start > 80:  # minimum card height
                segments.append((start, end))
            in_segment = False

    boxes = []

    for (y1, y2) in segments:
        # Crop full width (or slightly inset)
        boxes.append((0, y1, image.shape[1], y2 - y1))

    return boxes

def split_card(card_img):
    TARGET_WIDTH = 1000

    h, w = card_img.shape[:2]

    # 1️⃣ Resize to fixed width
    scale = TARGET_WIDTH / w
    new_h = int(h * scale)
    card_resized = cv2.resize(card_img, (TARGET_WIDTH, new_h))

    h2, w2 = card_resized.shape[:2]

    # 2️⃣ Absolute pixel cuts (tuned once)
    LEFT_CUT = 180           # left product image width
    PRICE_COLUMN_WIDTH = 160 # right price column width
    TOP_PRICE_HEIGHT = 80   # absolute top area for price

    # Remove left image
    content = card_resized[:, LEFT_CUT:]

    # Extract price column
    price_column = content[:, -PRICE_COLUMN_WIDTH:]

    # Absolute top crop
    price_crop = price_column[:TOP_PRICE_HEIGHT, :]

    # Middle full (exclude price column)
    middle_crop_full = content[:, :-PRICE_COLUMN_WIDTH]

    # Optional: top-only middle crop
    middle_crop_top = middle_crop_full[:TOP_PRICE_HEIGHT, :]

    return middle_crop_full, middle_crop_top, price_crop


# ---------- ENCODER ----------
def encode_image(img):
    _, buffer = cv2.imencode(".png", img)
    return base64.b64encode(buffer).decode("utf-8")


import json as json_lib

def extract_json_from_response(response_str: str) -> Optional[Dict]:
    """
    Extract JSON from LLM response which may contain markdown formatting.
    
    Tries to:
    1. Parse as-is (if response is pure JSON)
    2. Extract from ```json ... ``` blocks
    3. Find first { and last } and parse that
    
    Returns parsed dict or None if no valid JSON found.
    """
    try:
        # Try direct JSON parse
        return json_lib.loads(response_str)
    except json_lib.JSONDecodeError:
        pass
    
    # Try to find ```json...``` block
    import re
    match = re.search(r'```(?:json)?\s*\n(.*?)\n```', response_str, re.DOTALL)
    if match:
        try:
            return json_lib.loads(match.group(1))
        except json_lib.JSONDecodeError:
            pass
    
    # Try to find { ... } content
    start = response_str.find('{')
    if start != -1:
        end = response_str.rfind('}')
        if end != -1 and end > start:
            try:
                return json_lib.loads(response_str[start:end+1])
            except json_lib.JSONDecodeError:
                pass
    
    return None


# ---------- API ----------
@app.post("/upload")
async def upload_image(
    receipt_items: List[UploadFile] = File(...),
    charges_image: Optional[UploadFile] = File(None)
):
    """
    Process multiple receipt item images and optional charges image.
    
    Args:
        receipt_items: Multiple receipt item images to process and merge
        charges_image: Optional charges/totals image
    
    Returns:
        Merged results from all receipt item images
    """
    if not receipt_items:
        return JSONResponse(status_code=400, content={"error": "Must provide at least one receipt item image"})

    all_results = []

    # Process each receipt item image
    for file in receipt_items:
        contents = await file.read()
        np_arr = np.frombuffer(contents, np.uint8)
        image = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

        if image is None:
            continue  # Skip invalid images

        boxes = detect_rounded_boxes(image)

        for (x, y, w, h) in boxes:
            card = image[y:y+h, x:x+w]

            middle_full, middle, price = split_card(card)

            middle_text = run_ocr_on_crop(middle)
            middle_full_text = run_ocr_on_crop(middle_full)
            price_text = run_ocr_on_crop(price)

            all_results.append({
                # "middle": encode_image(middle),
                # "price": encode_image(price),
                "middle_text": middle_text,
                "middle_text_full": middle_full_text,
                "price_text": price_text
            })

    results_for_llm = [
        {
            "middle_text": item.get("middle_text"),
            "price_text": item.get("price_text")
        }
        for item in all_results
    ]
    response:str = str(call_nvidia_llama_vision(None, PROMPT_ITEMS + ONTARIO_HST_RULES + str(results_for_llm)))
    response_json = extract_json_from_response(response)

    charges_images_base64 = None
    if charges_image is not None:
        charges_bytes = await charges_image.read()
        charges_mime_type = charges_image.content_type or "image/jpeg"
        charges_base64 = base64.b64encode(charges_bytes).decode("utf-8")
        charges_images_base64 = [(charges_mime_type, charges_base64)]

    response2:str = str(call_nvidia_llama_vision(charges_images_base64, PROMPT_CHARGES + str(results_for_llm)))
    response2_json = extract_json_from_response(response2)

    return {
        "total_items_processed": len(all_results),
        # "cards": all_results,
        "items_analysis": response_json,
        "charges_analysis": response2_json
    }


from paddleocr import PaddleOCR
import cv2
import numpy as np

# Initialize once globally (important)
ocr_engine = PaddleOCR(use_angle_cls=True, lang='en')

def preprocess_for_ocr(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Increase contrast
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    gray = clahe.apply(gray)

    # Mild sharpening
    kernel = np.array([[0,-1,0], [-1,5,-1], [0,-1,0]])
    sharp = cv2.filter2D(gray, -1, kernel)

    return sharp

def run_ocr_on_crop(img):
    text = pytesseract.image_to_string(img, config="--psm 6")
    return text.strip()