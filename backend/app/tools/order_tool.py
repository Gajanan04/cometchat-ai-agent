"""Safe, lookup-only order tool."""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any

_ORDER_ID = re.compile(r"^ORD[- ]?(\d{4})$", re.IGNORECASE)


@dataclass(frozen=True)
class OrderLookup:
    found: bool
    order: dict[str, Any] | None
    error: str | None = None


def normalize_order_id(value: str) -> str | None:
    match = _ORDER_ID.match(value.strip())
    return f"ORD-{match.group(1)}" if match else None


def lookup_order(order_id: str, data_path: str | Path) -> OrderLookup:
    normalized = normalize_order_id(order_id)
    if normalized is None:
        return OrderLookup(False, None, "Please provide an order ID in the format ORD-1234.")
    payload = json.loads(Path(data_path).read_text(encoding="utf-8"))
    record = next((order for order in payload["orders"] if order["order_id"] == normalized), None)
    if record is None:
        return OrderLookup(False, None, "That order was not found. Please check the order ID or contact support.")
    return OrderLookup(True, _sanitize(record))


def _sanitize(record: dict[str, Any]) -> dict[str, Any]:
    status = record["status"]
    result = {key: record.get(key) for key in ("order_id", "membership_tier", "status", "status_updated_at", "placed_at", "customer_safe_message")}
    result["items"] = [{key: item[key] for key in ("name", "quantity", "final_sale")} for item in record["items"]]
    if status not in {"cancelled", "returned"}:
        result.update({key: record.get(key) for key in ("shipped_at", "delivered_at", "carrier", "tracking_number", "estimated_delivery")})
    return result
