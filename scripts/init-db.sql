-- E-commerce Comparison Database Initialization

-- Create schemas for each service
CREATE SCHEMA IF NOT EXISTS catalog;
CREATE SCHEMA IF NOT EXISTS cart;
CREATE SCHEMA IF NOT EXISTS orders;
CREATE SCHEMA IF NOT EXISTS payment;
CREATE SCHEMA IF NOT EXISTS inventory;

-- Catalog Service Tables
CREATE TABLE IF NOT EXISTS catalog.products (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    price DECIMAL(10, 2) NOT NULL,
    image_url VARCHAR(500),
    category VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Inventory Service Tables
CREATE TABLE IF NOT EXISTS inventory.stock (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id UUID NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 0,
    reserved INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_stock_product_id ON inventory.stock(product_id);

-- Cart Service Tables
CREATE TABLE IF NOT EXISTS cart.carts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS cart.cart_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cart_id UUID NOT NULL REFERENCES cart.carts(id) ON DELETE CASCADE,
    product_id UUID NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 1,
    price DECIMAL(10, 2) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_cart_items_cart_id ON cart.cart_items(cart_id);
CREATE INDEX IF NOT EXISTS idx_carts_user_id ON cart.carts(user_id);

-- Order Service Tables
CREATE TABLE IF NOT EXISTS orders.orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(255) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    total_amount DECIMAL(10, 2) NOT NULL,
    communication_mode VARCHAR(20) NOT NULL DEFAULT 'sync',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS orders.order_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id UUID NOT NULL REFERENCES orders.orders(id) ON DELETE CASCADE,
    product_id UUID NOT NULL,
    quantity INTEGER NOT NULL,
    price DECIMAL(10, 2) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_order_items_order_id ON orders.order_items(order_id);
CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders.orders(user_id);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders.orders(status);

-- Order Saga State (for async processing)
CREATE TABLE IF NOT EXISTS orders.saga_state (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id UUID NOT NULL REFERENCES orders.orders(id),
    current_step VARCHAR(50) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    payment_status VARCHAR(50),
    inventory_status VARCHAR(50),
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_saga_state_order_id ON orders.saga_state(order_id);

-- Payment Service Tables
CREATE TABLE IF NOT EXISTS payment.payments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id UUID NOT NULL,
    amount DECIMAL(10, 2) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    transaction_id VARCHAR(255),
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_payments_order_id ON payment.payments(order_id);
CREATE INDEX IF NOT EXISTS idx_payments_status ON payment.payments(status);

-- Idempotency Keys Table
CREATE TABLE IF NOT EXISTS orders.idempotency_keys (
    key VARCHAR(255) PRIMARY KEY,
    response JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Seed Data: Sample Products
INSERT INTO catalog.products (id, name, description, price, image_url, category) VALUES
    ('a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11', 'Laptop Pro 15', 'High-performance laptop with 16GB RAM and 512GB SSD', 1299.99, 'https://images.unsplash.com/photo-1496181133206-80ce9b88a853?w=300&h=200&fit=crop', 'Electronics'),
    ('a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a12', 'Wireless Mouse', 'Ergonomic wireless mouse with precision tracking', 49.99, 'https://images.unsplash.com/photo-1527864550417-7fd91fc51a46?w=300&h=200&fit=crop', 'Electronics'),
    ('a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a13', 'USB-C Hub', '7-in-1 USB-C hub with HDMI and card reader', 79.99, 'https://images.unsplash.com/photo-1625723044792-44de16ccb4e9?w=300&h=200&fit=crop', 'Electronics'),
    ('a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a14', 'Mechanical Keyboard', 'RGB mechanical keyboard with Cherry MX switches', 149.99, 'https://images.unsplash.com/photo-1595225476474-87563907a212?w=300&h=200&fit=crop', 'Electronics'),
    ('a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a15', 'Monitor 27"', '4K IPS monitor with HDR support', 449.99, 'https://images.unsplash.com/photo-1527443224154-c4a3942d3acf?w=300&h=200&fit=crop', 'Electronics'),
    ('a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a16', 'Webcam HD', '1080p webcam with built-in microphone', 89.99, 'https://images.unsplash.com/photo-1587826080692-f439cd0b70da?w=300&h=200&fit=crop', 'Electronics'),
    ('a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a17', 'Headphones', 'Noise-canceling wireless headphones', 299.99, 'https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=300&h=200&fit=crop', 'Electronics'),
    ('a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a18', 'Desk Lamp', 'LED desk lamp with adjustable brightness', 39.99, 'https://images.unsplash.com/photo-1507473885765-e6ed057f782c?w=300&h=200&fit=crop', 'Home Office'),
    ('a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a19', 'Notebook Stand', 'Adjustable aluminum notebook stand', 59.99, 'https://images.unsplash.com/photo-1527864550417-7fd91fc51a46?w=300&h=200&fit=crop', 'Home Office'),
    ('a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a20', 'Cable Organizer', 'Magnetic cable organizer set', 19.99, 'https://images.unsplash.com/photo-1558618666-fcd25c85cd64?w=300&h=200&fit=crop', 'Home Office')
ON CONFLICT (id) DO UPDATE SET image_url = EXCLUDED.image_url;

-- Seed Data: Initial Stock
INSERT INTO inventory.stock (product_id, quantity, reserved) VALUES
    ('a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11', 100, 0),
    ('a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a12', 500, 0),
    ('a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a13', 200, 0),
    ('a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a14', 150, 0),
    ('a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a15', 75, 0),
    ('a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a16', 300, 0),
    ('a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a17', 120, 0),
    ('a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a18', 250, 0),
    ('a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a19', 180, 0),
    ('a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a20', 400, 0)
ON CONFLICT DO NOTHING;
