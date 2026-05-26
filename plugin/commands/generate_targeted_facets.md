---
description: Guided workflow to author a Facet from a reusable SQL fragment and its intent.
---

The user wants to author a **Facet** — a reusable, modular SQL fragment (e.g., a WHERE clause or specialized join) tied to a specific vocabulary or terminology.

Please activate the `context-generation-guide` skill and follow its workflow, scoped to the Facet context type. Gather the intent and SQL snippet from the user if not already provided, parameterize per the skill's guidelines, and save via `mutate_context_set`.
