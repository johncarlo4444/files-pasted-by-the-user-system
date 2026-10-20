"""Dashboard metrics, sales summaries, and product analytics."""

from __future__ import annotations

from database import get_connection


def dashboard_metrics() -> dict:
    connection = get_connection()
    try:
        cursor = connection.cursor(dictionary=True)
        try:
            cursor.execute(
                "SELECT COUNT(*) AS total_orders, "
                "SUM(order_status='Pending Payment') AS pending, "
                "SUM(order_status IN ('Paid','Preparing')) AS preparing, "
                "SUM(order_status='Ready') AS ready, "
                "SUM(order_status='Completed') AS completed, "
                "SUM(order_status='Cancelled') AS cancelled "
                "FROM orders WHERE DATE(created_at)=CURRENT_DATE()"
            )
            metrics = cursor.fetchone() or {}
            cursor.execute(
                "SELECT COALESCE(SUM(amount_paid),0) AS sales FROM payments "
                "WHERE payment_status='Paid' AND DATE(payment_time)=CURRENT_DATE()"
            )
            metrics["sales"] = cursor.fetchone()["sales"]
            return metrics
        finally:
            cursor.close()
    finally:
        connection.close()


def sales_summary(period: str = "Daily") -> dict:
    units = {"Daily": ("DAY", 1), "Weekly": ("DAY", 7), "Monthly": ("MONTH", 1)}
    if period not in units:
        raise ValueError("Choose Daily, Weekly, or Monthly.")
    unit, count = units[period]
    connection = get_connection()
    try:
        cursor = connection.cursor(dictionary=True)
        try:
            cursor.execute(
                "SELECT COALESCE(SUM(p.amount_paid),0) AS sales, COUNT(DISTINCT p.order_id) AS orders "
                "FROM payments p WHERE p.payment_status='Paid' "
                f"AND p.payment_time >= CURRENT_DATE() - INTERVAL {count} {unit}"
            )
            summary = cursor.fetchone()
            cursor.execute(
                "SELECT DATE(p.payment_time) AS sale_date, SUM(p.amount_paid) AS sales, "
                "COUNT(*) AS orders FROM payments p WHERE p.payment_status='Paid' "
                f"AND p.payment_time >= CURRENT_DATE() - INTERVAL {count} {unit} "
                "GROUP BY DATE(p.payment_time) ORDER BY sale_date"
            )
            summary["trend"] = cursor.fetchall()
            cursor.execute(
                "SELECT pr.product_name, "
                "COALESCE(SUM(CASE WHEN p.payment_id IS NOT NULL THEN oi.quantity ELSE 0 END),0) "
                "AS units_sold, "
                "COALESCE(SUM(CASE WHEN p.payment_id IS NOT NULL THEN oi.subtotal ELSE 0 END),0) "
                "AS revenue FROM products pr "
                "LEFT JOIN order_items oi ON oi.product_id=pr.product_id "
                "LEFT JOIN payments p ON p.order_id=oi.order_id AND p.payment_status='Paid' "
                f"AND p.payment_time >= CURRENT_DATE() - INTERVAL {count} {unit} "
                "GROUP BY pr.product_id, pr.product_name ORDER BY units_sold DESC, pr.product_name"
            )
            summary["products"] = cursor.fetchall()
            cursor.execute(
                "SELECT c.category_name, COALESCE(SUM(CASE WHEN p.payment_id IS NOT NULL "
                "THEN oi.subtotal ELSE 0 END),0) AS revenue FROM categories c "
                "LEFT JOIN products pr ON pr.category_id=c.category_id "
                "LEFT JOIN order_items oi ON oi.product_id=pr.product_id "
                "LEFT JOIN payments p ON p.order_id=oi.order_id AND p.payment_status='Paid' "
                f"AND p.payment_time >= CURRENT_DATE() - INTERVAL {count} {unit} "
                "GROUP BY c.category_id, c.category_name ORDER BY revenue DESC, c.category_name"
            )
            summary["categories"] = cursor.fetchall()
            cursor.execute(
                "SELECT order_status, COUNT(*) AS orders FROM orders "
                f"WHERE created_at >= CURRENT_DATE() - INTERVAL {count} {unit} "
                "GROUP BY order_status ORDER BY order_status"
            )
            summary["order_distribution"] = cursor.fetchall()
            return summary
        finally:
            cursor.close()
    finally:
        connection.close()
