CREATE DATABASE IF NOT EXISTS fastfood_db
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;
USE fastfood_db;

-- Default login: admin / admin123. The value is a PBKDF2-SHA256 hash using
-- 600,000 iterations, stored as algorithm$iterations$base64-salt$base64-hash.
CREATE TABLE IF NOT EXISTS users (
    user_id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role ENUM('Admin', 'Cashier', 'Kitchen Staff') NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS app_settings (
    setting_key VARCHAR(100) PRIMARY KEY,
    setting_value TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS categories (
    category_id INT AUTO_INCREMENT PRIMARY KEY,
    category_name VARCHAR(100) NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS products (
    product_id INT AUTO_INCREMENT PRIMARY KEY,
    category_id INT NOT NULL,
    product_name VARCHAR(100) NOT NULL,
    description TEXT,
    price DECIMAL(10,2) NOT NULL,
    image_path VARCHAR(255) DEFAULT NULL,
    is_available BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_products_category_name (category_id, product_name),
    CONSTRAINT fk_products_category
        FOREIGN KEY (category_id) REFERENCES categories(category_id)
        ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS inventory (
    inventory_id INT AUTO_INCREMENT PRIMARY KEY,
    item_name VARCHAR(100) NOT NULL UNIQUE,
    stock_quantity INT NOT NULL DEFAULT 0,
    unit VARCHAR(20) NOT NULL DEFAULT 'pcs',
    min_stock_level INT NOT NULL DEFAULT 10,
    status ENUM('Available', 'Low Stock', 'Out of Stock') DEFAULT 'Available',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- Recipe links determine which ingredients are deducted when an order is paid.
CREATE TABLE IF NOT EXISTS product_inventory (
    product_id INT NOT NULL,
    inventory_id INT NOT NULL,
    quantity_required INT NOT NULL DEFAULT 1,
    PRIMARY KEY (product_id, inventory_id),
    CONSTRAINT fk_product_inventory_product
        FOREIGN KEY (product_id) REFERENCES products(product_id) ON DELETE CASCADE,
    CONSTRAINT fk_product_inventory_item
        FOREIGN KEY (inventory_id) REFERENCES inventory(inventory_id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS orders (
    order_id INT AUTO_INCREMENT PRIMARY KEY,
    order_code VARCHAR(10) NOT NULL UNIQUE,
    order_type ENUM('Dine-In', 'Take-Out') NOT NULL,
    total_amount DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    payment_status ENUM('Unpaid', 'Paid', 'Cancelled') DEFAULT 'Unpaid',
    order_status ENUM(
        'Pending Payment', 'Paid', 'Preparing', 'Ready', 'Completed', 'Cancelled'
    ) DEFAULT 'Pending Payment',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS order_items (
    order_item_id INT AUTO_INCREMENT PRIMARY KEY,
    order_id INT NOT NULL,
    product_id INT NOT NULL,
    quantity INT NOT NULL DEFAULT 1,
    customization TEXT DEFAULT NULL,
    special_instructions TEXT DEFAULT NULL,
    subtotal DECIMAL(10,2) NOT NULL,
    CONSTRAINT fk_order_items_order
        FOREIGN KEY (order_id) REFERENCES orders(order_id) ON DELETE CASCADE,
    CONSTRAINT fk_order_items_product
        FOREIGN KEY (product_id) REFERENCES products(product_id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS payments (
    payment_id INT AUTO_INCREMENT PRIMARY KEY,
    order_id INT NOT NULL,
    payment_method ENUM('Cash', 'GCash', 'Card') NOT NULL,
    amount_paid DECIMAL(10,2) NOT NULL,
    amount_tendered DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    change_returned DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    payment_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    payment_status ENUM('Paid', 'Cancelled') DEFAULT 'Paid',
    cashier_user_id INT DEFAULT NULL,
    CONSTRAINT fk_payments_order
        FOREIGN KEY (order_id) REFERENCES orders(order_id) ON DELETE CASCADE,
    CONSTRAINT fk_payments_cashier
        FOREIGN KEY (cashier_user_id) REFERENCES users(user_id) ON DELETE SET NULL
) ENGINE=InnoDB;

INSERT INTO users (username, password_hash, role)
VALUES (
    'admin',
    'pbkdf2_sha256$600000$4Iq8yaAVJedcRy/7Qaqd8A==$zAzQqNq5xd05q09mdIu63hM1zTsaqOKmnQuYGzVjNmA=',
    'Admin'
)
ON DUPLICATE KEY UPDATE username = VALUES(username);

INSERT INTO categories (category_id, category_name) VALUES
    (1, 'Burgers & Steaks'),
    (2, 'Pizza & Pasta'),
    (3, 'Chicken & Tacos'),
    (4, 'Asian Classics'),
    (5, 'Sides, Desserts & Drinks'),
    (6, 'Combos'),
    (7, 'Rice Meals')
ON DUPLICATE KEY UPDATE category_name = VALUES(category_name);

INSERT INTO products (category_id, product_name, description, price, is_available) VALUES
    (1, 'Classic Double Cheeseburger', 'Two juicy beef patties, melted cheddar, lettuce, tomato, pickles, and house sauce.', 249.00, TRUE),
    (1, 'Garlic Butter Ribeye Steak', 'Grilled premium ribeye steak topped with herb garlic butter and served with vegetables.', 899.00, TRUE),
    (2, 'Neapolitan Margherita Pizza', 'Wood-fired sourdough pizza with tomato, fresh mozzarella, and basil.', 499.00, TRUE),
    (2, 'Creamy Fettuccine Alfredo', 'Fresh fettuccine pasta tossed in parmesan butter and cream sauce.', 320.00, TRUE),
    (3, 'Crispy Golden Fried Chicken', 'Crispy seasoned chicken pieces served with savory dipping gravy.', 199.00, TRUE),
    (3, 'Mexican Birria Street Tacos', 'Slow-cooked shredded beef in warm corn tortillas with onions, cilantro, and consommé.', 280.00, TRUE),
    (4, 'Tonkotsu Pork Ramen', 'Rich pork broth with noodles, chashu pork belly, bamboo shoots, and soft egg.', 395.00, TRUE),
    (4, 'Fresh Salmon & Tuna Sushi Roll', 'Maki roll with salmon, tuna, avocado, and seasoned sushi rice.', 450.00, TRUE),
    (4, 'Thai Pad Thai Noodles', 'Stir-fried rice noodles with tamarind sauce, crushed peanuts, sprouts, and lime.', 295.00, TRUE),
    (5, 'Belgian Crispy Golden Fries', 'Crispy potato fries served with garlic mayonnaise dipping sauce.', 120.00, TRUE),
    (5, 'Italian Chocolate Gelato', 'Rich, velvety dark chocolate gelato.', 150.00, TRUE),
    (5, 'Iced Matcha Green Tea Latte', 'Japanese green tea whisked with cold milk and served over ice.', 165.00, TRUE)
ON DUPLICATE KEY UPDATE product_name = VALUES(product_name);

INSERT INTO inventory (item_name, stock_quantity, unit, min_stock_level, status) VALUES
    ('Beef Patties', 200, 'pcs', 25, 'Available'),
    ('Ribeye Steaks', 50, 'pcs', 10, 'Available'),
    ('Pizza Dough', 100, 'pcs', 15, 'Available'),
    ('Mozzarella', 80, 'packs', 12, 'Available'),
    ('Fettuccine', 100, 'packs', 15, 'Available'),
    ('Chicken Pieces', 150, 'pcs', 25, 'Available'),
    ('Taco Beef', 100, 'packs', 15, 'Available'),
    ('Ramen Noodles', 100, 'packs', 15, 'Available'),
    ('Sushi Rice', 100, 'packs', 15, 'Available'),
    ('Pad Thai Noodles', 100, 'packs', 15, 'Available'),
    ('Potatoes', 200, 'packs', 25, 'Available'),
    ('Gelato Servings', 100, 'pcs', 15, 'Available'),
    ('Matcha Servings', 100, 'pcs', 15, 'Available')
ON DUPLICATE KEY UPDATE item_name = VALUES(item_name);

INSERT INTO product_inventory (product_id, inventory_id, quantity_required)
SELECT p.product_id, i.inventory_id,
       CASE WHEN p.product_name = 'Classic Double Cheeseburger' THEN 2 ELSE 1 END
FROM products p JOIN inventory i ON
    (p.product_name = 'Classic Double Cheeseburger' AND i.item_name = 'Beef Patties') OR
    (p.product_name = 'Garlic Butter Ribeye Steak' AND i.item_name = 'Ribeye Steaks') OR
    (p.product_name = 'Neapolitan Margherita Pizza' AND i.item_name = 'Pizza Dough') OR
    (p.product_name = 'Neapolitan Margherita Pizza' AND i.item_name = 'Mozzarella') OR
    (p.product_name = 'Creamy Fettuccine Alfredo' AND i.item_name = 'Fettuccine') OR
    (p.product_name = 'Crispy Golden Fried Chicken' AND i.item_name = 'Chicken Pieces') OR
    (p.product_name = 'Mexican Birria Street Tacos' AND i.item_name = 'Taco Beef') OR
    (p.product_name = 'Tonkotsu Pork Ramen' AND i.item_name = 'Ramen Noodles') OR
    (p.product_name = 'Fresh Salmon & Tuna Sushi Roll' AND i.item_name = 'Sushi Rice') OR
    (p.product_name = 'Thai Pad Thai Noodles' AND i.item_name = 'Pad Thai Noodles') OR
    (p.product_name = 'Belgian Crispy Golden Fries' AND i.item_name = 'Potatoes') OR
    (p.product_name = 'Italian Chocolate Gelato' AND i.item_name = 'Gelato Servings') OR
    (p.product_name = 'Iced Matcha Green Tea Latte' AND i.item_name = 'Matcha Servings')
ON DUPLICATE KEY UPDATE quantity_required = VALUES(quantity_required);

