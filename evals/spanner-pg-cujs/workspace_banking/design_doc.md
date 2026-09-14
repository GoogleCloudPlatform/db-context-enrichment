# Product Requirements & System Architecture Specification
## Aura Financial Core Banking & Risk Analytics (v3.1)

---

### 1. Executive Summary & Product Vision

**Aura Financial** is a global commercial banking and institutional asset management platform running on Cloud Spanner (PostgreSQL dialect). The system manages high-throughput ledger transactions, multi-currency accounts, regulatory KYC/AML risk evaluations, and institutional credit portfolios across global financial centers (New York, London, Singapore, Tokyo, Frankfurt).

The platform embeds an **AI Banking Analytics Copilot** to empower treasury directors, risk analysts, and portfolio managers to query account balances, fraud anomaly indicators, and credit risk distributions using natural language.

---

### 2. Technical Stack & Database Architecture

* **Database Engine**: Cloud Spanner (PostgreSQL dialect)
* **Instance ID**: `nl2sql-spanner-pg`
* **Database Name**: `aura_banking_core`
* **Schema Namespace**: `public`

#### Relational Schema Overview (PostgreSQL Dialect)

1. **`accounts`**
   * `account_id`: `varchar(64) PRIMARY KEY`
   * `customer_id`: `varchar(64) NOT NULL`
   * `account_type`: `varchar(32)` (`'CHECKING'`, `'SAVINGS'`, `'TREASURY'`, `'ESCROW'`)
   * `currency`: `varchar(3)` (`'USD'`, `'EUR'`, `'GBP'`, `'JPY'`, `'SGD'`)
   * `balance`: `numeric NOT NULL DEFAULT 0.0000`
   * `status`: `varchar(16)` (`'ACTIVE'`, `'FROZEN'`, `'CLOSED'`)
   * `branch_code`: `varchar(16)`
   * `opened_at`: `timestamptz NOT NULL`

2. **`customers`**
   * `customer_id`: `varchar(64) PRIMARY KEY`
   * `legal_name`: `varchar(255) NOT NULL`
   * `entity_type`: `varchar(32)` (`'INDIVIDUAL'`, `'CORPORATION'`, `'INSTITUTION'`)
   * `country_code`: `varchar(2)`
   * `risk_score`: `bigint` (1 - 100)
   * `kyc_status`: `varchar(16)` (`'VERIFIED'`, `'PENDING'`, `'REJECTED'`)
   * `created_at`: `timestamptz NOT NULL`

3. **`transactions`**
   * `transaction_id`: `varchar(64) PRIMARY KEY`
   * `account_id`: `varchar(64) REFERENCES accounts(account_id)`
   * `transaction_type`: `varchar(32)` (`'DEPOSIT'`, `'WITHDRAWAL'`, `'TRANSFER'`, `'FEE'`)
   * `amount`: `numeric NOT NULL`
   * `currency`: `varchar(3) NOT NULL`
   * `counterparty_account`: `varchar(64)`
   * `status`: `varchar(16)` (`'COMPLETED'`, `'PENDING'`, `'REVERSED'`)
   * `executed_at`: `timestamptz NOT NULL`

4. **`credit_facilities`**
   * `facility_id`: `varchar(64) PRIMARY KEY`
   * `customer_id`: `varchar(64) REFERENCES customers(customer_id)`
   * `limit_amount`: `numeric NOT NULL`
   * `drawn_amount`: `numeric NOT NULL DEFAULT 0.0000`
   * `interest_rate`: `numeric`
   * `rating`: `varchar(8)` (`'AAA'`, `'AA'`, `'A'`, `'BBB'`, `'BB'`, `'B'`)
   * `maturity_date`: `date NOT NULL`

---

### 3. Query Guidelines & PostgreSQL Syntax Rules

* **Identifier Quoting**: All table and column names should be double-quoted in queries when appropriate (e.g., `SELECT "balance" FROM "accounts"`).
* **Positional Parameters**: Context templates and facets must use `$1`, `$2`, etc.
* **Dialect Functions**: Use standard PostgreSQL functions: `COALESCE()`, `DATE_TRUNC()`, `TO_CHAR()`, `||` for concatenation, and `spanner.generate_uuid()` for UUIDs.
