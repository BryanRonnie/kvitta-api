"""Receipt validation utilities."""
from typing import List, Optional
from app.schemas.receipt import ItemBase, ChargeBase


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


def validate_charges(charges: Optional[List[ChargeBase]]) -> None:
    """
    Validate charges (taxes, tips, fees, etc.).
    
    Rules:
    - unit_price_cents must be non-negative
    - If splits are specified, they must sum to 1.0 (100% of charge)
    """
    if not charges:
        return
    
    for charge in charges:
        # Check non-negative price
        if charge.unit_price_cents < 0:
            raise ReceiptValidationError(
                f"Charge '{charge.name}' has negative price: {charge.unit_price_cents}"
            )
        
        # Check split sum equals 1.0 if splits are specified
        if charge.splits:
            split_sum = sum(split.share_quantity for split in charge.splits)
            if abs(split_sum - 1.0) > 0.0001:  # Float comparison tolerance
                raise ReceiptValidationError(
                    f"Charge '{charge.name}': split sum ({split_sum}) does not equal 1.0"
                )
        
        # Check each split has positive share
        for split in charge.splits:
            if split.share_quantity <= 0:
                raise ReceiptValidationError(
                    f"Charge '{charge.name}' has non-positive split share: {split.share_quantity}"
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


def calculate_charges_total(charges: Optional[List[ChargeBase]]) -> int:
    """Calculate total charges from charges list."""
    if not charges:
        return 0
    return sum(charge.unit_price_cents for charge in charges)


def calculate_total(subtotal_cents: int, charges: Optional[List[ChargeBase]] = None) -> int:
    """Calculate total from subtotal and charges."""
    charges_total = calculate_charges_total(charges)
    return subtotal_cents + charges_total
