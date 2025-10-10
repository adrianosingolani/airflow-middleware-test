CREATE TABLE products (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100),
    quantity INT
);
INSERT INTO products (name, quantity) VALUES ('Produto A', 10), ('Produto B', 25), ('Produto C', 7);