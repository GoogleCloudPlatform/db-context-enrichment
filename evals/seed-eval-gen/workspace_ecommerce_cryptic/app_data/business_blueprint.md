## E-Commerce Platform Blueprint & Cryptographic Data Dictionary

### Executive Summary

This document serves as the master key for the e-commerce platform's data architecture. The physical database schema utilizes a heavily abbreviated, cryptic naming convention (`t_` for tables, consonant-heavy shorthand for columns) to prevent immediate comprehension by unauthorized actors. This blueprint maps those cryptic entities back to their respective business domains and operational logic.

### 1. The Rosetta Stone: Global Naming Convention

To read the database, developers must apply the following global translation rules.

**Table Prefixes:** All tables begin with `t_`.
**Common Suffixes/Shorthand:**

* `_id`: Identifier (Primary/Foreign Key)
* `_nm`: Name
* `_dt`: Date / Timestamp
* `_amt`: Amount / Financial Value
* `_sts`: Status
* `_qty`: Quantity
* `_mthd`: Method

**Domain Mappings:**

| Business Concept | Cryptic Table Name | Cryptic Column Examples |
| --- | --- | --- |
| **Users / Customers** | `t_usr` | `u_id` (User ID), `eml` (Email), `gndr` (Gender) |
| **Products / Catalog** | `t_prd` | `p_id` (Product ID), `prc` (Price), `stk_qty` (Stock Quantity) |
| **Categories** | `t_cat` | `c_id` (Category ID), `c_nm` (Category Name) |
| **Orders** | `t_ord` | `o_id` (Order ID), `t_amt` (Total Amount), `sts` (Order Status) |
| **Order Items** | `t_o_itm` | `oi_id` (Order Item ID), `p_id` (Product ID) |
| **Returns** | `t_rtn_req` | `r_id` (Return ID), `r_rsn` (Return Reason), `r_sts` (Return Status) |
| **Shipping** | `t_shp` | `s_id` (Shipping ID), `c_nm` (Carrier Name) |

---

### 2. Business Domain Architecture

#### A. User & Identity Management Domain (Table: `t_usr`)

This domain handles the complete lifecycle and segmentation of all platform actors.

* **Demographic Tracking:** Captures rich demographic data (`dob`, `gndr`, `occ` for occupation) to drive personalized recommendations.
* **Security & Access:** Tracks account security through failed login attempts (`f_log_a`) and account lockouts (`a_lck_dt`).
* **Location Management (Table: `t_addr`):** Manages user addresses (`s_addr` for street, `pst_c` for postal code), categorized by type (`a_typ`) to optimize shipping logistics.

#### B. Catalog & Inventory Domain (Tables: `t_prd`, `t_cat`, `t_brnd`)

This is the core of the platform's offering, tracking inventory health and hierarchical taxonomies.

* **Taxonomy (`t_cat`):** Utilizes a nested model (`l_lvl`, `r_val`) for deep, highly performant sub-category trees.
* **Inventory Lifecycle (`t_prd`):** Tracks stock quantities (`stk_qty`) and availability statuses (`a_sts`). The system triggers restocking alerts when `stk_qty` drops below thresholds.
* **Financials:** Tracks base price (`prc`), discounted price (`d_prc`), and discount percentages (`d_pct`) for margin calculations.

#### C. Sales & Order Fulfillment Domain (Tables: `t_ord`, `t_o_itm`, `t_shp`)

Manages the customer's purchasing journey from intent to physical delivery.

* **Transaction Processing (`t_ord`):** Orders are linked to specific payment methods (`p_mthd`) and shipping methods (`s_mthd`). Total revenue calculations rely heavily on the `t_amt` column.
* **Logistics Tracking (`t_shp`):** Integrates shipping details directly with orders. It measures estimated (`e_d_dt`) versus actual delivery dates (`a_d_dt`) to evaluate external carrier (`c_nm`) performance.

#### D. Reverse Logistics & Customer Support (Tables: `t_rtn_req`, `t_rfnd`)

Handles post-purchase customer satisfaction and issue resolution.

* **Returns Management (`t_rtn_req`):** Tracks the reason for return (`r_rsn`), current operational status (`r_sts`), and resolution notes (`r_nts`). This allows the business to identify recurring product defects.
* **Refund Processing (`t_rfnd`):** Tracks the financial return to the customer, logging the refund amount (`r_amt`) and the method used (`r_mthd`).
