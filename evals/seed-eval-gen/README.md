
## CUJ: case_flights

**Setup**: In this CUJ, the user only provides the https://docs.cloud.google.com/alloydb/docs/ai/integrate-applications-data-agent documentation link. 

**Source**: database is `db_dummy`, which does not contain any table.

**Expected Outcome**: The eval dataset generator needs to figure out based on the documentation at https://docs.cloud.google.com/alloydb/docs/ai/integrate-applications-data-agent what NL-SQL pairs to generate.


## CUJ: case_property_search

**Setup**: In this CUJ, the user only provides the github link https://github.com/kupp0/multi-db-property-search-data-agents.

**Source**: database is `search`, which contains test data for the app.

**Expected Outcome**: The eval dataset generator needs to figure out based on the application source codes at https://github.com/kupp0/multi-db-property-search-data-agents what NL-SQL pairs to generate.

## CUJ: case_blog

**Setup**: In this CUJ, the user provides the `app_data` folder containing a `ER_Diagram.jpg` which sketch the ER diagram for blog application as well as its `design_doc.pdf`. 

**Source**: database is `db_dummy`, which does not contain any table.

**Expected Outcome**: The eval dataset generator need to figure out that the `<source>-list-schemas` returns the empty schema (since the user did not create any table in the schema), infers the schema from the `ER_Diagram.jpg` and makes use of the content in the `design_doc.pdf` to generate NL-SQL pairs.

## CUJ: case_ecommerce_cryptic

**Setup**: In this CUJ, the user provides a business context doc containing explaination over the cryptic column names in the database

**Source**: database is `db_ecommerce_cryptic`, which contains cryptic column names

**Expected Outcome**: The eval dataset generator needs to figure out how to generate NL which leverage domain knowledge from the business context doc which explains the cryptic column names, and its corresponding SQL only knows the cryptic column names.

## CUJ: case_financials

**Setup**: In this CUJ, the user provides the querylog file `querylog.txt` which simulates the query log for the `financials` database.

**Source**: database is `financials` from BIRD.

**Expected Outcome**: The eval dataset generator needs to figure out how to extract the SQL from the query log, and then translate them to the corresponding NL while ensuring the NL is unambiguous and logically align with the SQL. In the case the number of pairs user ask is more than the SQLs in the querylog, the eval dataset generator needs to uses its knowledge and inspection of querylog to come up with more NL-SQL pairs.

## CUJ: case_hr

**Setup**: In this CUJ, the user provides the `app_data` directory containing the application codes.

**Source**: database is the `db_hr`.

**Expected Outcome**: The eval dataset generator needs to figure out which tables and columns to use to generate NL-SQL so that it alighns with the application codes.