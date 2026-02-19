"""Receipt validation utilities."""
from typing import List
from app.schemas.receipt import ItemBase


class ReceiptValidationError(Exception):
    """Custom exception for receipt validation errors."""
    pass


def validate_items(items: List[ItemBase]) -> None:
    """
    Validate receipt items.
    
    Rules:
    - unit_price_cents must be non-negative
    - quantity must be positive
    - For each item, sum of split shares must equal quantity
    """
    for item in items:
        # Check non-negative price
        if item.unit_price_cents < 0:
            raise ReceiptValidationError(
                f"Item '{item.name}' has negative price: {item.unit_price_cents}"
            )
        
        # Check positive quantity
        if item.quantity <= 0:
            raise ReceiptValidationError(
                f"Item '{item.name}' has non-positive quantity: {item.quantity}"
            )
        
        # Check split sum equals quantity
        if item.splits:
            split_sum = sum(split.share_quantity for split in item.splits)
            if abs(split_sum - item.quantity) > 0.0001:  # Float comparison tolerance
                raise ReceiptValidationError(
                    f"Item '{item.name}': split sum ({split_sum}) does not equal quantity ({item.quantity})"
                )
        
        # Check each split has positive share
        for split in item.splits:
            if split.share_quantity <= 0:
                raise ReceiptValidationError(
                    f"Item '{item.name}' has non-positive split share: {split.share_quantity}"
                )


def validate_payments(payments: List, amount_cents: int) -> None:
    """
    Validate payments (basic validation - no negative amounts).
    Note: We don't enforce payments == total until finalize.
    """
    for payment in payments:
        if payment.amount_paid_cents < 0:
            raise ReceiptValidationError(
                f"Payment has negative amount: {payment.amount_paid_cents}"
            )


def calculate_subtotal(items: List[ItemBase]) -> int:
    """Calculate subtotal from items (in cents)."""
    subtotal = 0
    for item in items:
        item_total = int(item.unit_price_cents * item.quantity)
        subtotal += item_total
    return subtotal


def calculate_total(subtotal_cents: int, tax_cents: int, tip_cents: int) -> int:
    """Calculate total from subtotal, tax, and tip."""
    return subtotal_cents + tax_cents + tip_cents
