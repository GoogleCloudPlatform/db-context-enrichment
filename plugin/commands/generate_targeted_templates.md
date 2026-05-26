---
description: Guided workflow to author a Template from a sample NL question and SQL pair.
---

The user wants to author a **Template** — an end-to-end mapping from a natural language query to a runnable SQL query.

Please activate the `context-generation-guide` skill and follow its workflow, scoped to the Template context type. Gather the natural language question and SQL from the user if not already provided, parameterize per the skill's guidelines, and save via `mutate_context_set`.
