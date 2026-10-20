"""Menu and category data operations."""

from __future__ import annotations

from decimal import Decimal

from database import get_connection


def list_categories() -> list[dict]:
    connection = get_connection()
    try:
        cursor = connection.cursor(dictionary=True)
        try:
            cursor.execute("SELECT category_id, category_name FROM categories ORDER BY category_name")
            return cursor.fetchall()
        finally:
            cursor.close()
    finally:
        connection.close()


def save_category(category_name: str, category_id: int | None = None) -> int:
    category_name = category_name.strip()
    if not category_name:
        raise ValueError("Category name is required.")
    connection = get_connection()
    try:
        cursor = connection.cursor()
        try:
            if category_id:
                cursor.execute(
                    "UPDATE categories SET category_name=%s WHERE category_id=%s",
                    (category_name, category_id),
                )
                return category_id
            cursor.execute("INSERT INTO categories (category_name) VALUES (%s)", (category_name,))
            return int(cursor.lastrowid)
        finally:
            cursor.close()
    finally:
        connection.close()


def delete_category(category_id: int) -> None:
    connection = get_connection()
    try:
        cursor = connection.cursor()
        try:
            cursor.execute("DELETE FROM categories WHERE category_id=%s", (category_id,))
        finally:
            cursor.close()
    finally:
        connection.close()


def list_products(search: str = "", category_id: int | None = None) -> list[dict]:
    conditions: list[str] = []
    params: list[object] = []
    if search.strip():
        pattern = f"%{search.strip()}%"
        conditions.append("(p.product_name LIKE %s OR p.description LIKE %s)")
        params.extend((pattern, pattern))
    if category_id is not None:
        conditions.append("p.category_id=%s")
        params.append(category_id)
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    query = f"""
        SELECT p.product_id, p.category_id, c.category_name, p.product_name,
               p.description, p.price, p.image_path, p.is_available,
               (p.is_available AND NOT EXISTS (
                   SELECT 1 FROM product_inventory pi
                   JOIN inventory i ON i.inventory_id=pi.inventory_id
                   WHERE pi.product_id=p.product_id
                     AND i.stock_quantity < pi.quantity_required
               )) AS can_order
        FROM products p JOIN categories c ON c.category_id=p.category_id
        {where}
        ORDER BY c.category_name, p.product_name, p.product_id DESC
    """
    connection = get_connection()
    try:
        cursor = connection.cursor(dictionary=True)
        try:
            cursor.execute(query, tuple(params))
            rows = cursor.fetchall()
            # Older databases could contain multiple rows for the same menu
            # identity. Keep the newest row visible until startup migration
            # consolidates the old rows and preserves their order history.
            unique_rows: list[dict] = []
            seen: set[tuple[int, str]] = set()
            for row in rows:
                identity = (int(row["category_id"]), row["product_name"].casefold())
                if identity in seen:
                    continue
                seen.add(identity)
                unique_rows.append(row)
            return unique_rows
        finally:
            cursor.close()
    finally:
        connection.close()


def save_product(
    product_name: str,
    category_id: int,
    price: Decimal | str | float,
    description: str = "",
    image_path: str | None = None,
    product_id: int | None = None,
) -> int:
    product_name = product_name.strip()
    amount = Decimal(str(price))
    if not product_name:
        raise ValueError("Product name is required.")
    if amount < 0:
        raise ValueError("Price cannot be negative.")
    connection = get_connection()
    try:
        cursor = connection.cursor()
        try:
            if product_id:
                cursor.execute(
                    "UPDATE products SET category_id=%s, product_name=%s, description=%s, "
                    "price=%s, image_path=%s WHERE product_id=%s",
                    (category_id, product_name, description, amount, image_path, product_id),
                )
                return product_id
            cursor.execute(
                "INSERT INTO products (category_id, product_name, description, price, image_path) "
                "VALUES (%s, %s, %s, %s, %s)",
                (category_id, product_name, description, amount, image_path),
            )
            return int(cursor.lastrowid)
        finally:
            cursor.close()
    finally:
        connection.close()


def set_product_availability(product_id: int, is_available: bool) -> None:
    connection = get_connection()
    try:
        cursor = connection.cursor()
        try:
            cursor.execute(
                "UPDATE products SET is_available=%s WHERE product_id=%s",
                (bool(is_available), product_id),
            )
        finally:
            cursor.close()
    finally:
        connection.close()


def delete_product(product_id: int) -> None:
    connection = get_connection()
    try:
        cursor = connection.cursor()
        try:
            cursor.execute("DELETE FROM products WHERE product_id=%s", (product_id,))
        finally:
            cursor.close()
    finally:
        connection.close()
