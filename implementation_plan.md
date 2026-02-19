Below is your revised implementation plan, incorporating the critical corrections:

✅ Integer cents (no floats)

✅ Backend-calculated totals

✅ Explicit tax/tip allocation rule

✅ Deterministic ledger matching

✅ Strict authorization rules

✅ Version-based concurrency

✅ Safer deletion + settlement logic

This remains prototype-friendly but technically solid.

KVITTA ARCHITECTURE — REVISED (INTERVIEW-READY)

Core Philosophy
One Receipt = One Expense
Receipt generates immutable financial obligations.

1. GLOBAL MONEY RULE

All monetary values stored as integer cents.

Example:

$15.99 → 1599


All fields renamed accordingly.

2. DATA MODEL (UPDATED)
USERS
{
  "_id": ObjectId,
  "name": string,
  "email": string,
  "password_hash": string,
  "is_deleted": boolean,
  "created_at": Date,
  "updated_at": Date
}


Index:

email (unique)

RECEIPTS (Aggregate Root)
{
  "_id": ObjectId,

  "owner_id": ObjectId,
  "title": string,
  "description": string | null,
  "status": "draft" | "finalized" | "settled",
  "folder_id": ObjectId | null,

  "participants": [
    {
      "user_id": ObjectId,
      "role": "owner" | "member",
      "joined_at": Date
    }
  ],

  "items": [
    {
      "item_id": ObjectId,
      "name": string,
      "unit_price_cents": number,
      "quantity": number,
      "splits": [
        {
          "user_id": ObjectId,
          "share_quantity": number
        }
      ]
    }
  ],

  "payments": [
    {
      "user_id": ObjectId,
      "amount_paid_cents": number
    }
  ],

  "subtotal_cents": number,
  "tax_cents": number,
  "tip_cents": number,
  "total_cents": number,

  "version": number,

  "created_by": ObjectId,
  "updated_by": ObjectId,
  "is_deleted": boolean,

  "created_at": Date,
  "updated_at": Date
}

Backend Rules (CRITICAL)

Client may send:

items

payments

tax_cents

tip_cents

Backend calculates:

subtotal_cents = Σ(unit_price_cents × quantity)
total_cents = subtotal + tax + tip


If client total does not match → reject 400.

Tax & Tip Allocation Rule (Explicit)

When finalizing:

For each user:

item_owed_cents = Σ(item share value)

ratio = item_owed_cents / subtotal_cents

tax_share = round(tax_cents × ratio)
tip_share = round(tip_cents × ratio)

total_owed = item_owed + tax_share + tip_share


This ensures fair proportional distribution.

FOLDERS

Flat structure.

{
  "_id": ObjectId,
  "name": string,
  "color": string,
  "owner_id": ObjectId,
  "created_at": Date,
  "updated_at": Date,
  "is_deleted": boolean
}


Deletion allowed only if:

No finalized receipts inside.

LEDGERS
{
  "_id": ObjectId,
  "receipt_id": ObjectId,
  "debtor_id": ObjectId,
  "creditor_id": ObjectId,
  "amount_cents": number,
  "status": "open" | "settled",
  "created_at": Date,
  "updated_at": Date
}


No "adjusted" for prototype. Keep clean.

Indexes:

receipt_id
(debtor_id, status)
(creditor_id, status)

3. LEDGER GENERATION ENGINE (Deterministic)

Triggered on:

POST /receipts/{id}/finalize


Steps:

Validate:

status == draft

subtotal > 0

Σ payments == total_cents

split integrity per item

Compute owed per user (including tax & tip)

Compute paid per user

Compute net:

net = paid - owed


Partition:

creditors = users where net > 0
debtors = users where net < 0


Deterministic Matching Algorithm:

Sort creditors by user_id
Sort debtors by user_id

For each debtor:
    remaining_debt = abs(net)

    For each creditor:
        if creditor has remaining_credit:
            transfer = min(remaining_debt, creditor_credit)

            create ledger entry:
                debtor → creditor (transfer)

            subtract transfer from both

            continue until remaining_debt == 0


Guaranteed balanced.

Insert ledger entries in transaction.

Set receipt.status = finalized

4. SETTLEMENT LOGIC

Endpoint:

POST /ledger/{id}/settle


Body:

{
  "amount_cents": number
}


Rules:

Only debtor or creditor may settle.

amount ≤ open amount.

Partial settlement allowed.

If after settlement all ledger entries for receipt are settled:

receipt.status = settled

5. RECEIPT STATUS FLOW

draft
→ finalized (ledger created)
→ settled (all ledger entries closed)

No reverse transitions.

Delete allowed only if:

status == draft

6. AUTHORIZATION RULES

For every receipt request:

User must be:

owner OR participant.

Only owner can:

finalize

delete

move receipt

Participants can:

edit draft

add splits

record payments

No one edits finalized receipt.

7. CONCURRENCY CONTROL

Every update must include:

version


Update condition:

WHERE _id = receipt_id AND version = provided_version


If 0 documents updated → 409 Conflict.

Then increment version.

8. MEMBER RULES

Cannot remove member if:

Has splits

Has payments

Has ledger entries

Otherwise reject 400.

9. API ENDPOINT REFINEMENTS

Receipts:

POST /receipts
PATCH /receipts/{id}
POST /receipts/{id}/finalize
DELETE /receipts/{id}

Members:

POST /receipts/{id}/members
DELETE /receipts/{id}/members/{user_id}

Ledger:

GET /ledger/balance
GET /ledger/balance/{user_id}
GET /receipts/{id}/ledger
POST /ledger/{id}/settle

Folders:

POST /folders
PATCH /folders/{id}
DELETE /folders/{id}
PATCH /receipts/{id}/move

10. BALANCE CALCULATION ENDPOINT

GET /ledger/balance

Compute:

owes = Σ open where debtor_id = user
is_owed = Σ open where creditor_id = user
net = is_owed - owes

11. VALIDATION CHECKLIST

Reject if:

Negative money values

share_quantity ≤ 0

split sum ≠ quantity

payments sum ≠ total_cents (on finalize)

subtotal mismatch

editing finalized receipt

settling more than open amount

12. INTERVIEW DEFENSIBILITY

You can now justify:

Why integer cents

Why deterministic matching

Why version control

Why proportional tax allocation

Why ledger normalization

Why draft → finalized immutability

This version removes silent financial bugs and race conditions.

For a prototype, this is technically disciplined and structurally clean.

Can you break down the api into features I can commit step-by-step, so that I can implement one by one. In which commit, I should implement what, what functions & features, etc. Planned to be done in fastapi.

Below is a clean, interview-friendly commit roadmap for implementing Kvitta in FastAPI.

Each commit builds a complete vertical slice.
Each step should compile and run.

Stack Assumption:

FastAPI

Motor (async MongoDB)

Pydantic v2

JWT (python-jose)

bcrypt

PHASE 1 — Project Foundation
Commit 1 — Project Bootstrap

Goal: Running FastAPI app with Mongo connection.

Implement:

main.py

MongoDB connection (Motor client)

Basic health endpoint

Files:

app/main.py

app/core/config.py

app/db/mongo.py

Endpoints:
GET /health

Commit 2 — User Model + Database Layer

Goal: Define user schema + CRUD layer.

Implement:

Pydantic User schemas

Password hashing (bcrypt)

User repository functions:

create_user()

get_user_by_email()

get_user_by_id()

Files:

app/models/user.py

app/repositories/user_repo.py

app/core/security.py

No routes yet.

PHASE 2 — Authentication
Commit 3 — Auth: Signup + Login

Goal: Working JWT auth.

Implement:

Routes:

POST /auth/signup
POST /auth/login

Functions:

verify_password()

hash_password()

create_access_token()

authenticate_user()

Add:

JWT dependency:

get_current_user()

Files:

app/routes/auth.py

app/core/auth.py

Now protected routes possible.

Commit 4 — /auth/me + Auth Middleware
Implement:
GET /auth/me

Add:

JWT dependency injection

Global exception handling

Now authentication layer complete.

PHASE 3 — Folder Feature (Simple CRUD)
Commit 5 — Folder Schema + CRUD
Implement:

Folder schema (with is_deleted).

Repository:

create_folder()

list_folders()

update_folder()

soft_delete_folder()

Routes:
POST /folders
GET /folders
PATCH /folders/{id}
DELETE /folders/{id}


Authorization:

owner_id must match current user

Folder feature complete.

PHASE 4 — Receipt Draft System
Commit 6 — Receipt Schema (Draft Only)

Define:

integer cents

version field

status = draft default

Repository:

create_receipt()

get_receipt()

list_receipts()

Routes:

POST /receipts
GET /receipts
GET /receipts/{id}


Owner automatically added as participant.

Commit 7 — Receipt Update (Items + Payments)
Implement:
PATCH /receipts/{id}


Rules:

Only if status == draft

Validate:

non-negative values

split sum == quantity

Backend computes:

subtotal_cents

total_cents

Add:

optimistic concurrency check (version match)

Now draft editing works.

PHASE 5 — Members
Commit 8 — Add/Remove Members
Implement:
POST /receipts/{id}/members
DELETE /receipts/{id}/members/{user_id}
GET /receipts/{id}/members


Rules:

Email must exist

Cannot add duplicate

Cannot remove if financial activity exists

Now collaborative draft works.

PHASE 6 — Ledger Engine
Commit 9 — Ledger Schema + Repository

Create:

ledger model

insert_ledger_entries()

get_ledger_by_receipt()

get_user_balance()

No finalize yet.

Commit 10 — Receipt Finalization
Implement:
POST /receipts/{id}/finalize


Steps inside transaction:

Validate:

status == draft

payments sum == total_cents

Calculate:

per-user owed (proportional tax + tip)

net positions

Deterministic matching algorithm

Insert ledger entries

Update receipt.status = finalized

Now ledger generation works.

PHASE 7 — Ledger Reporting
Commit 11 — Ledger Query APIs

Implement:

GET /ledger/balance
GET /ledger/balance/{user_id}
GET /receipts/{id}/ledger


Aggregation:

owes

is_owed

net

Ledger visibility complete.

PHASE 8 — Settlement
Commit 12 — Partial Settlement

Implement:

POST /ledger/{id}/settle


Rules:

Only debtor or creditor

amount <= open amount

Update ledger entry

If fully settled → status = settled

After settlement:
Check if all ledger entries of receipt are settled → mark receipt.status = settled.

Now financial lifecycle complete.

PHASE 9 — Receipt Move + Folder Integration
Commit 13 — Move Receipt to Folder

Implement:

PATCH /receipts/{id}/move


Rules:

Folder must belong to user

Cannot move deleted receipt

PHASE 10 — Safety + Cleanup
Commit 14 — Authorization Hardening

Audit all endpoints:

Only owner can finalize

Only participants can edit draft

Only owner can delete

Cannot delete finalized receipt

Commit 15 — Input Validation Hardening

Add:

Central validation utilities

Negative money prevention

Zero quantity rejection

Duplicate split detection

OPTIONAL (if time)
Commit 16 — Global Exception Handler + Logging

Structured error responses

Central error middleware

Basic logging

IMPLEMENTATION ORDER SUMMARY

App bootstrap

Users

Auth

Folders

Receipt draft

Members

Ledger engine

Finalize

Balance API

Settlement

Hardening

Each phase gives a usable demo.

Why This Order Works

You always:

Build foundation

Add draft functionality

Then financial logic

Then lifecycle management

No premature ledger logic before receipt editing works.

If executed cleanly, this roadmap produces:

Auth system

Collaborative receipt splitting

Deterministic ledger generation

Settlement lifecycle

Folder organization

Concurrency control

Financial correctness

This is interview-grade architecture with clean incremental commits.