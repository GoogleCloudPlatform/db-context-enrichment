# Product Requirements & Schema Architecture Specification
## Global Hospitality & Hotel Search Platform (v1.2)

---

### 1. Executive Summary & Product Vision

The **Global Hospitality Platform** manages property metadata, live pricing tiers, guest amenities, and review scores across hundreds of thousands of international hotels. 

To support high-throughput, low-latency reservation queries alongside analytical reporting, the core hospitality inventory is hosted on **Google Cloud Bigtable**. We are embedding a **Natural Language Query Copilot** that allows travel agents, pricing analysts, and support staff to query hotel inventory, pricing distributions, and customer satisfaction metrics using natural language.

---

### 2. Infrastructure & Data Source Configuration

- **Database Engine**: Google Cloud Bigtable (BTQL Dialect)
- **GCP Project**: `cloud-db-nl2sql`
- **Instance ID**: `evalbench-hotels`
- **Primary Table**: `hotels`

---

### 3. Data Model & Column Family Schema

The `hotels` table uses a partitioned row key design combined with four distinct column families:

```
Row Key Pattern: hotel#<CountryCode>#<City>#<HotelId>
Example:         hotel#USA#Seattle#0042
```

#### Column Families & Qualifiers

| Column Family | Qualifier | Data Type (Logical) | Description | Example Values |
| :--- | :--- | :--- | :--- | :--- |
| *(Row Key)* | `_key` | `STRING` | Primary unique row identifier | `hotel#USA#Seattle#0042`, `hotel#USA#Austin#1099` |
| **`details`** | `name` | `STRING` | Hotel property name | `"Grand Hyatt Seattle"`, `"Fairmont Olympic"` |
| **`details`** | `city` | `STRING` | Metropolitan city location | `"Seattle"`, `"New York"`, `"Chicago"` |
| **`details`** | `state` | `STRING` | State or province abbreviation | `"WA"`, `"NY"`, `"CA"`, `"IL"` |
| **`details`** | `address` | `STRING` | Street address | `"721 Pine St"`, `"411 University St"` |
| **`details`** | `star_rating` | `INT64` | Hotel star classification (1-5) | `"3"`, `"4"`, `"5"` |
| **`pricing`** | `nightly_rate`| `FLOAT64` | Standard nightly room rate in USD | `"149.00"`, `"289.50"`, `"520.00"` |
| **`pricing`** | `currency` | `STRING` | Billing currency code | `"USD"`, `"EUR"`, `"GBP"` |
| **`amenities`**| `has_pool` | `STRING` / `BOOL` | Whether pool is available | `"true"`, `"false"` |
| **`amenities`**| `has_wifi` | `STRING` / `BOOL` | High-speed wireless internet | `"true"`, `"false"` |
| **`amenities`**| `has_spa` | `STRING` / `BOOL` | Full-service spa facilities | `"true"`, `"false"` |
| **`amenities`**| `pets_allowed`| `STRING` / `BOOL` | Pet-friendly accommodation | `"true"`, `"false"` |
| **`reviews`** | `avg_rating` | `FLOAT64` | Aggregate guest rating (1.0 - 5.0)| `"4.6"`, `"4.9"`, `"3.8"` |
| **`reviews`** | `cleanliness_score` | `FLOAT64` | Dedicated cleanliness score (1-5) | `"4.8"`, `"5.0"`, `"4.2"` |
| **`reviews`** | `review_count`| `INT64` | Total verified guest reviews | `"1240"`, `"350"`, `"89"` |

---

### 4. Bigtable Query Syntax (BTQL) Rules & Conventions

Queries executed against Cloud Bigtable must follow GoogleSQL for Bigtable (BTQL) syntax standards:

1. **Column Family Access**: Qualifiers must be accessed using subscript bracket notation on the column family:
   - Correct: `details['city']`, `pricing['nightly_rate']`, `amenities['has_pool']`
   - Incorrect: `details.city` or `city`
2. **Type Casting for Numeric Aggregations & Comparisons**: Bigtable values are stored as byte strings. When filtering, comparing, or aggregating numeric fields, cast them explicitly:
   - Floats: `TO_FLOAT64(pricing['nightly_rate']) < 200.0`
   - Integers: `TO_INT64(details['star_rating']) = 5`
3. **Table Identifier Quoting**: Enclose table names in backticks:
   - Example: ``SELECT _key, details['name'] FROM `hotels` WHERE ...``
4. **Row Key Optimization**: Utilize the `_key` pseudo-column for fast prefix scanning when searching by geographic hierarchy:
   - Example: `WHERE _key LIKE 'hotel#USA#Austin%'`

---

### 5. Target Query Classes & Business Scenarios

The Natural Language Copilot must handle the following primary query patterns:

#### Class 1: Geographic & Price-Bound Search
- *"Find all hotels in Seattle with nightly rate under 200"*
- *"Calculate minimum, maximum, and average hotel price in Boston"*

#### Class 2: Amenities & Pet-Friendly Filters
- *"Show pet-friendly hotels with cleanliness score above 4.8"*
- *"List hotels with a swimming pool and wifi in California"*
- *"Find cheapest hotels in Miami with spa"*

#### Class 3: Star Rating & Aggregate Analytics
- *"What is the average price of 5-star hotels in San Francisco?"*
- *"Count total hotels by star rating in New York"*
- *"Find top 5 highest rated hotels in Chicago"*

#### Class 4: Exact Entity & Row Key Lookups
- *"Lookup hotel by name Grand Hyatt Seattle"*
- *"Find hotels with row key prefix hotel#USA#Austin"*
