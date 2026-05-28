CREATE TABLE IF NOT EXISTS airports (
  id INT PRIMARY KEY,
  iata TEXT,
  name TEXT,
  city TEXT,
  country TEXT
  );

CREATE TABLE IF NOT EXISTS flights (
  id INT PRIMARY KEY,
  airline VARCHAR(10),
  flight_number INT,
  departure_airport VARCHAR(5),
  arrival_airport VARCHAR(5),
  departure_time TIMESTAMP,
  arrival_time TIMESTAMP,
  departure_gate VARCHAR(10),
  arrival_gate VARCHAR(10)
);
