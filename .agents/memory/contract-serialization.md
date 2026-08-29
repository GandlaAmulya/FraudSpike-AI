---
name: Contract serialization
description: Pydantic contract constraints used by the FraudSpike domain layer
---

Pydantic schema generation can recurse indefinitely on an implicitly recursive
JSON type alias. Use a bounded value shape or Pydantic's explicit named alias
support when nested JSON is required. Keep monetary values as `Decimal` in
Python and represent them as strings across JSON/TypeScript. Pydantic's JSON
mode emits UTC-aware datetimes with the canonical `Z` suffix.

**Why:** These choices preserve monetary precision and prevent schema
generation/runtime test failures while keeping frontend contracts honest.

**How to apply:** When adding API-facing domain values, validate timestamps as
timezone-aware UTC values, use Decimal for money/rates where precision matters,
and test `model_dump(mode="json")` rather than assuming a particular offset
spelling.