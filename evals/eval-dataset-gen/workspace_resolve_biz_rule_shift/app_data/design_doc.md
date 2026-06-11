# Pet Store API Web Service - Design Document

APPROVAL DATE: 2026-05-01

## 1. Overview
This document outlines the architecture, data model, and API design for the Pet Store Web Service. The application is a RESTful API built with Python and Flask, backed by a PostgreSQL database. It provides endpoints to manage pet inventory, customer records, and sales transactions.

## 2. High-Level Design (HLD)
The system follows a standard three-tier architecture:
*   **Presentation / API Layer:** Implemented using Flask (and optionally Flask-RESTful or Flask-Smorest), handling HTTP request parsing, routing, and JSON serialization.
*   **Business Logic Layer:** Python services that orchestrate data validation, state transitions (e.g., updating a pet's status to 'Sold' when a sale is created), and business rules.
*   **Data Access Layer:** Uses SQLAlchemy (Flask-SQLAlchemy) as the ORM to interact with the PostgreSQL database.

### 2.1 Architecture Diagram (Conceptual)
```text
[ Client (Web/Mobile) ] 
       │ (HTTPS / JSON)
       ▼
[ Flask Application ]
  ├─ API Routers / Controllers
  ├─ Business Services
  └─ SQLAlchemy ORM
       │ (psycopg2)
       ▼
[ PostgreSQL Database ]
```

## 3. Data Model
The relational database is designed with data integrity in mind, utilizing foreign keys and check constraints.

### 3.1 `species`
Lookup table for categorizing pets.
*   `id`: Primary Key (Integer, Auto-incremented)
*   `name`: String, Unique (e.g., Dog, Cat, Bird)

### 3.2 `pets`
Core inventory table.
*   `id`: Primary Key (Integer, Auto-incremented)
*   `species_id`: Foreign Key referencing `species(id)`
*   `name`: String
*   `breed`: String
*   `age_months`: Integer (>= 0)
*   `price`: Numeric (Monetary value in USD, >= 0)
*   `status`: Enum/String ('Available', 'Sold', 'Pending')

### 3.3 `customers`
Stores client information.
*   `id`: Primary Key (Integer, Auto-incremented)
*   `first_name`: String
*   `last_name`: String
*   `email`: String, Unique
*   `phone`: String (Standard 10-digit format, e.g., 206-555-0199)

### 3.4 `sales`
Records transactions.
*   `id`: Primary Key (Integer, Auto-incremented)
*   `pet_id`: Foreign Key referencing `pets(id)`, Unique (a pet can only be sold once)
*   `customer_id`: Foreign Key referencing `customers(id)`
*   `sale_date`: Timestamp with Time Zone (Defaults to current time, PT)
*   `sale_price`: Numeric (Final transaction price in USD)

## 4. REST API Design
All endpoints prefixed with `/api/v1/`. Data is exchanged in JSON format.

### 4.1 Pets Endpoints
*   **`GET /pets`**
    *   *Description:* Retrieve a list of pets. Supports query parameters for filtering (`?status=Available`, `?species=Dog`).
    *   *Response:* `200 OK` (Array of pet objects)
*   **`POST /pets`**
    *   *Description:* Add a new pet to the inventory.
    *   *Payload:* `{ "species_id": 1, "name": "Buddy", "breed": "Labrador", "age_months": 8, "price": 850.00 }`
    *   *Response:* `201 Created`
*   **`GET /pets/{id}`**
    *   *Description:* Get details of a specific pet.
    *   *Response:* `200 OK` or `404 Not Found`
*   **`PUT /pets/{id}`**
    *   *Description:* Update pet details (e.g., price changes, correcting breed).
*   **`DELETE /pets/{id}`**
    *   *Description:* Remove a pet (only permitted if not linked to a sale).

### 4.2 Customers Endpoints
*   **`GET /customers`**
    *   *Description:* List all customers.
*   **`POST /customers`**
    *   *Description:* Register a new customer.
    *   *Payload:* `{ "first_name": "Jane", "last_name": "Doe", "email": "jane.doe@example.com", "phone": "425-555-0122" }`
    *   *Response:* `201 Created`

### 4.3 Sales Endpoints
*   **`POST /sales`**
    *   *Description:* Process a pet adoption/sale. This endpoint handles the transaction: recording the sale and automatically updating the pet's status to 'Sold'.
    *   *Payload:* `{ "pet_id": 1, "customer_id": 5, "sale_price": 800.00 }`
    *   *Response:* `201 Created` or `400 Bad Request` (e.g., if pet is already sold)
*   **`GET /sales`**
    *   *Description:* View transaction history.

## 5. Error Handling
The API returns standard HTTP status codes:
*   `200 OK` / `201 Created` for success.
*   `400 Bad Request` for validation errors (e.g., negative price).
*   `404 Not Found` for non-existent resources.
*   `409 Conflict` for constraint violations (e.g., duplicate email).
*   `500 Internal Server Error` for unexpected server issues.

Error responses will include a standard JSON payload:
```json
{
  "error": "Bad Request",
  "message": "sale_price cannot be negative."
}
```