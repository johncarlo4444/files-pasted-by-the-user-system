"""Order creation, payment, kitchen status, and history operations."""

from __future__ import annotations

import secrets
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP

from database import get_connection


CENT = Decimal("0.01")
ORDER_STATUSES = (
    "Pending Payment", "Paid", "Preparing", "Ready", "Completed", "Cancelled"
)
NEXT_STATUS = {"Paid": "Preparing", "Preparing": "Ready", "Ready": "Completed"}


def _amount(value: object) -> Decimal:
    return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)


def _new_order_code(cursor) -> str:
    for attempt in range(50):
        code = (
            f"A{secrets.randbelow(1000):03d}"
            if attempt < 20
            else f"A{secrets.token_hex(4).upper()}"
        )
        cursor.execute("SELECT 1 FROM orders WHERE order_code=%s", (code,))
        if cursor.fetchone() is None:
            return code
    raise RuntimeError("Could not generate a unique order code. Please try again.")


def create_order(order_type: str, items: list[dict]) -> dict:
    if order_type not in ("Dine-In", "Take-Out"):
        raise ValueError("Choose Dine-In or Take-Out.")
    if not items:
        raise ValueError("Add at least one item before submitting the order.")

    connection = get_connection()
    try:
        connection.start_transaction()
        cursor = connection.cursor(dictionary=True)
        try:
            normalized: list[dict] = []
            total = Decimal("0.00")
            for line in items:
                product_id = int(line["product_id"])
                quantity = int(line.get("quantity", 1))
                if quantity < 1:
                    raise ValueError("Item quantity must be at least one.")
                cursor.execute(
                    "SELECT p.product_name, p.price, p.is_available, "
                    "(p.is_available AND NOT EXISTS (SELECT 1 FROM product_inventory pi "
                    "JOIN inventory i ON i.inventory_id=pi.inventory_id "
                    "WHERE pi.product_id=p.product_id AND i.stock_quantity < pi.quantity_required)) "
                    "AS can_order FROM products p WHERE p.product_id=%s FOR UPDATE",
                    (product_id,),
                )
                product = cursor.fetchone()
                if not product or not product["can_order"]:
                    raise ValueError(f"{product['product_name'] if product else 'An item'} is unavailable.")
                adjustment = _amount(line.get("unit_adjustment", 0))
                if adjustment < 0:
                    raise ValueError("Customization price adjustments cannot be negative.")
                unit_total = _amount(product["price"]) + adjustment
                subtotal = _amount(unit_total * quantity)
                total += subtotal
                normalized.append({
                    "product_id": product_id,
                    "quantity": quantity,
                    "customization": (line.get("customization") or "").strip(),
                    "instructions": (line.get("special_instructions") or "").strip(),
                    "subtotal": subtotal,
                })

            required_by_id: dict[int, int] = defaultdict(int)
            ingredient_names: dict[int, str] = {}
            for line in normalized:
                cursor.execute(
                    "SELECT i.inventory_id, i.item_name, pi.quantity_required "
                    "FROM product_inventory pi JOIN inventory i ON i.inventory_id=pi.inventory_id "
                    "WHERE pi.product_id=%s",
                    (line["product_id"],),
                )
                for ingredient in cursor.fetchall():
                    inventory_id = int(ingredient["inventory_id"])
                    required_by_id[inventory_id] += int(ingredient["quantity_required"]) * line["quantity"]
                    ingredient_names[inventory_id] = ingredient["item_name"]
            if required_by_id:
                placeholders = ",".join(["%s"] * len(required_by_id))
                cursor.execute(
                    f"SELECT inventory_id, stock_quantity FROM inventory "
                    f"WHERE inventory_id IN ({placeholders}) FOR UPDATE",
                    tuple(required_by_id),
                )
                stock = {int(row["inventory_id"]): int(row["stock_quantity"]) for row in cursor.fetchall()}
                for inventory_id, required in required_by_id.items():
                    if stock.get(inventory_id, 0) < required:
                        raise ValueError(f"Not enough stock for {ingredient_names[inventory_id]}.")

            order_code = _new_order_code(cursor)
            cursor.execute(
                "INSERT INTO orders (order_code, order_type, total_amount) "
                "VALUES (%s, %s, %s)",
                (order_code, order_type, _amount(total)),
            )
            order_id = int(cursor.lastrowid)
            for line in normalized:
                cursor.execute(
                    "INSERT INTO order_items "
                    "(order_id, product_id, quantity, customization, special_instructions, subtotal) "
                    "VALUES (%s, %s, %s, %s, %s, %s)",
                    (order_id, line["product_id"], line["quantity"], line["customization"],
                     line["instructions"] or None, line["subtotal"]),
                )
            connection.commit()
            return {"order_id": order_id, "order_code": order_code, "total_amount": _amount(total)}
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()
    finally:
        connection.close()


def _items_for_order(cursor, order_id: int) -> list[dict]:
    cursor.execute(
        "SELECT oi.order_item_id, oi.product_id, oi.quantity, oi.customization, "
        "oi.special_instructions, oi.subtotal, p.product_name "
        "FROM order_items oi JOIN products p ON p.product_id=oi.product_id "
        "WHERE oi.order_id=%s ORDER BY oi.order_item_id",
        (order_id,),
    )
    return cursor.fetchall()


def get_order_by_code(order_code: str) -> dict | None:
    connection = get_connection()
    try:
        cursor = connection.cursor(dictionary=True)
        try:
            cursor.execute(
                "SELECT o.*, pay.payment_method, pay.amount_paid, pay.amount_tendered, "
                "pay.change_returned, pay.payment_time, "
                "pay.payment_status AS transaction_status, u.username AS cashier_name "
                "FROM orders o LEFT JOIN payments pay ON pay.payment_id=("
                "SELECT MAX(p2.payment_id) FROM payments p2 WHERE p2.order_id=o.order_id) "
                "LEFT JOIN users u ON u.user_id=pay.cashier_user_id "
                "WHERE o.order_code=%s",
                (order_code.strip().upper(),),
            )
            order = cursor.fetchone()
            if order:
                order["items"] = _items_for_order(cursor, order["order_id"])
            return order
        finally:
            cursor.close()
    finally:
        connection.close()


def list_orders(
    status: str | None = None,
    search: str = "",
    limit: int = 200,
) -> list[dict]:
    if status is not None and status not in ORDER_STATUSES:
        raise ValueError("Invalid order status filter.")
    conditions: list[str] = []
    params: list[object] = []
    if status:
        conditions.append("o.order_status=%s")
        params.append(status)
    if search.strip():
        conditions.append("(o.order_code LIKE %s OR CAST(o.created_at AS CHAR) LIKE %s)")
        pattern = f"%{search.strip()}%"
        params.extend((pattern, pattern))
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    params.append(max(1, min(int(limit), 1000)))
    connection = get_connection()
    try:
        cursor = connection.cursor(dictionary=True)
        try:
            cursor.execute(
                f"SELECT o.order_id, o.order_code, o.order_type, o.total_amount, "
                f"o.payment_status, o.order_status, o.created_at, "
                "(SELECT GROUP_CONCAT(CONCAT(oi.quantity, 'x ', p.product_name, "
                "CASE WHEN COALESCE(oi.customization, '') NOT IN ('', 'Regular') "
                "THEN CONCAT(' [', oi.customization, ']') ELSE '' END, "
                "CASE WHEN COALESCE(oi.special_instructions, '') <> '' "
                "THEN CONCAT(' - Note: ', oi.special_instructions) ELSE '' END) "
                "ORDER BY oi.order_item_id SEPARATOR ' | ') "
                "FROM order_items oi JOIN products p ON p.product_id=oi.product_id "
                "WHERE oi.order_id=o.order_id) AS ticket_items "
                f"FROM orders o {where} "
                "ORDER BY o.created_at DESC LIMIT %s",
                tuple(params),
            )
            return cursor.fetchall()
        finally:
            cursor.close()
    finally:
        connection.close()


def list_pending_orders() -> list[dict]:
    """List unpaid orders in the order they entered the cashier queue."""
    connection = get_connection()
    try:
        cursor = connection.cursor(dictionary=True)
        try:
            cursor.execute(
                "SELECT order_id, order_code, order_type, total_amount, created_at "
                "FROM orders WHERE payment_status='Unpaid' "
                "AND order_status='Pending Payment' "
                "ORDER BY created_at ASC, order_id ASC",
            )
            return cursor.fetchall()
        finally:
            cursor.close()
    finally:
        connection.close()

def record_payment(
    order_code: str,
    payment_method: str,
    amount_tendered: Decimal | str | float,
    cashier_user_id: int | None = None,
) -> dict:
    if payment_method not in ("Cash", "GCash", "Card"):
        raise ValueError("Choose Cash, GCash, or Card.")
    tendered = _amount(amount_tendered)
    if tendered < 0:
        raise ValueError("Amount tendered cannot be negative.")

    connection = get_connection()
    try:
        connection.start_transaction()
        cursor = connection.cursor(dictionary=True)
        try:
            cursor.execute(
                "SELECT order_id, total_amount, payment_status, order_status "
                "FROM orders WHERE order_code=%s FOR UPDATE",
                (order_code.strip().upper(),),
            )
            order = cursor.fetchone()
            if not order:
                raise ValueError("Order code was not found.")
            if order["payment_status"] != "Unpaid" or order["order_status"] != "Pending Payment":
                raise ValueError("This order is not awaiting payment.")
            amount_due = _amount(order["total_amount"])
            if tendered < amount_due:
                raise ValueError(f"Amount tendered is less than the total of ₱{amount_due:,.2f}.")

            cursor.execute(
                "SELECT pi.inventory_id, SUM(oi.quantity*pi.quantity_required) AS required_quantity "
                "FROM order_items oi JOIN product_inventory pi ON pi.product_id=oi.product_id "
                "WHERE oi.order_id=%s GROUP BY pi.inventory_id",
                (order["order_id"],),
            )
            requirements = cursor.fetchall()
            required_by_id = {int(row["inventory_id"]): int(row["required_quantity"]) for row in requirements}
            stock_by_id: dict[int, dict] = {}
            if required_by_id:
                placeholders = ",".join(["%s"] * len(required_by_id))
                cursor.execute(
                    "SELECT inventory_id, item_name, stock_quantity, min_stock_level "
                    f"FROM inventory WHERE inventory_id IN ({placeholders}) FOR UPDATE",
                    tuple(required_by_id),
                )
                stock_by_id = {int(row["inventory_id"]): row for row in cursor.fetchall()}
                for inventory_id, required in required_by_id.items():
                    item = stock_by_id.get(inventory_id)
                    if not item or int(item["stock_quantity"]) < required:
                        name = item["item_name"] if item else "A required ingredient"
                        raise ValueError(f"Not enough stock for {name}; restock before taking payment.")

            for inventory_id, required in required_by_id.items():
                item = stock_by_id[inventory_id]
                remaining = int(item["stock_quantity"]) - required
                status = "Out of Stock" if remaining == 0 else (
                    "Low Stock" if remaining <= int(item["min_stock_level"]) else "Available"
                )
                cursor.execute(
                    "UPDATE inventory SET stock_quantity=%s, status=%s WHERE inventory_id=%s",
                    (remaining, status, inventory_id),
                )

            change = tendered - amount_due if payment_method == "Cash" else Decimal("0.00")
            recorded_tender = tendered if payment_method == "Cash" else amount_due
            cursor.execute(
                "INSERT INTO payments "
                "(order_id, payment_method, amount_paid, amount_tendered, change_returned, cashier_user_id) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                (order["order_id"], payment_method, amount_due, recorded_tender, change, cashier_user_id),
            )
            cursor.execute(
                "UPDATE orders SET payment_status='Paid', order_status='Paid' WHERE order_id=%s",
                (order["order_id"],),
            )
            connection.commit()
            return {
                "order_id": int(order["order_id"]),
                "order_code": order_code.strip().upper(),
                "amount_due": amount_due,
                "amount_tendered": recorded_tender,
                "change_returned": change,
                "payment_method": payment_method,
            }
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()
    finally:
        connection.close()


def advance_order_status(order_id: int, status: str | None = None) -> str:
    connection = get_connection()
    try:
        connection.start_transaction()
        cursor = connection.cursor(dictionary=True)
        try:
            cursor.execute(
                "SELECT order_status FROM orders WHERE order_id=%s FOR UPDATE", (order_id,)
            )
            row = cursor.fetchone()
            if not row:
                raise ValueError("Order was not found.")
            current = row["order_status"]
            next_status = status or NEXT_STATUS.get(current)
            if next_status not in ORDER_STATUSES:
                raise ValueError("There is no next kitchen status for this order.")
            if next_status not in ("Cancelled", NEXT_STATUS.get(current)):
                raise ValueError(f"Cannot move an order from {current} to {next_status}.")
            if next_status == "Cancelled":
                cursor.execute(
                    "UPDATE orders SET order_status='Cancelled', payment_status='Cancelled' "
                    "WHERE order_id=%s AND payment_status='Unpaid'",
                    (order_id,),
                )
                if cursor.rowcount == 0:
                    raise ValueError("Paid orders must be completed through the kitchen workflow.")
            else:
                cursor.execute("UPDATE orders SET order_status=%s WHERE order_id=%s", (next_status, order_id))
            connection.commit()
            return next_status
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()
    finally:
        connection.close()


def cancel_order(order_code: str) -> None:
    connection = get_connection()
    try:
        connection.start_transaction()
        cursor = connection.cursor(dictionary=True)
        try:
            cursor.execute(
                "SELECT order_id, payment_status, order_status FROM orders "
                "WHERE order_code=%s FOR UPDATE",
                (order_code.strip().upper(),),
            )
            order = cursor.fetchone()
            if not order:
                raise ValueError("Order code was not found.")
            if order["order_status"] in ("Completed", "Cancelled"):
                raise ValueError("This order can no longer be cancelled.")
            if order["payment_status"] == "Paid":
                cursor.execute(
                    "SELECT pi.inventory_id, SUM(oi.quantity*pi.quantity_required) AS quantity "
                    "FROM order_items oi JOIN product_inventory pi ON pi.product_id=oi.product_id "
                    "WHERE oi.order_id=%s GROUP BY pi.inventory_id",
                    (order["order_id"],),
                )
                for row in cursor.fetchall():
                    cursor.execute(
                        "UPDATE inventory SET "
                        "status=CASE WHEN stock_quantity+%s=0 THEN 'Out of Stock' "
                        "WHEN stock_quantity+%s<=min_stock_level THEN 'Low Stock' "
                        "ELSE 'Available' END, stock_quantity=stock_quantity+%s "
                        "WHERE inventory_id=%s",
                        (row["quantity"], row["quantity"], row["quantity"], row["inventory_id"]),
                    )
                cursor.execute(
                    "UPDATE payments SET payment_status='Cancelled' "
                    "WHERE order_id=%s AND payment_status='Paid'",
                    (order["order_id"],),
                )
            cursor.execute(
                "UPDATE orders SET payment_status='Cancelled', order_status='Cancelled' WHERE order_id=%s",
                (order["order_id"],),
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()
    finally:
        connection.close()

def _require_admin_override(username: str, password: str) -> dict:
    from models.user_model import authenticate

    user = authenticate(username, password)
    if not user or user["role"] != "Admin":
        raise PermissionError("An active administrator account is required for this action.")
    return user


def update_order_item_quantity(
    order_id: int,
    order_item_id: int,
    quantity: int,
    *,
    admin_username: str | None = None,
    admin_password: str | None = None,
) -> Decimal:
    """Update an unpaid line; reducing its quantity requires admin verification."""
    quantity = int(quantity)
    if quantity < 1:
        raise ValueError("Quantity must be at least one. Use Remove Item to delete a line.")

    connection = get_connection()
    try:
        connection.start_transaction()
        cursor = connection.cursor(dictionary=True)
        try:
            cursor.execute(
                "SELECT payment_status, order_status FROM orders WHERE order_id=%s FOR UPDATE",
                (order_id,),
            )
            order = cursor.fetchone()
            if not order:
                raise ValueError("Order was not found.")
            if order["payment_status"] != "Unpaid" or order["order_status"] != "Pending Payment":
                raise ValueError("Only unpaid pending orders can be edited.")

            cursor.execute(
                "SELECT quantity, subtotal FROM order_items "
                "WHERE order_item_id=%s AND order_id=%s FOR UPDATE",
                (order_item_id, order_id),
            )
            item = cursor.fetchone()
            if not item:
                raise ValueError("The selected item is no longer in this order.")
            old_quantity = int(item["quantity"])
            if quantity < old_quantity:
                _require_admin_override(admin_username or "", admin_password or "")

            unit_total = _amount(Decimal(str(item["subtotal"])) / old_quantity)
            new_subtotal = _amount(unit_total * quantity)
            cursor.execute(
                "UPDATE order_items SET quantity=%s, subtotal=%s WHERE order_item_id=%s",
                (quantity, new_subtotal, order_item_id),
            )
            cursor.execute(
                "SELECT COALESCE(SUM(subtotal), 0) AS total_amount "
                "FROM order_items WHERE order_id=%s",
                (order_id,),
            )
            total = _amount(cursor.fetchone()["total_amount"])
            cursor.execute("UPDATE orders SET total_amount=%s WHERE order_id=%s", (total, order_id))
            connection.commit()
            return total
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()
    finally:
        connection.close()


def remove_order_item(
    order_id: int,
    order_item_id: int,
    admin_username: str,
    admin_password: str,
) -> Decimal:
    """Remove a line from an unpaid order after an authenticated admin override."""
    _require_admin_override(admin_username, admin_password)
    connection = get_connection()
    try:
        connection.start_transaction()
        cursor = connection.cursor(dictionary=True)
        try:
            cursor.execute(
                "SELECT payment_status, order_status FROM orders WHERE order_id=%s FOR UPDATE",
                (order_id,),
            )
            order = cursor.fetchone()
            if not order:
                raise ValueError("Order was not found.")
            if order["payment_status"] != "Unpaid" or order["order_status"] != "Pending Payment":
                raise ValueError("Only unpaid pending orders can have items removed.")
            cursor.execute(
                "SELECT order_item_id FROM order_items "
                "WHERE order_item_id=%s AND order_id=%s FOR UPDATE",
                (order_item_id, order_id),
            )
            if not cursor.fetchone():
                raise ValueError("The selected item is no longer in this order.")
            cursor.execute("SELECT COUNT(*) AS item_count FROM order_items WHERE order_id=%s", (order_id,))
            if int(cursor.fetchone()["item_count"]) <= 1:
                raise ValueError("Use Cancel Order to remove the last item from an order.")
            cursor.execute(
                "DELETE FROM order_items WHERE order_item_id=%s AND order_id=%s",
                (order_item_id, order_id),
            )
            cursor.execute(
                "SELECT COALESCE(SUM(subtotal), 0) AS total_amount "
                "FROM order_items WHERE order_id=%s",
                (order_id,),
            )
            total = _amount(cursor.fetchone()["total_amount"])
            cursor.execute("UPDATE orders SET total_amount=%s WHERE order_id=%s", (total, order_id))
            connection.commit()
            return total
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()
    finally:
        connection.close()


def cancel_order_as_cashier(
    order_code: str,
    admin_username: str,
    admin_password: str,
) -> None:
    """Cancel a cashier-selected order only after a valid admin override."""
    _require_admin_override(admin_username, admin_password)
    cancel_order(order_code)

