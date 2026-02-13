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
      "line_subtotal": 1.00
    },
    {
      "name_raw": "Whole Milk",
      "quantity": 1,
      "unit_price": 4.99,
      "line_subtotal": 4.99
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

# Ontario HST Rules (13%)
ONTARIO_HST_RULES = """
ONTARIO HST RULES (for groceries/retail):

ZERO-RATED (taxable = false):
- Basic groceries: bread, milk, eggs, butter, cheese, yogurt, flour, rice, pasta, grains
- Fresh fruits and vegetables (raw or minimally processed)
- Fresh meat, fish, poultry (uncooked)
- Baby food, formula
- Coffee beans/grounds, tea (not prepared beverages)
- Most packaged foods intended for home consumption

TAXABLE (taxable = true):
- Prepared foods: sandwiches, salads, hot meals, ready-to-eat items
- Snacks: chips, candy, chocolate bars, cookies, pastries
- Soft drinks, energy drinks, sweetened beverages
- Alcohol (beer, wine, spirits)
- Non-food items: cleaning supplies, toiletries, household items, electronics
- Restaurant meals and catering
- Bakery items sold individually (single muffin, donut, etc.)

SPECIAL CASES:
- If item is explicitly marked as "taxable" on receipt, classify as taxable
- Instacart service fees, delivery fees, bag fees → usually taxable
- When unsure, default to taxable = false for grocery items

# ---------------- ABSOLUTE OVERRIDES ----------------
# If these appear, the item is NOT food, regardless of food words.
ALWAYS_TAXABLE = {
    # Stationery / office
    "notebook", "pen", "pencil", "marker", "highlighter",
    "paper", "folder", "binder", "journal", "cahier",

    # Containers / kitchenware
    "dispenser", "container", "bottle", "jar", "glass",
    "plastic", "steel", "utensil", "utensils",
    "spoon", "fork", "knife", "plate", "bowl", "cup",

    # Household / tools
    "cleaner", "detergent", "soap", "sponge", "brush",
    "battery", "electronics", "device", "charger",
}

# ---------------- NON-FOOD OBJECT SIGNALS ----------------
# These override food words like "oil", "vinegar", "salt"
NON_FOOD_OBJECTS = {
    "dispenser", "container", "glass", "bottle", "jar",
    "tool", "kitchenware", "accessory", "holder"
}

# ---------------- BASIC GROCERIES (NON-TAXABLE) ----------------
NON_TAXABLE_KEYWORDS = {
    # Dairy & eggs
    "milk", "cheese", "butter", "yogurt", "curd", "paneer",
    "egg", "eggs",

    # Grains / bakery
    "bread", "bun", "roll", "roti", "naan",
    "rice", "basmati", "jasmine",
    "flour", "atta", "maida",
    "oats", "cereal",

    # Pulses / legumes
    "lentil", "lentils", "dal", "beans", "chickpea", "peas",

    # Meat / seafood
    "chicken", "beef", "pork", "lamb", "fish", "salmon",
    "shrimp", "prawn", "meat", "seafood",

    # Vegetables
    "onion", "potato", "tomato", "carrot", "spinach",
    "broccoli", "cabbage", "cauliflower", "pepper",
    "cucumber", "zucchini", "okra", "corn",

    # Fruits
    "apple", "banana", "orange", "grape", "mango",
    "berry", "strawberry", "blueberry", "fruit",

    # Cooking basics
    "oil", "olive", "canola", "sunflower",
    "salt", "sugar", "spice", "masala", "ginger", "garlic",
}

# ---------------- TAXABLE CONSUMABLES ----------------
TAXABLE_KEYWORDS = {
    # Snacks / processed food
    "chips", "crisps", "snack", "snacks",
    "chocolate", "candy", "cookie", "cookies",
    "cracker", "crackers", "dessert",
    "icecream", "ice", "cream",

    # Drinks (taxable)
    "soda", "cola", "pop", "soft", "drink",
    "energy", "beverage", "juice",

    # Personal care
    "toothpaste", "toothbrush", "shampoo",
    "conditioner", "deodorant", "perfume",

    # Alcohol / restricted
    "alcohol", "beer", "wine", "liquor",
    "cigarette", "tobacco", "vape",
}
"""