"""Inventory listing, adjustments, and recipe configuration."""

from __future__ import annotations

from database import get_connection


def list_inventory(search: str = "") -> list[dict]:
    connection = get_connection()
    try:
        cursor = connection.cursor(dictionary=True)
        try:
            if search.strip():
                cursor.execute(
                    "SELECT * FROM inventory WHERE item_name LIKE %s ORDER BY item_name",
                    (f"%{search.strip()}%",),
                )
            else:
                cursor.execute("SELECT * FROM inventory ORDER BY item_name")
            return cursor.fetchall()
        finally:
            cursor.close()
    finally:
        connection.close()


def save_inventory_item(
    item_name: str,
    stock_quantity: int,
    unit: str = "pcs",
    min_stock_level: int = 10,
    inventory_id: int | None = None,
) -> int:
    item_name = item_name.strip()
    if not item_name or not unit.strip():
        raise ValueError("Item name and unit are required.")
    if stock_quantity < 0 or min_stock_level < 0:
        raise ValueError("Stock and minimum level cannot be negative.")
    status = "Out of Stock" if stock_quantity == 0 else (
        "Low Stock" if stock_quantity <= min_stock_level else "Available"
    )
    connection = get_connection()
    try:
        cursor = connection.cursor()
        try:
            if inventory_id:
                cursor.execute(
                    "UPDATE inventory SET item_name=%s, stock_quantity=%s, unit=%s, "
                    "min_stock_level=%s, status=%s WHERE inventory_id=%s",
                    (item_name, stock_quantity, unit.strip(), min_stock_level, status, inventory_id),
                )
                return inventory_id
            cursor.execute(
                "INSERT INTO inventory (item_name, stock_quantity, unit, min_stock_level, status) "
                "VALUES (%s, %s, %s, %s, %s)",
                (item_name, stock_quantity, unit.strip(), min_stock_level, status),
            )
            return int(cursor.lastrowid)
        finally:
            cursor.close()
    finally:
        connection.close()


def adjust_stock(inventory_id: int, change: int) -> None:
    connection = get_connection()
    try:
        connection.start_transaction()
        cursor = connection.cursor(dictionary=True)
        try:
            cursor.execute(
                "SELECT stock_quantity, min_stock_level FROM inventory "
                "WHERE inventory_id=%s FOR UPDATE",
                (inventory_id,),
            )
            item = cursor.fetchone()
            if not item:
                raise ValueError("Inventory item was not found.")
            quantity = int(item["stock_quantity"]) + int(change)
            if quantity < 0:
                raise ValueError("Adjustment would make stock negative.")
            status = "Out of Stock" if quantity == 0 else (
                "Low Stock" if quantity <= item["min_stock_level"] else "Available"
            )
            cursor.execute(
                "UPDATE inventory SET stock_quantity=%s, status=%s WHERE inventory_id=%s",
                (quantity, status, inventory_id),
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()
    finally:
        connection.close()


def set_product_recipe(product_id: int, ingredient_quantities: dict[int, int]) -> None:
    if any(quantity <= 0 for quantity in ingredient_quantities.values()):
        raise ValueError("Recipe quantities must be positive integers.")
    connection = get_connection()
    try:
        connection.start_transaction()
        cursor = connection.cursor()
        try:
            cursor.execute("DELETE FROM product_inventory WHERE product_id=%s", (product_id,))
            for inventory_id, quantity in ingredient_quantities.items():
                cursor.execute(
                    "INSERT INTO product_inventory (product_id, inventory_id, quantity_required) "
                    "VALUES (%s, %s, %s)",
                    (product_id, inventory_id, quantity),
                )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()
    finally:
        connection.close()


def get_product_recipe(product_id: int) -> dict[int, int]:
    connection = get_connection()
    try:
        cursor = connection.cursor()
        try:
            cursor.execute(
                "SELECT inventory_id, quantity_required FROM product_inventory WHERE product_id=%s",
                (product_id,),
            )
            return {int(inventory_id): int(quantity) for inventory_id, quantity in cursor.fetchall()}
        finally:
            cursor.close()
    finally:
        connection.close()
