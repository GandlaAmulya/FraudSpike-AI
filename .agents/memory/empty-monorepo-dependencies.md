---
name: Empty monorepo dependency setup
description: Replit package setup behavior to watch for in a split frontend/backend repository
---

When adding Python dependencies to an otherwise empty monorepo, the Replit
package setup may initialize Python metadata at the repository root rather
than inside the intended backend directory. Keep the authoritative Python
project metadata scoped to `backend/` and remove accidental root bootstrap
files.

**Why:** Root-level bootstrap metadata can conflict with a deliberate
frontend/backend monorepo layout and make future dependency ownership
ambiguous.

**How to apply:** After installing Python dependencies in a new monorepo,
inspect the root for generated `pyproject.toml`, lockfiles, or starter
modules before finalizing the scaffold.