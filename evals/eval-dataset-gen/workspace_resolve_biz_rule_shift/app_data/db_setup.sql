-- Drop tables if they already exist (useful for testing)
DROP TABLE IF EXISTS sales;
DROP TABLE IF EXISTS customers;
DROP TABLE IF EXISTS customers_v2;
DROP TABLE IF EXISTS pets;
DROP TABLE IF EXISTS species;

-- Create species lookup table
CREATE TABLE species (
    id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE
);

-- Create pets table
CREATE TABLE pets (
    id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    species_id INT NOT NULL REFERENCES species(id) ON DELETE RESTRICT,
    name VARCHAR(100) NOT NULL,
    breed VARCHAR(100),
    age_months INT CHECK (age_months >= 0),
    price NUMERIC(8, 2) NOT NULL CHECK (price >= 0),
    status VARCHAR(20) DEFAULT 'Available' CHECK (status IN ('Available', 'Sold', 'Pending'))
);

-- Create customers table
CREATE TABLE customers (
    id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    first_name VARCHAR(50) NOT NULL,
    last_name VARCHAR(50) NOT NULL,
    email VARCHAR(150) UNIQUE NOT NULL,
    phone VARCHAR(20)
);

-- Create customers_v2 table (UPDATED on 2026-06-01 to reflect business rule change: phone number should be masked for privacy)
CREATE TABLE customers_v2 (
    id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    first_name VARCHAR(50) NOT NULL,
    last_name VARCHAR(50) NOT NULL,
    email VARCHAR(150) UNIQUE NOT NULL,
    phone VARCHAR(20)
);


-- Create sales/transactions table
CREATE TABLE sales (
    id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    pet_id INT UNIQUE NOT NULL REFERENCES pets(id) ON DELETE RESTRICT, -- UNIQUE ensures a pet is only sold once
    customer_id INT NOT NULL REFERENCES customers(id) ON DELETE RESTRICT,
    sale_date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    sale_price NUMERIC(8, 2) NOT NULL CHECK (sale_price >= 0)
);

-- Insert Species
INSERT INTO species (name) VALUES
    ('Dog'),
    ('Cat'),
    ('Bird'),
    ('Reptile');

-- Insert Pets
INSERT INTO pets (species_id, name, breed, age_months, price, status) VALUES
    (1, 'Bella', 'Golden Retriever', 3, 1200.00, 'Available'),
    (1, 'Max', 'French Bulldog', 12, 1800.00, 'Sold'),
    (2, 'Luna', 'Siamese', 4, 600.00, 'Available'),
    (2, 'Milo', 'Maine Coon', 24, 450.00, 'Sold'),
    (3, 'Charlie', 'Macaw', 36, 1500.00, 'Available'),
    (4, 'Spike', 'Bearded Dragon', 6, 150.00, 'Available');

-- Insert Customers
INSERT INTO customers (first_name, last_name, email, phone) VALUES
    ('Alice', 'Smith', 'alice.smith@example.com', '555-0101'),
    ('Bob', 'Johnson', 'bob.j@example.com', '555-0102'),
    ('Clara', 'Oswald', 'clara.o@example.com', '555-0103');

-- Insert Customers (v2)
INSERT INTO customers_v2 (first_name, last_name, email, phone) VALUES
    ('Alice', 'Smith', 'alice.smith@example.com', '***-0101'),
    ('Bob', 'Johnson', 'bob.j@example.com', '***-0102'),
    ('Clara', 'Oswald', 'clara.o@example.com', '***-0103'),
    ('David', 'Brown', 'david.b@example.com', '***-0104'),
    ('Eva', 'Green', 'eva.g@example.com', '***-0105'),
    ('Frank', 'Wilson', 'frank.w@example.com', '***-0106');

-- Insert Sales 
-- (Note: Max is pet_id 2, Milo is pet_id 4)
INSERT INTO sales (pet_id, customer_id, sale_price) VALUES
    (2, 1, 1750.00), -- Alice bought Max, negotiated down slightly
    (4, 2, 450.00);  -- Bob bought Milo at full price