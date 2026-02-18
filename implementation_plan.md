Architecture layers:
Data Layer (Mongo schemas + indexes)
Domain Services (business rules)
API Layer (HTTP contracts)
Ledger Engine

1. DATABASE SCHEMAS
Collections:
users
folders
folder_members
receipts
ledger_entries
settlements

USERS
Schema
{
  "_id": ObjectId,
  "name": string,
  "email": string,
  "created_at": datetime,
  "updated_at": datetime,
  "is_deleted": boolean
}

Indexes

unique(email)

Purpose

Identity + authentication anchor.
No financial logic here.

FOLDERS
Schema
{
  "_id": ObjectId,
  "owner_id": ObjectId,
  "name": string,
  "parent_folder_id": ObjectId | null,
  "created_at": datetime,
  "updated_at": datetime,
  "is_deleted": boolean
}

Indexes

owner_id

parent_folder_id

(owner_id, name)

Purpose

Organizational grouping of receipts.
No financial data stored here.

FOLDER_MEMBERS
Schema
{
  "_id": ObjectId,
  "folder_id": ObjectId,
  "user_id": ObjectId,
  "role": "owner" | "editor" | "viewer",
  "joined_at": datetime
}

Indexes

(folder_id, user_id)

Purpose

Access control layer.

RECEIPTS (AGGREGATE ROOT)
Schema
{
  "_id": ObjectId,

  "owner_id": ObjectId,
  "folder_id": ObjectId | null,

  "title": string,
  "status": "draft" | "finalized" | "settled",

  "participants": [
    {
      "user_id": ObjectId,
      "joined_at": datetime
    }
  ],

  "items": [
    {
      "item_id": ObjectId,
      "name": string,
      "unit_price": float,
      "quantity": float,
      "splits": [
        {
          "user_id": ObjectId,
          "share_quantity": float
        }
      ]
    }
  ],

  "payments": [
    {
      "user_id": ObjectId,
      "amount_paid": float
    }
  ],

  "subtotal": float,
  "tax": float,
  "tip": float,
  "total": float,

  "version": int,

  "created_at": datetime,
  "updated_at": datetime,
  "created_by": ObjectId,
  "updated_by": ObjectId,

  "is_deleted": boolean
}

Indexes

owner_id

folder_id

participants.user_id

status

Purpose

Immutable financial document once finalized.
Ledger derived from here.

LEDGER_ENTRIES
Schema
{
  "_id": ObjectId,

  "receipt_id": ObjectId,

  "debtor_id": ObjectId,
  "creditor_id": ObjectId,

  "amount": float,

  "status": "open" | "settled",

  "created_at": datetime,
  "settled_at": datetime | null
}

Indexes

(debtor_id, status)

(creditor_id, status)

receipt_id

Purpose

Normalized debt representation.

SETTLEMENTS
Schema
{
  "_id": ObjectId,

  "from_user_id": ObjectId,
  "to_user_id": ObjectId,

  "amount": float,

  "created_at": datetime
}

Indexes

from_user_id

to_user_id

Purpose

Real money transfer event.

2. DOMAIN SERVICES

Separate business logic from API.

ReceiptService
create_receipt()

Validate folder access

Insert draft receipt

update_receipt()

Only if status == draft

Validate split integrity

Recalculate subtotal & total

Increment version

finalize_receipt()

Validate all invariants

Lock receipt (status = finalized)

Trigger LedgerService.generate_from_receipt()

delete_receipt()

Soft delete only

LedgerService
generate_from_receipt(receipt_id)

Steps:

Compute owed per user

For each item:

owed[user] += unit_price * share_quantity


Compute paid per user

paid[user] += amount_paid


Compute net

net[user] = paid - owed


Partition:

creditors = net > 0

debtors = net < 0

Create pairwise debt entries:
Distribute debtor deficits to creditors.

Insert ledger_entries

get_user_balance(user_id)

Aggregate:

owed_by = sum(open where debtor_id = user)
owed_to = sum(open where creditor_id = user)

Return:

{
  "owes": owed_by,
  "is_owed": owed_to,
  "net": owed_to - owed_by
}

SettlementService
create_settlement(from_user, to_user, amount)

Steps:

Insert settlement record

Reduce open ledger entries:

Oldest first

Partial reduce allowed

Mark ledger entries settled when amount == 0

If all entries of receipt settled:

Optionally mark receipt.status = settled

3. API STRUCTURE

Prefix: /api/v1

USERS

POST /users
GET /users/{id}

FOLDERS

POST /folders
GET /folders
PATCH /folders/{id}
DELETE /folders/{id}

POST /folders/{id}/members
DELETE /folders/{id}/members/{user_id}

RECEIPTS

POST /receipts
→ create draft

GET /receipts/{id}

PATCH /receipts/{id}
→ update draft only

POST /receipts/{id}/finalize
→ generates ledger entries

DELETE /receipts/{id}

POST /receipts/{id}/move
body: { folder_id }

LEDGER

GET /ledger/balance/{user_id}

GET /ledger/user/{user_id}
→ all open entries

GET /ledger/receipt/{receipt_id}

SETTLEMENTS

POST /settlements

GET /settlements/user/{user_id}

4. DATA VALIDATION RULES

Receipt Draft Stage:

All participants exist

All split users exist in participants

For each item:
sum(share_quantity) == quantity

Finalize Stage:

sum(payments.amount_paid) == total

No negative net drift

Settlement Stage:

Cannot settle more than open balance

5. TRANSACTIONAL REQUIREMENTS

Use MongoDB transactions when:

Finalizing receipt

Generating ledger entries

Creating settlement and updating ledger

All must be atomic.

6. STATUS FLOW

draft
→ finalized (ledger created)
→ settled (all ledger entries settled)

No reverse transition.

7. VERSION CONTROL

Use optimistic concurrency:

When updating receipt:

update where _id = X AND version = Y


If modified count == 0 → conflict.

Increment version each write.

8. SECURITY MODEL

Every request must verify:

User exists

User has folder access

User is participant for financial modification

Viewer cannot mutate

Authorization lives in service layer.