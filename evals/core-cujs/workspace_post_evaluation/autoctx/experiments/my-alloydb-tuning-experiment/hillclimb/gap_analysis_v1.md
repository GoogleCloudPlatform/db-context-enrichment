# Gap Analysis Report - v1

## Summary
- **Total Queries**: 4
- **Passed**: 3
- **Failed**: 1
- **Pass Rate**: 75%

## Failed Queries Detail

### Query 1: "How many accounts who choose issuance after transaction are staying in East Bohemia region?" (eval_001)
- **Error Category**: `[ValueLinkingError]`, `[CountingError]`
- **Expected SQL**: `SELECT COUNT(DISTINCT "T1"."account_id") FROM "account" AS "T1" INNER JOIN "district" AS "T2" ON "T1"."district_id" = "T2"."district_id" WHERE "T2"."A3" = 'east Bohemia' AND "T1"."frequency" = 'POPLATEK PO OBRATU'`
- **Actual SQL**: `SELECT COUNT("account"."account_id") FROM "account" JOIN "district" ON "account"."district_id" = "district"."district_id" WHERE "district"."A3" = 'East Bohemia' AND "account"."frequency" = 'POPLATEK PO OBRATU';`
- **Root Cause**: 
    1. The LLM used the casing from the prompt ('East Bohemia') instead of the casing in the database ('east Bohemia').
    2. The LLM failed to use `COUNT(DISTINCT ...)` for "How many accounts".
- **Proposed Mutation**: 
    1. Add a facet for regions in `district.A3` that handles the common casing (or a value search, but instructions say ONLY `templates` and `facets`). I'll use a facet to map "East Bohemia" to "east Bohemia" or just provide the correct value. Actually, a facet mapping "East Bohemia" to the snippet `"district"."A3" = 'east Bohemia'` would work.
    2. Add or update a template that demonstrates `COUNT(DISTINCT account_id)` for "How many accounts".
