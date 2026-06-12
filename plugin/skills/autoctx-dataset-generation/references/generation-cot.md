When tasked with creating new pairs, using the generation plan as the guideline and north star. For *every* generated pair, execute the following internal Chain of Thought:

1. **Draft SQL (Schema-First):** Write syntactically perfect, dialect-compliant SQL using prioritized tables and conditions. Make sure to adhere to the technical schema and generation plan. Avoid inventing columns or tables based on business documents alone.  
2. **Literal Translation:** Translate the SQL literally into English to guarantee no logical constraints are missed.  
3. **Humanize & Bridge:** Rewrite the literal translation into natural business language, applying the *Semantic Bridge* principle.  
4. **Verify and Refine:** Apply the acceptance criteria to verify the generated pair. If the pair fails the acceptance criteria, refine the query or natural language and verify again.