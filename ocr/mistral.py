import base64
import os
from mistralai import Mistral, JSONSchema, ResponseFormat

api_key = os.environ["MISTRAL_API_KEY"]

client = Mistral(api_key=api_key)

def encode_file(file_path):
    with open(file_path, "rb") as pdf_file:
        return base64.b64encode(pdf_file.read()).decode('utf-8')

file_path = "path/to/2a.jpeg"
base64_file = encode_file(file_path)

ocr_response = client.ocr.process(
    document={
      "type": "image_url",
      "image_url": f"data:image/jpeg;base64,{base64_file}"
    },
    model="mistral-ocr-latest",
	include_image_base64=False,
	document_annotation_format=ResponseFormat(
		type="json_schema",
		json_schema=JSONSchema(
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
								"item_price": {
									"title": "Item_Price",
									"type": "number"
								},
								"price_per_unit": {
									"title": "Price_Per_Unit",
									"type": "string"
								}
							},
							"required": [
								"item_description",
								"item_price",
								"price_per_unit"
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
								"price_per_unit": {
									"title": "Price_Per_Unit",
									"type": "string"
								},
								"unit_weight": {
									"title": "Unit_Weight",
									"type": "string"
								},
								"weight_change": {
									"title": "Weight_Change",
									"type": "string"
								}
							},
							"required": [
								"item_description",
								"item_quantity",
								"item_price",
								"price_per_unit"
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
								"price_per_unit": {
									"title": "Price_Per_Unit",
									"type": "string"
								},
								"refund_reason": {
									"title": "Refund_Reason",
									"type": "string"
								}
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
		),
	),
	document_annotation_prompt="Ignore the item images. \n\nRULES:\n- You MUST NOT invent numeric values.\n- You MUST NOT calculate totals or prices.\n- If a numeric value is not clearly present, set it to null.\n\nPATTERNS:\n- Quantity: \"N ct\", \"Nct\", \"X kg\", \"X lb\"\n- Price: \"$X each\", price near item name\n- Ignore UI noise like \"|\", stray numbers, icons\n- Discounted Items have strikethrough characters, ignore them\n- Some items have long item names wrapping to next lines, make sure you capture that correctly. \n- For Replacement section - ignore the field \"Replacement for \", it's not useful"
)