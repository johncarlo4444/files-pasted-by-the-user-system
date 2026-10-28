"""Dashboard metrics, sales summaries, and printable report exports."""

from __future__ import annotations

import csv
from datetime import date, datetime, timedelta
from pathlib import Path

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


def _as_date(value: date | datetime | str | None, label: str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if value is None or not str(value).strip():
        raise ValueError(f"Enter a {label} date in YYYY-MM-DD format.")
    try:
        return date.fromisoformat(str(value).strip())
    except ValueError as exc:
        raise ValueError(f"The {label} date must use YYYY-MM-DD format.") from exc


def _period_bounds(period: str, start_date=None, end_date=None) -> tuple[date, date]:
    today = date.today()
    if period == "Daily":
        return today, today
    if period == "Weekly":
        return today - timedelta(days=6), today
    if period == "Monthly":
        return today.replace(day=1), today
    if period == "Custom Range":
        start, end = _as_date(start_date, "start"), _as_date(end_date, "end")
        if start > end:
            raise ValueError("Start date must be on or before the end date.")
        if (end - start).days > 365:
            raise ValueError("Choose a date range of one year or less.")
        return start, end
    raise ValueError("Choose Daily, Weekly, Monthly, or Custom Range.")


def sales_summary(period: str = "Daily", *, start_date=None, end_date=None) -> dict:
    """Return paid sales and order analytics for a date range (inclusive)."""
    start, end = _period_bounds(period, start_date, end_date)
    start_dt = datetime.combine(start, datetime.min.time())
    end_exclusive = datetime.combine(end + timedelta(days=1), datetime.min.time())
    connection = get_connection()
    try:
        cursor = connection.cursor(dictionary=True)
        try:
            cursor.execute(
                "SELECT COALESCE(SUM(p.amount_paid),0) AS sales, "
                "COUNT(DISTINCT p.order_id) AS orders FROM payments p "
                "WHERE p.payment_status='Paid' AND p.payment_time >= %s AND p.payment_time < %s",
                (start_dt, end_exclusive),
            )
            summary = cursor.fetchone() or {"sales": 0, "orders": 0}
            cursor.execute(
                "SELECT DATE(p.payment_time) AS sale_date, SUM(p.amount_paid) AS sales, "
                "COUNT(DISTINCT p.order_id) AS orders FROM payments p "
                "WHERE p.payment_status='Paid' AND p.payment_time >= %s AND p.payment_time < %s "
                "GROUP BY DATE(p.payment_time) ORDER BY sale_date",
                (start_dt, end_exclusive),
            )
            by_date = {row["sale_date"].isoformat(): row for row in cursor.fetchall()}
            trend = []
            current = start
            while current <= end:
                row = by_date.get(current.isoformat())
                trend.append({
                    "sale_date": current,
                    "sales": row["sales"] if row else 0,
                    "orders": row["orders"] if row else 0,
                })
                current += timedelta(days=1)
            summary["trend"] = trend
            cursor.execute(
                "SELECT pr.product_name, "
                "COALESCE(SUM(CASE WHEN p.payment_id IS NOT NULL THEN oi.quantity ELSE 0 END),0) "
                "AS units_sold, "
                "COALESCE(SUM(CASE WHEN p.payment_id IS NOT NULL THEN oi.subtotal ELSE 0 END),0) "
                "AS revenue FROM products pr "
                "LEFT JOIN order_items oi ON oi.product_id=pr.product_id "
                "LEFT JOIN payments p ON p.order_id=oi.order_id AND p.payment_status='Paid' "
                "AND p.payment_time >= %s AND p.payment_time < %s "
                "GROUP BY pr.product_id, pr.product_name ORDER BY units_sold DESC, pr.product_name",
                (start_dt, end_exclusive),
            )
            summary["products"] = cursor.fetchall()
            cursor.execute(
                "SELECT c.category_name, COALESCE(SUM(CASE WHEN p.payment_id IS NOT NULL "
                "THEN oi.subtotal ELSE 0 END),0) AS revenue FROM categories c "
                "LEFT JOIN products pr ON pr.category_id=c.category_id "
                "LEFT JOIN order_items oi ON oi.product_id=pr.product_id "
                "LEFT JOIN payments p ON p.order_id=oi.order_id AND p.payment_status='Paid' "
                "AND p.payment_time >= %s AND p.payment_time < %s "
                "GROUP BY c.category_id, c.category_name ORDER BY revenue DESC, c.category_name",
                (start_dt, end_exclusive),
            )
            summary["categories"] = cursor.fetchall()
            cursor.execute(
                "SELECT order_status, COUNT(*) AS orders FROM orders "
                "WHERE created_at >= %s AND created_at < %s "
                "GROUP BY order_status ORDER BY order_status",
                (start_dt, end_exclusive),
            )
            summary["order_distribution"] = cursor.fetchall()
            summary["start_date"] = start
            summary["end_date"] = end
            summary["period"] = period
            return summary
        finally:
            cursor.close()
    finally:
        connection.close()


def save_sales_report_csv(data: dict, path: str | Path) -> Path:
    """Export report summary and breakdowns to a spreadsheet-friendly CSV."""
    target = Path(path).expanduser().resolve()
    if target.suffix.lower() != ".csv":
        target = target.with_suffix(".csv")
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["Sales Report", data.get("period", "Custom Range")])
        writer.writerow(["Date range", data["start_date"], "to", data["end_date"]])
        writer.writerow(["Total sales (PHP)", data.get("sales", 0)])
        writer.writerow(["Paid transactions", data.get("orders", 0)])
        writer.writerow([])
        writer.writerow(["Daily Breakdown"])
        writer.writerow(["Date", "Sales (PHP)", "Paid orders"])
        for row in data.get("trend", []):
            writer.writerow([row["sale_date"], row["sales"], row["orders"]])
        writer.writerow([])
        writer.writerow(["Product Sales"])
        writer.writerow(["Product", "Units sold", "Revenue (PHP)"])
        for row in data.get("products", []):
            writer.writerow([row["product_name"], row["units_sold"], row["revenue"]])
        writer.writerow([])
        writer.writerow(["Category Sales"])
        writer.writerow(["Category", "Revenue (PHP)"])
        for row in data.get("categories", []):
            writer.writerow([row["category_name"], row["revenue"]])
        writer.writerow([])
        writer.writerow(["Orders by status"])
        writer.writerow(["Status", "Orders"])
        for row in data.get("order_distribution", []):
            writer.writerow([row["order_status"], row["orders"]])
    return target


def save_sales_report_pdf(
    data: dict,
    path: str | Path,
    restaurant_name: str,
    tagline: str = "",
    branch: str = "",
    address: str = "",
    contact: str = "",
) -> Path:
    """Create a paginated, ready-to-print PDF sales report."""
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import landscape, letter
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.units import inch
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
        from xml.sax.saxutils import escape
    except ImportError as exc:
        raise RuntimeError("PDF export requires reportlab. Install the app dependencies first.") from exc

    target = Path(path).expanduser().resolve()
    if target.suffix.lower() != ".pdf":
        target = target.with_suffix(".pdf")
    target.parent.mkdir(parents=True, exist_ok=True)
    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(str(target), pagesize=landscape(letter),
                            rightMargin=0.45 * inch, leftMargin=0.45 * inch,
                            topMargin=0.45 * inch, bottomMargin=0.45 * inch)
    elements = [Paragraph(escape(restaurant_name), styles["Title"])]
    for detail in (tagline, branch, address, contact):
        if detail.strip():
            elements.append(Paragraph(escape(detail), styles["Normal"]))
    elements.extend([
        Spacer(1, 8),
        Paragraph("Sales Report", styles["Heading1"]),
        Paragraph(f"{data['start_date']} through {data['end_date']}", styles["Normal"]),
        Spacer(1, 10),
    ])

    def add_table(title: str, headings: list[str], rows: list[list[object]]) -> None:
        elements.append(Paragraph(title, styles["Heading2"]))
        table = Table([headings, *rows], repeatRows=1, hAlign="LEFT")
        table_styles = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#c62828")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#d7ccc8")),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]
        if rows:
            table_styles.append(("ROWBACKGROUNDS", (0, 1), (-1, -1),
                                 [colors.white, colors.HexColor("#fff8f5")]))
        table.setStyle(TableStyle(table_styles))
        elements.extend([table, Spacer(1, 10)])

    add_table("Summary", ["Total Sales (PHP)", "Paid Transactions"],
              [[f"PHP {data.get('sales', 0):,.2f}", data.get("orders", 0)]])
    add_table("Daily Breakdown", ["Date", "Sales (PHP)", "Paid Orders"],
              [[str(row["sale_date"]), f"PHP {row['sales']:,.2f}", row["orders"]]
               for row in data.get("trend", [])])
    add_table("Product Sales", ["Product", "Units Sold", "Revenue (PHP)"],
              [[row["product_name"], row["units_sold"], f"PHP {row['revenue']:,.2f}"]
               for row in data.get("products", [])])
    add_table("Category Sales", ["Category", "Revenue (PHP)"],
              [[row["category_name"], f"PHP {row['revenue']:,.2f}"]
               for row in data.get("categories", [])])
    add_table("Orders by Status", ["Status", "Orders"],
              [[row["order_status"], row["orders"]] for row in data.get("order_distribution", [])])
    doc.build(elements)
    return target
