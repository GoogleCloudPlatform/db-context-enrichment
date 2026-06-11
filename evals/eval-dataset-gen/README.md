## CUJ: resolve_biz_rule_shift

**Setup**: In this CUJs, the user provides a design doc and the application source codes. The design doc (with outdated business rules) uses `customers` as the target table, while the application source (with updated business rule) uses `customers_v2` as the target table. Both tables share the same table definition but their content defers. 

**Source**: database is `petstore`, which contains both `customers` and `customers_v2` tables. 

**Expected Outcome**: The eval dataset generator needs to figure out that the SQL generated should always used `customers_v2` as the target table instead of `customers`, based on its inspection on the provided design doc and application source codes.

## CUJ: resolve_cryptic_schema

**Setup**: In this CUJ, the user provides a business context doc containing explaination over the cryptic column names in the database

**Source**: database is `db_ecommerce_cryptic`, which contains cryptic column names

**Expected Outcome**: The eval dataset generator needs to figure out how to generate NL which leverage domain knowledge from the business context doc which explains the cryptic column names, and its corresponding SQL only knows the cryptic column names.



## CUJ: grounding_github_code

**Setup**: In this CUJ, the user only provides the github link https://github.com/kupp0/google-dach-summit26-database-labs/tree/main/labs/03_fullstack_ai_app_property_search.

**Source**: database is `search`, which contains test data for the app.

**Expected Outcome**: The eval dataset generator needs to figure out based on the application source codes at https://github.com/kupp0/google-dach-summit26-database-labs/tree/main/labs/03_fullstack_ai_app_property_search what NL-SQL pairs to generate.


## CUJ: grounding_querylog

**Setup**: In this CUJ, the user provides the querylog file `querylog.txt` which simulates the query log for the `financials` database.

**Source**: database is `financials` from BIRD.

**Expected Outcome**: The eval dataset generator needs to figure out how to extract the SQL from the query log, and then translate them to seed pairs with the corresponding NL while ensuring the NL is unambiguous and logically align with the SQL. In the case the number of pairs user ask is more than the SQLs in the querylog, the eval dataset generator needs to uses its knowledge and inspection of querylog to come up with more NL-SQL pairs.

## CUJ: grounding_local_code

**Setup**: In this CUJ, the user provides the `app_data` directory containing the application codes.

**Source**: database is the `db_hr`.

**Expected Outcome**: The eval dataset generator needs to figure out which tables and columns to use to generate NL-SQL so that it alighns with the application codes.