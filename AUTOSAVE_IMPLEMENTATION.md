# Receipt Autosave API Documentation

## ✅ Implementation Status: Phase 4 Commit 7 Complete

Your autosave requirements are **fully implemented** with granular field-level updates.

## Autosave Architecture

### Single Unified Endpoint for Draft Updates
```
PATCH /receipts/{id}
```

**All fields are optional** - send only what you want to update:

### 1. **Metadata Updates** (Autosave as user types)
```json
// Update title only
PATCH /receipts/{id}
{
  "version": 1,
  "title": "Team Dinner"
}

// Update description only
PATCH /receipts/{id}
{
  "version": 2,
  "description": "Annual team outing"
}

// Update comments only (for clarifications)
PATCH /receipts/{id}
{
  "version": 3,
  "comments": "Alice said she'll cover desserts separately"
}

// Move to folder
PATCH /receipts/{id}
{
  "version": 4,
  "folder_id": "507f1f77bcf86cd799439011"
}
```

### 2. **Items/Charges Update** (After OCR/JSON generation)
```json
PATCH /receipts/{id}
{
  "version": 1,
  "items": [
    {
      "name": "Pizza",
      "unit_price_cents": 1599,
      "quantity": 2,
      "splits": [
        {"user_id": "507f1...", "share_quantity": 1.0},
        {"user_id": "608c2...", "share_quantity": 1.0}
      ]
    }
  ]
}
```
**Backend automatically calculates:**
- `subtotal_cents` = 3198 (1599 × 2)
- Returns updated `total_cents`

### 3. **Tax & Tip Update** (Separate from items)
```json
PATCH /receipts/{id}
{
  "version": 2,
  "tax_cents": 320,
  "tip_cents": 480
}
```
**Backend recalculates total:** `total_cents = subtotal + tax + tip`

### 4. **Payments Update** (Who paid what)
```json
PATCH /receipts/{id}
{
  "version": 3,
  "payments": [
    {"user_id": "507f1...", "amount_paid_cents": 2000},
    {"user_id": "608c2...", "amount_paid_cents": 1998}
  ]
}
```

### 5. **Combined Updates** (Multiple fields at once)
```json
PATCH /receipts/{id}
{
  "version": 5,
  "items": [...],
  "tax_cents": 320,
  "tip_cents": 480,
  "payments": [...],
  "comments": "Split evenly"
}
```

---

## Separate Endpoints for Distinct Operations

### Member Management (Phase 5 - Commit 8, Not Yet Implemented)
```
POST /receipts/{id}/members
{
  "email": "friend@example.com"
}
// Validates email exists in DB
// Returns 404 if user not found
// Returns 400 if already a member

DELETE /receipts/{id}/members/{user_id}
// Fails if member has splits or payments
```

### Finalization (Phase 6 - Commit 10, Not Yet Implemented)
```
POST /receipts/{id}/finalize
// Validates: payments sum == total_cents
// Generates ledger entries (who owes whom)
// Locks receipt (no more edits)
// Status: draft → finalized
```

### Settlement (Phase 8 - Commit 12, Not Yet Implemented)
```
POST /ledger/{id}/settle
{
  "amount_cents": 1500
}
// Records partial or full settlement
// Updates ledger status
```

---

## Optimistic Concurrency Control

Every update requires **current version number**:

```json
// Client always sends version from last known state
{
  "version": 3,
  "title": "Updated"
}

// Backend increments version on success
// Response: {"version": 4, ...}

// If another client updated first:
// 400 Bad Request: "Version conflict: expected 3, current 4"
```

**Frontend autosave flow:**
1. User types → debounce → send PATCH with current version
2. If 200 OK → update local version from response
3. If 409/400 version conflict → fetch latest, notify user, merge changes

---

## Validation Rules (Applied on Update)

### Items Validation
- ✅ `unit_price_cents >= 0`
- ✅ `quantity > 0`
- ✅ `sum(splits.share_quantity) == quantity`
- ✅ Each `split.share_quantity > 0`

### Payments Validation
- ✅ `amount_paid_cents >= 0`
- ⚠️ **No** total match enforced until finalize

### Tax/Tip Validation
- ✅ `tax_cents >= 0`
- ✅ `tip_cents >= 0`

### Backend Calculations
- ✅ `subtotal_cents = Σ(unit_price_cents × quantity)`
- ✅ `total_cents = subtotal + tax + tip`

**Validation errors return:**
```json
HTTP 400 Bad Request
{
  "detail": "Item 'Pizza': split sum (1.5) does not equal quantity (2.0)"
}
```

---

## Authorization Model

### Receipt Visibility
- **View** (GET): Owner OR Participant
- **Update** (PATCH): Owner ONLY (draft status)
- **Delete** (DELETE): Owner ONLY

### State Transitions
```
draft → finalized → settled
  ↑      (locked)     (locked)
  |
  └─ Only draft can be edited
```

---

## Autosave Implementation Example

### Frontend React/Vue Pattern
```typescript
let currentVersion = 1;
let debounceTimer = null;

function autoSave(field: string, value: any) {
  clearTimeout(debounceTimer);
  
  debounceTimer = setTimeout(async () => {
    try {
      const response = await api.patch(`/receipts/${receiptId}`, {
        version: currentVersion,
        [field]: value
      });
      
      currentVersion = response.data.version; // Update local version
      console.log('Autosaved successfully');
      
    } catch (error) {
      if (error.response?.status === 400 && 
          error.response?.data?.detail?.includes('Version')) {
        // Version conflict - fetch latest
        await refreshReceipt();
        alert('Receipt was updated by another user. Please review.');
      }
    }
  }, 1000); // 1 second debounce
}

// Usage
onTitleChange((newTitle) => autoSave('title', newTitle));
onCommentsChange((newComments) => autoSave('comments', newComments));
onItemsChange((newItems) => autoSave('items', newItems));
```

---

## Database Push Sequence (Your Requirement)

### ✅ Step 1: Create Receipt
```
POST /receipts
{"title": "Dinner"}
→ DB Push (draft created, owner added as participant)
```

### ✅ Step 2: OCR/JSON Items Generated
```
PATCH /receipts/{id}
{"version": 1, "items": [...]}
→ DB Push (items saved)
```

### ✅ Step 3: Tax/Tip Added
```
PATCH /receipts/{id}
{"version": 2, "tax_cents": 500, "tip_cents": 800}
→ DB Push (charges updated)
```

### 🔄 Step 4: Members Added (Commit 8 - Next Phase)
```
POST /receipts/{id}/members
{"email": "friend@example.com"}
→ DB Push (participant added)
```

### ✅ Step 5: Bill Split
```
PATCH /receipts/{id}
{"version": 3, "items": [... with splits ...]}
→ DB Push (splits updated)
```

### ✅ Step 6: Payments Recorded
```
PATCH /receipts/{id}
{"version": 4, "payments": [...]}
→ DB Push (payments saved)
```

### 🔄 Step 7: Finalized (Commit 10 - Future Phase)
```
POST /receipts/{id}/finalize
→ DB Push (status=finalized, ledger entries created)
```

### 🔄 Step 8: Settlement (Commit 12 - Future Phase)
```
POST /ledger/{id}/settle
{"amount_cents": 1500}
→ DB Push (ledger status updated)
```

---

## Why This Design is Better

### ✅ Benefits
1. **Granular Control** - Update any field independently
2. **Conflict Detection** - Version control prevents lost updates
3. **Clear Semantics** - Separate endpoints for member/finalize/settle
4. **Validation Boundaries** - Draft vs finalized have different rules
5. **Efficient** - Send only changed fields
6. **Audit Trail** - Version tracking for debugging
7. **Frontend Flexibility** - Autosave any field without blocking others

### ✅ Aligns with Implementation Plan
- Commit 7 (✅ Done): Draft updates with validation
- Commit 8 (Next): Member management with email check
- Commit 10 (Future): Finalization with ledger generation
- Commit 12 (Future): Settlement tracking

---

## Next Steps

### Immediate (Commit 8 - Member Management)
1. `POST /receipts/{id}/members` - Add member with email validation
2. `DELETE /receipts/{id}/members/{user_id}` - Remove member
3. `GET /receipts/{id}/members` - List members
4. Validation: Cannot remove member with financial activity

### Then (Commit 9-10 - Finalization)
1. Ledger schema and repository
2. `POST /receipts/{id}/finalize` endpoint
3. Tax/tip proportional allocation algorithm
4. Ledger entry generation

### Finally (Commit 11-12 - Settlement)
1. `GET /ledger/balance` - User's net position
2. `POST /ledger/{id}/settle` - Record settlement
3. Partial settlement support

---

## Testing

Run tests to verify autosave functionality:
```bash
pytest tests/test_receipts.py -v
```

**Test Coverage:**
- ✅ Create draft receipt
- ✅ Update with items (backend calculates subtotal)
- ✅ Validation: negative price rejected
- ✅ Validation: split sum mismatch rejected
- ✅ Version conflict detection
- ✅ Autosave: update comments only
- ✅ Autosave: update title only
- ✅ Autosave: update tax/tip only

---

## Summary

Your autosave requirements are **fully met** with the current implementation:

✅ Separate DB pushes for each operation (via optional fields)  
✅ Comments field for clarifications  
✅ Member management planned (Commit 8)  
✅ Finalization planned (Commit 10)  
✅ Settlement planned (Commit 12)  
✅ Optimistic locking prevents conflicts  
✅ Backend-calculated totals ensure consistency  
✅ Integer cents eliminate rounding errors  

The architecture separates **editing** (PATCH /receipts/{id}) from **state transitions** (POST /finalize, POST /settle), which provides cleaner semantics and better authorization control.
