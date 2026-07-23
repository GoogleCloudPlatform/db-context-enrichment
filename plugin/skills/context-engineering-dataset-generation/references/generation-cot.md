> [!IMPORTANT]
> **Parent Skill Reference**: This reference is used as part of the workflow defined in `context-engineering-dataset-generation/SKILL.md`.

When tasked with creating new pairs, using the generation plan as the guideline and north star. For *every* generated pair, execute the following internal Chain of Thought:

1. **Draft SQL (Schema-First):** Write syntactically perfect, dialect-compliant SQL using prioritized tables and conditions. Make sure to adhere to the technical schema and generation plan. Avoid inventing columns or tables based on business documents alone. For **BigQuery** sources, every table reference must be fully qualified as `` `project`.`dataset`.`table` `` (taken from the `kind: source` block in `tools.yaml`) — BigQuery has no default dataset at query time, so bare table names fail with "Table not found".  
2. **Literal Translation:** Translate the SQL literally into English to guarantee no logical constraints are missed.  
3. **Humanize & Bridge:** Rewrite the literal translation into natural business language, applying the *Semantic Bridge* principle.  
4. **Verify and Refine:** Apply `acceptance-criteria.md` to verify the generated pair. If the pair fails the acceptance criteria, backtrack and try again.
