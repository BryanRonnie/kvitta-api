"""
FastAPI routes for Mistral OCR processing.
"""

import base64
import json
import os
from typing import Dict, List, Optional
from fastapi import APIRouter, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
from mistralai import Mistral, JSONSchema, ResponseFormat

router = APIRouter(prefix="/mistral-ocr", tags=["mistral-ocr"])

MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")

if not MISTRAL_API_KEY:
    print("WARNING: MISTRAL_API_KEY environment variable not set - Mistral OCR will not work")


def _build_ocr_schema():
    """Build the JSON schema for Mistral OCR response."""
    return JSONSchema(
        name="response_schema",
        schema_definition={
            "title": "ShoppingList",
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "replacements": {
                    "title": "Replacements",
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "item_description": {
                                "title": "Item_Description",
                                "type": "string"
                            },
                            "item_quantity": {
                                "title": "Item_Quantity",
                                "type": "number"
                            },
                            "item_price": {
                                "title": "Item_Price",
                                "type": "number"
                            },
                        },
                        "required": [
                            "item_description",
                            "item_price",
                            "item_quantity"
                        ]
                    }
                },
                "found": {
                    "title": "Found",
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "item_description": {
                                "title": "Item_Description",
                                "type": "string"
                            },
                            "item_quantity": {
                                "title": "Item_Quantity",
                                "type": "number"
                            },
                            "item_price": {
                                "title": "Item_Price",
                                "type": "number"
                            },
                            "unit_weight": {
                                "title": "Unit_Weight",
                                "type": "string"
                            }
                        },
                        "required": [
                            "item_description",
                            "item_quantity",
                            "item_price",
                        ]
                    }
                },
                "refunded": {
                    "title": "Refunded",
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "item_description": {
                                "title": "Item_Description",
                                "type": "string"
                            },
                            "item_quantity": {
                                "title": "Item_Quantity",
                                "type": "number"
                            },
                            "item_price": {
                                "title": "Item_Price",
                                "type": "number"
                            },
                        },
                        "required": [
                            "item_description",
                            "item_quantity",
                            "item_price"
                        ]
                    }
                }
            }
        },
    )


async def process_image_with_mistral(image_data: bytes, mime_type: str = "image/jpeg") -> tuple[Dict, Dict]:
    """
    Process a single image with Mistral OCR.
    
    Args:
        image_data: Raw image bytes
        mime_type: MIME type of the image
    
    Returns:
        Tuple of (parsed_data dict, status dict) where status contains:
        - status: 'success', 'failed', 'empty_response', 'timeout', 'parse_error'
        - message: Human readable status message
        - error: Error details if any
    """
    if not MISTRAL_API_KEY:
        return (
            {"replacements": [], "found": [], "refunded": []},
            {"status": "failed", "message": "MISTRAL_API_KEY not configured", "error": "No API key"}
        )
    
    try:
        client = Mistral(api_key=MISTRAL_API_KEY)
        base64_image = base64.b64encode(image_data).decode('utf-8')
        
        ocr_response = client.ocr.process(
            document={
                "type": "image_url",
                "image_url": f"data:{mime_type};base64,{base64_image}"
            },
            model="mistral-ocr-latest",
            include_image_base64=False,
            document_annotation_format=ResponseFormat(
                type="json_schema",
                json_schema=_build_ocr_schema(),
            ),
            document_annotation_prompt=(
                "Ignore the item images. "
                "Don't worry about the per qty/weight prices. The final price of the item(first line, immediate right side of the item name) is enough.  \n\n"
                "RULES:\n"
                "- You MUST NOT invent numeric values.\n"
                "- You MUST NOT calculate totals or prices.\n"
                "- If a numeric value is not clearly present, set it to null.\n\n"
                "PATTERNS:\n"
                "- Quantity: \"N ct\", \"Nct\", \"X kg\", \"X lb\"\n"
                "- Price: \"$X each\", price near item name\n"
                "- Ignore UI noise like \"|\", stray numbers, icons\n"
                "- Discounted Items have strikethrough characters, ignore them\n"
                "- Some items have long item names wrapping to next lines, make sure you capture that correctly.\n"
                "- For Replacement section - ignore the field \"Replacement for \", it's not useful"
            )
        )
        
        # Validate response has required attribute
        if not hasattr(ocr_response, 'document_annotation'):
            return (
                {"replacements": [], "found": [], "refunded": []},
                {"status": "failed", "message": "No document_annotation in response", "error": "Missing attribute"}
            )
        
        if not isinstance(ocr_response.document_annotation, str):
            return (
                {"replacements": [], "found": [], "refunded": []},
                {"status": "failed", "message": f"document_annotation is not string: {type(ocr_response.document_annotation)}", "error": "Wrong type"}
            )
        
        if len(ocr_response.document_annotation) == 0:
            return (
                {"replacements": [], "found": [], "refunded": []},
                {"status": "empty_response", "message": "document_annotation is empty", "error": "Empty content"}
            )
        
        # Parse JSON
        try:
            parsed_data = json.loads(ocr_response.document_annotation)
        except json.JSONDecodeError as e:
            return (
                {"replacements": [], "found": [], "refunded": []},
                {"status": "parse_error", "message": f"Failed to parse JSON: {str(e)}", "error": str(e)}
            )
        
        # Check if this is actual data or just the schema
        has_replacements = 'replacements' in parsed_data and isinstance(parsed_data.get('replacements'), list) and len(parsed_data['replacements']) > 0
        has_found = 'found' in parsed_data and isinstance(parsed_data.get('found'), list) and len(parsed_data['found']) > 0
        has_refunded = 'refunded' in parsed_data and isinstance(parsed_data.get('refunded'), list) and len(parsed_data['refunded']) > 0
        
        if has_replacements or has_found or has_refunded:
            # This is actual data
            result = {
                'replacements': parsed_data.get('replacements', []),
                'found': parsed_data.get('found', []),
                'refunded': parsed_data.get('refunded', [])
            }
            items_count = len(result['replacements']) + len(result['found']) + len(result['refunded'])
            return (result, {"status": "success", "message": f"Extracted {items_count} items", "items_found": items_count})
        else:
            # This is just the schema, no actual data extracted
            return (
                {"replacements": [], "found": [], "refunded": []},
                {"status": "empty_response", "message": "Schema returned but no items extracted", "error": "Mistral found no items"}
            )
    
    except TimeoutError:
        return (
            {"replacements": [], "found": [], "refunded": []},
            {"status": "timeout", "message": "Mistral API call timed out", "error": "Request timeout"}
        )
    except Exception as e:
        return (
            {"replacements": [], "found": [], "refunded": []},
            {"status": "failed", "message": f"Mistral OCR processing failed: {str(e)}", "error": str(e)}
        )


@router.post("/extract-items")
async def extract_items_mistral(
    images: List[UploadFile] = File(..., description="One or more receipt images to process")
):
    """
    Extract shopping list items from multiple images using Mistral OCR.
    
    Merges items from replacements, found, and refunded categories across all images.
    
    Returns:
        {
            "success": true,
            "items": [...merged items from all categories...],
            "replacements": [...items marked as replacements...],
            "found": [...items marked as found...],
            "refunded": [...items marked as refunded...],
            "total_images_processed": N,
            "item_count": N,
            "processing_status": [
                {"image_index": 0, "status": "success", "message": "...", "items_found": N},
                ...
            ]
        }
    """
    if not MISTRAL_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="MISTRAL_API_KEY not configured on server"
        )
    
    if not images:
        raise HTTPException(
            status_code=400,
            detail="Must provide at least one image"
        )
    
    try:
        all_replacements = []
        all_found = []
        all_refunded = []
        processing_status = []
        
        # Process each image
        for idx, image in enumerate(images):
            image_data = await image.read()
            mime_type = image.content_type or "image/jpeg"
            
            # Process image and get both data and status
            response_data, status = await process_image_with_mistral(image_data, mime_type)
            
            # Record status for this image
            status_entry = {
                "image_index": idx,
                "filename": image.filename,
                **status
            }
            processing_status.append(status_entry)
            
            # Merge items regardless of success (empty dict has empty arrays)
            if response_data.get("replacements"):
                all_replacements.extend(response_data["replacements"])
            if response_data.get("found"):
                all_found.extend(response_data["found"])
            if response_data.get("refunded"):
                all_refunded.extend(response_data["refunded"])
        
        # Combine all items with category labels
        all_items = []
        for item in all_replacements:
            all_items.append({**item, "category": "replacement"})
        for item in all_found:
            all_items.append({**item, "category": "found"})
        for item in all_refunded:
            all_items.append({**item, "category": "refunded"})
        
        # Determine overall success (at least one successful extraction)
        has_success = any(s.get("status") == "success" for s in processing_status)
        
        return JSONResponse({
            "success": has_success,
            "items": all_items,
            "replacements": all_replacements,
            "found": all_found,
            "refunded": all_refunded,
            "total_images_processed": len(images),
            "item_count": len(all_items),
            "processing_status": processing_status
        })
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Mistral OCR extraction failed: {str(e)}"
        )
