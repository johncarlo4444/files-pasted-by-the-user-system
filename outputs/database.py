"""MySQL connection and schema initialization helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from config import DB_CONFIG


def get_connection(*, select_database: bool = True) -> Any:
    """Open a MySQL connection using the configured local server settings."""
    try:
        import mysql.connector
    except ImportError as exc:
        raise RuntimeError(
            "MySQL driver is missing. Install it with: "
            "python -m pip install mysql-connector-python"
        ) from exc

    options: dict[str, Any] = {
        "host": DB_CONFIG.host,
        "port": DB_CONFIG.port,
        "user": DB_CONFIG.user,
        "password": DB_CONFIG.password,
        "connection_timeout": DB_CONFIG.connection_timeout,
        "autocommit": True,
    }
    if select_database:
        options["database"] = DB_CONFIG.database
    return mysql.connector.connect(**options)


def verify_connection(*, select_database: bool = False) -> dict[str, str]:
    """Check that MySQL accepts a connection and return server details.

    By default this checks the server itself, so it also works before the
    application database has been created. Pass ``select_database=True`` to
    verify the configured database specifically.
    """
    connection = get_connection(select_database=select_database)
    try:
        cursor = connection.cursor()
        try:
            cursor.execute("SELECT VERSION(), DATABASE()")
            version, database_name = cursor.fetchone()
        finally:
            cursor.close()
        return {"server_version": str(version), "database": database_name or ""}
    finally:
        connection.close()


def _statements_from_sql(script: str) -> list[str]:
    """Split the simple DDL/seed script into statements.

    The schema contains no stored routines or semicolons inside string values,
    so splitting on statement terminators is sufficient and works across
    mysql-connector-python versions (including versions without multi=True).
    """
    return [statement.strip() for statement in script.split(";") if statement.strip()]


def initialize_database(schema_path: str | Path | None = None) -> None:
    """Create or upgrade the database, then add default staff and menu seed data."""
    path = Path(schema_path) if schema_path else Path(__file__).with_name("schema.sql")
    script = path.read_text(encoding="utf-8")
    statements = _statements_from_sql(script)
    setup_statements = [
        statement for statement in statements
        if statement.upper().startswith(("CREATE ", "USE "))
    ]
    seed_statements = [
        statement for statement in statements
        if statement.upper().startswith("INSERT ")
    ]

    # Build tables first, then repair older schemas and add the unique product
    # key before replaying seeds. This prevents an old table without that key
    # from collecting another copy of each menu item on every setup run.
    connection = get_connection(select_database=False)
    try:
        cursor = connection.cursor()
        try:
            for statement in setup_statements:
                cursor.execute(statement)
        finally:
            cursor.close()
    finally:
        connection.close()
    ensure_runtime_schema(normalize_categories=False)

    connection = get_connection(select_database=True)
    try:
        cursor = connection.cursor()
        try:
            for statement in seed_statements:
                cursor.execute(statement)
        finally:
            cursor.close()
    finally:
        connection.close()
    normalize_menu_categories()


def ensure_runtime_schema(*, normalize_categories: bool = True) -> None:
    """Apply additive upgrades needed by the current app to an existing DB.

    This intentionally does not replay menu inserts. It lets older installs
    gain recipe tracking and payment details, consolidates duplicate product
    rows while preserving their order history, and enforces menu uniqueness.
    Run ``initialize_database`` for a brand-new database.
    """
    connection = get_connection(select_database=True)
    try:
        cursor = connection.cursor()
        try:
            cursor.execute(
                "CREATE TABLE IF NOT EXISTS app_settings ("
                "setting_key VARCHAR(100) PRIMARY KEY, setting_value TEXT NOT NULL, "
                "updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP) ENGINE=InnoDB"
            )
            cursor.execute(
                "CREATE TABLE IF NOT EXISTS product_inventory ("
                "product_id INT NOT NULL, inventory_id INT NOT NULL, "
                "quantity_required INT NOT NULL DEFAULT 1, "
                "PRIMARY KEY (product_id, inventory_id), "
                "CONSTRAINT fk_product_inventory_product FOREIGN KEY (product_id) "
                "REFERENCES products(product_id) ON DELETE CASCADE, "
                "CONSTRAINT fk_product_inventory_item FOREIGN KEY (inventory_id) "
                "REFERENCES inventory(inventory_id) ON DELETE CASCADE) ENGINE=InnoDB"
            )

            # Older installations may have created `products` before the
            # category/name unique key existed. Repeated schema seeding then
            # inserted duplicate menu rows. Keep the newest row (highest ID),
            # fold recipe links and order history into it, then enforce the key.
            cursor.execute(
                "SELECT category_id, product_name FROM products "
                "GROUP BY category_id, product_name HAVING COUNT(*) > 1"
            )
            duplicate_groups = cursor.fetchall()
            for category_id, product_name in duplicate_groups:
                cursor.execute(
                    "SELECT product_id, image_path FROM products "
                    "WHERE category_id=%s AND product_name=%s ORDER BY product_id DESC",
                    (category_id, product_name),
                )
                duplicate_rows = cursor.fetchall()
                if len(duplicate_rows) < 2:
                    continue
                keeper_id = duplicate_rows[0][0]
                keeper_image = duplicate_rows[0][1]
                if not keeper_image:
                    keeper_image = next((row[1] for row in duplicate_rows[1:] if row[1]), None)
                    if keeper_image:
                        cursor.execute(
                            "UPDATE products SET image_path=%s WHERE product_id=%s",
                            (keeper_image, keeper_id),
                        )
                for duplicate_id, _image_path in duplicate_rows[1:]:
                    cursor.execute(
                        "INSERT IGNORE INTO product_inventory "
                        "(product_id, inventory_id, quantity_required) "
                        "SELECT %s, inventory_id, quantity_required FROM product_inventory "
                        "WHERE product_id=%s",
                        (keeper_id, duplicate_id),
                    )
                    cursor.execute(
                        "UPDATE order_items SET product_id=%s WHERE product_id=%s",
                        (keeper_id, duplicate_id),
                    )
                    cursor.execute("DELETE FROM products WHERE product_id=%s", (duplicate_id,))

            cursor.execute(
                "SELECT INDEX_NAME, COLUMN_NAME, NON_UNIQUE, SEQ_IN_INDEX "
                "FROM INFORMATION_SCHEMA.STATISTICS WHERE TABLE_SCHEMA=%s "
                "AND TABLE_NAME='products' ORDER BY INDEX_NAME, SEQ_IN_INDEX",
                (DB_CONFIG.database,),
            )
            indexes: dict[str, list[tuple[int, str, int]]] = {}
            for index_name, column_name, non_unique, sequence in cursor.fetchall():
                indexes.setdefault(index_name, []).append((sequence, column_name, non_unique))
            has_product_identity_key = any(
                [column for _sequence, column, _non_unique in sorted(columns)]
                == ["category_id", "product_name"]
                and all(non_unique == 0 for _sequence, _column, non_unique in columns)
                for columns in indexes.values()
            )
            if not has_product_identity_key:
                cursor.execute(
                    "ALTER TABLE products ADD UNIQUE KEY uq_products_category_name "
                    "(category_id, product_name)"
                )

            cursor.execute(
                "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS "
                "WHERE TABLE_SCHEMA=%s AND TABLE_NAME='payments'",
                (DB_CONFIG.database,),
            )
            payment_columns = {row[0] for row in cursor.fetchall()}
            additions = (
                ("amount_tendered", "DECIMAL(10,2) NOT NULL DEFAULT 0.00"),
                ("change_returned", "DECIMAL(10,2) NOT NULL DEFAULT 0.00"),
                ("cashier_user_id", "INT DEFAULT NULL"),
            )
            for column, definition in additions:
                if column not in payment_columns:
                    cursor.execute(f"ALTER TABLE payments ADD COLUMN {column} {definition}")

            cursor.execute(
                "SELECT 1 FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE "
                "WHERE TABLE_SCHEMA=%s AND TABLE_NAME='payments' "
                "AND COLUMN_NAME='cashier_user_id' AND REFERENCED_TABLE_NAME='users' LIMIT 1",
                (DB_CONFIG.database,),
            )
            if cursor.fetchone() is None:
                cursor.execute(
                    "ALTER TABLE payments ADD CONSTRAINT fk_payments_cashier "
                    "FOREIGN KEY (cashier_user_id) REFERENCES users(user_id) ON DELETE SET NULL"
                )

            inventory_seed = (
                ("Beef Patties", 200, "pcs", 25), ("Ribeye Steaks", 50, "pcs", 10),
                ("Pizza Dough", 100, "pcs", 15), ("Mozzarella", 80, "packs", 12),
                ("Fettuccine", 100, "packs", 15), ("Chicken Pieces", 150, "pcs", 25),
                ("Taco Beef", 100, "packs", 15), ("Ramen Noodles", 100, "packs", 15),
                ("Sushi Rice", 100, "packs", 15), ("Pad Thai Noodles", 100, "packs", 15),
                ("Potatoes", 200, "packs", 25), ("Gelato Servings", 100, "pcs", 15),
                ("Matcha Servings", 100, "pcs", 15),
            )
            for item_name, stock, unit, minimum in inventory_seed:
                cursor.execute("SELECT inventory_id FROM inventory WHERE item_name=%s LIMIT 1", (item_name,))
                if cursor.fetchone() is None:
                    cursor.execute(
                        "INSERT INTO inventory (item_name, stock_quantity, unit, min_stock_level, status) "
                        "VALUES (%s, %s, %s, %s, 'Available')",
                        (item_name, stock, unit, minimum),
                    )

            recipe_seed = (
                ("Classic Double Cheeseburger", "Beef Patties", 2),
                ("Garlic Butter Ribeye Steak", "Ribeye Steaks", 1),
                ("Neapolitan Margherita Pizza", "Pizza Dough", 1),
                ("Neapolitan Margherita Pizza", "Mozzarella", 1),
                ("Creamy Fettuccine Alfredo", "Fettuccine", 1),
                ("Crispy Golden Fried Chicken", "Chicken Pieces", 1),
                ("Mexican Birria Street Tacos", "Taco Beef", 1),
                ("Tonkotsu Pork Ramen", "Ramen Noodles", 1),
                ("Fresh Salmon & Tuna Sushi Roll", "Sushi Rice", 1),
                ("Thai Pad Thai Noodles", "Pad Thai Noodles", 1),
                ("Belgian Crispy Golden Fries", "Potatoes", 1),
                ("Italian Chocolate Gelato", "Gelato Servings", 1),
                ("Iced Matcha Green Tea Latte", "Matcha Servings", 1),
            )
            cursor.execute("SELECT DISTINCT product_id FROM product_inventory")
            products_with_existing_recipes = {row[0] for row in cursor.fetchall()}
            for product_name, ingredient_name, quantity in recipe_seed:
                cursor.execute("SELECT product_id FROM products WHERE product_name=%s", (product_name,))
                product_ids = [row[0] for row in cursor.fetchall()]
                cursor.execute("SELECT inventory_id FROM inventory WHERE item_name=%s LIMIT 1", (ingredient_name,))
                inventory_row = cursor.fetchone()
                if not inventory_row:
                    continue
                for product_id in product_ids:
                    # Preserve any recipes already configured by the store.
                    # For products with no existing recipe, insert every default
                    # ingredient (including multiple ingredients for one product).
                    if product_id not in products_with_existing_recipes:
                        cursor.execute(
                            "INSERT INTO product_inventory (product_id, inventory_id, quantity_required) "
                            "VALUES (%s, %s, %s)",
                            (product_id, inventory_row[0], quantity),
                        )
        finally:
            cursor.close()
    finally:
        connection.close()
    if normalize_categories:
        normalize_menu_categories()


def normalize_menu_categories() -> None:
    """Keep the menu taxonomy consistent on existing and newly seeded databases."""
    connection = get_connection(select_database=True)
    try:
        cursor = connection.cursor()
        try:
            # Older versions grouped rice meals under Fried Chicken & Tacos.
            cursor.execute(
                "UPDATE categories SET category_name=%s WHERE category_name=%s",
                ("Chicken & Tacos", "Fried Chicken & Tacos"),
            )

            category_names = (
                "Burgers & Steaks",
                "Pizza & Pasta",
                "Chicken & Tacos",
                "Asian Classics",
                "Sides, Desserts & Drinks",
                "Combos",
                "Rice Meals",
            )
            for category_name in category_names:
                cursor.execute(
                    "INSERT INTO categories (category_name) VALUES (%s) "
                    "ON DUPLICATE KEY UPDATE category_name=VALUES(category_name)",
                    (category_name,),
                )

            moves = {
                "Burgers & Steaks": ("Chicken Burger Sandwich",),
                "Chicken & Tacos": (
                    "BBQ Chicken Wings",
                    "Chicken Quesadilla",
                    "Chicken Parmesan",
                    "Classic Fried Chicken",
                    "Crispy Golden Fried Chicken",
                    "Lemon Herb Chicken",
                    "Mexican Birria Street Tacos",
                    "Spicy Fried Chicken",
                ),
                "Asian Classics": ("Honey Garlic Chicken",),
                "Sides, Desserts & Drinks": (
                    "Bubble Tea",
                    "Coca-Cola",
                    "Iced Coffee",
                    "Iced Matcha Latte",
                    "Iced Tea",
                    "Lemonade",
                    "Mango Shake",
                    "Strawberry Lemonade",
                ),
                "Rice Meals": (
                    "Beef & Broccoli Rice",
                    "Butter Chicken Rice",
                    "Chicken Teriyaki Rice Bowl",
                    "Egg Fried Rice",
                    "Garlic Butter Shrimp Rice",
                    "Pork Adobo Rice",
                    "Pork Katsu Rice",
                    "Shrimp Fried Rice",
                ),
            }
            for category_name, product_names in moves.items():
                cursor.execute(
                    "SELECT category_id FROM categories WHERE category_name=%s",
                    (category_name,),
                )
                row = cursor.fetchone()
                if row is None:
                    raise RuntimeError(f"Required menu category is missing: {category_name}")
                category_id = int(row[0])
                for product_name in product_names:
                    cursor.execute(
                        "UPDATE products SET category_id=%s WHERE product_name=%s",
                        (category_id, product_name),
                    )
        finally:
            cursor.close()
    finally:
        connection.close()
    ensure_asian_menu()
    ensure_american_menu()


def ensure_asian_menu() -> None:
    """Add the supplied Asian dishes and bundle their photos with the app."""
    products = (
        (
            "Asian Classics",
            "Chinese Dim Sum",
            "Assorted steamed dumplings and buns served with a savory dipping sauce.",
            "199.00",
            "assets/menu/chinese-dim-sum.jpg",
        ),
        (
            "Rice Meals",
            "Filipino Chicken Adobo",
            "Chicken braised with soy sauce, vinegar, garlic, and bay leaves, served with rice.",
            "199.00",
            "assets/menu/filipino-chicken-adobo.jpg",
        ),
        (
            "Rice Meals",
            "Indian Chicken Biryani",
            "Fragrant spiced basmati rice layered with chicken, herbs, and warm spices.",
            "249.00",
            "assets/menu/indian-chicken-biryani.jpg",
        ),
        (
            "Rice Meals",
            "Indonesian Nasi Goreng",
            "Indonesian fried rice with chicken, vegetables, egg, and sweet soy sauce.",
            "229.00",
            "assets/menu/indonesian-nasi-goreng.jpg",
        ),
        (
            "Rice Meals",
            "Korean Bibimbap",
            "Rice bowl topped with seasoned vegetables, egg, and gochujang sauce.",
            "249.00",
            "assets/menu/korean-bibimbap.jpg",
        ),
        (
            "Asian Classics",
            "Peking Duck",
            "Crispy roasted duck served with pancakes, scallions, cucumber, and hoisin sauce.",
            "599.00",
            "assets/menu/peking-duck.jpg",
        ),
        (
            "Asian Classics",
            "Vietnamese Pho",
            "Rice noodle soup with aromatic broth, fresh herbs, and tender beef.",
            "249.00",
            "assets/menu/vietnamese-pho.jpg",
        ),
    )
    connection = get_connection(select_database=True)
    try:
        cursor = connection.cursor()
        try:
            for category_name, product_name, description, price, image_path in products:
                cursor.execute(
                    "SELECT category_id FROM categories WHERE category_name=%s",
                    (category_name,),
                )
                category = cursor.fetchone()
                if category is None:
                    raise RuntimeError(f"Required menu category is missing: {category_name}")
                cursor.execute(
                    "INSERT INTO products "
                    "(category_id, product_name, description, price, image_path) "
                    "VALUES (%s, %s, %s, %s, %s) "
                    "ON DUPLICATE KEY UPDATE image_path=VALUES(image_path)",
                    (category[0], product_name, description, price, image_path),
                )
        finally:
            cursor.close()
    finally:
        connection.close()


def ensure_american_menu() -> None:
    """Add American Classics products and their bundled menu photos."""
    products = (
        (
            "BBQ Pork Ribs",
            "Tender pork ribs coated in smoky barbecue sauce.",
            "399.00",
            "assets/menu/bbq-pork-ribs.jpg",
        ),
        (
            "Buffalo Chicken Wings",
            "Crispy chicken wings tossed in tangy Buffalo sauce.",
            "229.00",
            "assets/menu/buffalo-chicken-wings.jpg",
        ),
        (
            "Buttermilk Pancakes",
            "Fluffy buttermilk pancakes served with butter and maple syrup.",
            "159.00",
            "assets/menu/buttermilk-pancakes.jpg",
        ),
        (
            "Chocolate Chip Cookies",
            "Fresh-baked cookies filled with chocolate chips.",
            "59.00",
            "assets/menu/chocolate-chip-cookies.jpg",
        ),
        (
            "Classic American Hot Dog",
            "Grilled hot dog in a soft bun with classic toppings.",
            "129.00",
            "assets/menu/classic-american-hot-dog.jpg",
        ),
        (
            "Macaroni and Cheese",
            "Tender macaroni folded into a creamy cheese sauce.",
            "189.00",
            "assets/menu/macaroni-and-cheese.jpg",
        ),
        (
            "New England Clam Chowder",
            "Creamy chowder with clams and potatoes.",
            "249.00",
            "assets/menu/new-england-clam-chowder.jpg",
        ),
        (
            "Southern Fried Chicken",
            "Crispy Southern-style chicken seasoned and fried until golden.",
            "199.00",
            "assets/menu/southern-fried-chicken.jpg",
        ),
    )

    connection = get_connection(select_database=True)
    try:
        cursor = connection.cursor()
        try:
            cursor.execute(
                "INSERT INTO categories (category_name) VALUES (%s) "
                "ON DUPLICATE KEY UPDATE category_name=VALUES(category_name)",
                ("American Classics",),
            )
            cursor.execute(
                "SELECT category_id FROM categories WHERE category_name=%s",
                ("American Classics",),
            )
            category = cursor.fetchone()
            if category is None:
                raise RuntimeError("Required menu category is missing: American Classics")

            for product_name, description, price, image_path in products:
                cursor.execute(
                    "INSERT INTO products "
                    "(category_id, product_name, description, price, image_path) "
                    "VALUES (%s, %s, %s, %s, %s) "
                    "ON DUPLICATE KEY UPDATE image_path=VALUES(image_path)",
                    (category[0], product_name, description, price, image_path),
                )
        finally:
            cursor.close()
    finally:
        connection.close()


if __name__ == "__main__":
    details = verify_connection()
    print(
        f"Connected to MySQL {details['server_version']} at "
        f"{DB_CONFIG.host}:{DB_CONFIG.port}."
    )
    initialize_database()
    database_details = verify_connection(select_database=True)
    print(f"Initialized database '{DB_CONFIG.database}' and seeded the menu.")
    print(f"Verified connection to database '{database_details['database']}'.")




