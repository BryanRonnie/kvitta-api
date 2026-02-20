# Implementation Status vs Plan

## ✅ Complete (Commit 6-7)

### Commit 6: Receipt Schema (Draft Only)
- ✅ `POST /receipts` - Create draft receipt
- ✅ `GET /receipts` - List receipts (user is owner or participant)
- ✅ `GET /receipts/{id}` - Get receipt by ID
- ✅ Owner automatically added as participant
- ✅ Integer cents fields (subtotal_cents, tax_cents, tip_cents, total_cents)
- ✅ Version field for optimistic locking
- ✅ Status defaults to "draft"
- ✅ Comments field for clarifications

### Commit 7: Receipt Update (Items + Payments)
- ✅ `PATCH /receipts/{id}` - Update draft receipt
- ✅ Supports individual field updates (autosave)
- ✅ Items validation (split sum == quantity, non-negative prices)
- ✅ Backend calculates subtotal and total
- ✅ Optimistic locking (version check)
- ✅ Tax/tip updates
- ✅ Payments updates
- ✅ Only works on draft status

---

## 🔄 Next: Commit 8 - Member Management

**Missing Endpoints:**
```
POST /receipts/{id}/members          # Add member by email
DELETE /receipts/{id}/members/{uid}  # Remove member
GET /receipts/{id}/members           # List members (maybe)
```

**Rules to implement:**
- Email validation (must exist in users DB)
- Cannot add duplicate member
- Cannot remove if has splits/payments/ledger entries
- Member added → receipt visible to them

**Files needed:**
- `app/routes/members.py` (or add to receipts.py)
- Update receipt_repo.py with member operations
- Tests in test_receipts.py

---

## 🔄 Future: Commit 9-10 - Finalization & Ledger

**Missing Endpoints:**
```
POST /receipts/{id}/finalize         # Lock receipt, generate ledger
POST /ledger/{id}/settle             # Record settlement
GET /ledger/balance                  # User's net position
GET /ledger/balance/{user_id}        # Another user's balance
GET /receipts/{id}/ledger            # Ledger entries for receipt
```

**Models needed:**
```python
class Ledger(MongoModel):
    receipt_id: ObjectId
    debtor_id: ObjectId
    creditor_id: ObjectId
    amount_cents: int
    status: "open" | "settled"
```

**Finalization Logic:**
1. Validate status == draft
2. Validate Σ payments == total_cents
3. Calculate per-user owed (including proportional tax/tip)
4. Run deterministic matching algorithm
5. Insert ledger entries
6. Set receipt.status = finalized

---

## Summary

**What You Have:**
- Draft receipt creation with autosave
- Item/payment/tax/tip updates
- Comments for collaboration
- Version control to prevent conflicts

**What's Missing:**
- ❌ Add members endpoint (Commit 8)
- ❌ Remove member endpoint (Commit 8)
- ❌ Finalize endpoint (Commit 10)
- ❌ Ledger model & repository (Commit 9)
- ❌ Settlement endpoint (Commit 12)
- ❌ Balance query endpoints (Commit 11)

**Recommendation:**
Implement Commit 8 next (member management) since it unblocks finalization testing.
