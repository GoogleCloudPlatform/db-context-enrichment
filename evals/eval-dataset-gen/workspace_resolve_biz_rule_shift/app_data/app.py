"""
LAST UPDATED: 2026-06-11

Here is the single-file Flask application implementing the REST API design document. It uses `Flask-SQLAlchemy` as the ORM to interact with the PostgreSQL database.
This application is based on the design_doc.md but with `customers` table updated to `customers_v2` to reflect the business rule change regarding phone number privacy.
The API endpoints and overall structure remain consistent with the original design, ensuring that the application can handle pet inventory management, customer registration,
and sales processing while adhering to the new privacy requirements.

=
### How to run it

1. **Install Dependencies:** You will need Flask, Flask-SQLAlchemy, and the PostgreSQL database adapter (`psycopg2`).
```bash
pip install Flask Flask-SQLAlchemy psycopg2-binary

```
2.  **Configure the Database:** Update the `DATABASE_URL` string on line 11 with your actual PostgreSQL connection details (username, password, and database name).
3.  **Run the Server:**
    ```bash
    python app.py

```
"""

import os
from datetime import datetime

from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy

# Initialize Flask App
app = Flask(__name__)

# Configure Database Connection
# Defaults to a local PostgreSQL instance. Update with your actual credentials.
db_url = os.getenv(
    "DATABASE_URL", "postgresql://postgres:password@localhost:5432/petstore"
)
app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# ==========================================
# DATABASE MODELS
# ==========================================


class Species(db.Model):
    __tablename__ = "species"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False, unique=True)


class Pet(db.Model):
    __tablename__ = "pets"
    id = db.Column(db.Integer, primary_key=True)
    species_id = db.Column(
        db.Integer, db.ForeignKey("species.id", ondelete="RESTRICT"), nullable=False
    )
    name = db.Column(db.String(100), nullable=False)
    breed = db.Column(db.String(100))
    age_months = db.Column(db.Integer)
    price = db.Column(db.Numeric(8, 2), nullable=False)
    status = db.Column(db.String(20), default="Available")

    def to_dict(self):
        return {
            "id": self.id,
            "species_id": self.species_id,
            "name": self.name,
            "breed": self.breed,
            "age_months": self.age_months,
            "price": float(self.price),
            "status": self.status,
        }


class Customer(db.Model):
    __tablename__ = "customers_v2"
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    phone = db.Column(db.String(20))

    def to_dict(self):
        return {
            "id": self.id,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "email": self.email,
            "phone": self.phone,
        }


class Sale(db.Model):
    __tablename__ = "sales"
    id = db.Column(db.Integer, primary_key=True)
    pet_id = db.Column(
        db.Integer,
        db.ForeignKey("pets.id", ondelete="RESTRICT"),
        unique=True,
        nullable=False,
    )
    # Updated the foreign key reference to target customers_v2
    customer_id = db.Column(
        db.Integer,
        db.ForeignKey("customers_v2.id", ondelete="RESTRICT"),
        nullable=False,
    )
    sale_date = db.Column(db.DateTime, default=datetime.utcnow)
    sale_price = db.Column(db.Numeric(8, 2), nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "pet_id": self.pet_id,
            "customer_id": self.customer_id,
            "sale_date": self.sale_date.isoformat(),
            "sale_price": float(self.sale_price),
        }


# ==========================================
# API ENDPOINTS
# ==========================================

# --- Pets ---


@app.route("/api/v1/pets", methods=["GET"])
def get_pets():
    """Retrieve a list of pets, optionally filtering by status."""
    status_filter = request.args.get("status")
    query = Pet.query

    if status_filter:
        query = query.filter_by(status=status_filter)

    pets = query.all()
    return jsonify([pet.to_dict() for pet in pets]), 200


@app.route("/api/v1/pets", methods=["POST"])
def add_pet():
    """Add a new pet to the inventory."""
    data = request.get_json()

    try:
        new_pet = Pet(
            species_id=data["species_id"],
            name=data["name"],
            breed=data.get("breed"),
            age_months=data.get("age_months", 0),
            price=data["price"],
            status=data.get("status", "Available"),
        )
        db.session.add(new_pet)
        db.session.commit()
        return jsonify(new_pet.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Bad Request", "message": str(e)}), 400


@app.route("/api/v1/pets/<int:pet_id>", methods=["GET"])
def get_pet(pet_id):
    """Get details of a specific pet."""
    pet = Pet.query.get(pet_id)
    if not pet:
        return jsonify({"error": "Not Found", "message": "Pet not found."}), 404
    return jsonify(pet.to_dict()), 200


# --- Customers ---


@app.route("/api/v1/customers", methods=["POST"])
def add_customer():
    """Register a new customer."""
    data = request.get_json()

    try:
        new_customer = Customer(
            first_name=data["first_name"],
            last_name=data["last_name"],
            email=data["email"],
            phone=data.get("phone"),
        )
        db.session.add(new_customer)
        db.session.commit()
        return jsonify(new_customer.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Conflict or Bad Request", "message": str(e)}), 400


@app.route("/api/v1/customers", methods=["GET"])
def get_customers():
    """List all customers."""
    customers = Customer.query.all()
    return jsonify([customer.to_dict() for customer in customers]), 200


# --- Sales ---


@app.route("/api/v1/sales", methods=["POST"])
def create_sale():
    """Process a pet adoption/sale and update the pet's status."""
    data = request.get_json()

    pet_id = data.get("pet_id")
    customer_id = data.get("customer_id")
    sale_price = data.get("sale_price")

    # Basic Validation
    if not all([pet_id, customer_id, sale_price]):
        return jsonify(
            {"error": "Bad Request", "message": "Missing required fields."}
        ), 400

    pet = Pet.query.get(pet_id)
    if not pet:
        return jsonify({"error": "Not Found", "message": "Pet not found."}), 404

    if pet.status == "Sold":
        return jsonify({"error": "Conflict", "message": "Pet is already sold."}), 409

    try:
        # 1. Create the sale record
        new_sale = Sale(pet_id=pet_id, customer_id=customer_id, sale_price=sale_price)
        db.session.add(new_sale)

        # 2. Update the pet's status
        pet.status = "Sold"

        # Commit transaction (if anything fails, SQLAlchemy rolls back automatically via error handling)
        db.session.commit()
        return jsonify(new_sale.to_dict()), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Internal Error", "message": str(e)}), 500


@app.route("/api/v1/sales", methods=["GET"])
def get_sales():
    """View transaction history."""
    sales = Sale.query.all()
    return jsonify([sale.to_dict() for sale in sales]), 200


# ==========================================
# APP ENTRY POINT
# ==========================================

if __name__ == "__main__":
    # Ensure tables are created before running the app
    # (In a production environment, use a migration tool like Flask-Migrate instead)
    with app.app_context():
        db.create_all()

    app.run(debug=True, port=5000)
