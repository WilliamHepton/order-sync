"""Reads historical orders from CSV, keeping good rows and explaining bad ones."""

import csv
import io
import re
from dataclasses import asdict, dataclass, field
from decimal import Decimal, InvalidOperation

from pydantic import ValidationError

from order_sync.models import Order
from order_sync.money import to_minor

REQUIRED = {"order_id", "email", "amount", "currency"}
OPTIONAL = {"customer_name", "customer_note"}
MAX_BYTES = 1_000_000
MAX_ROWS = 1000
AMOUNT = re.compile(r"[0-9]{1,9}(\.[0-9]{1,3})?")  # no signs, commas or exponents


class InvalidFile(Exception):
    """The whole file cannot be read. The message is safe to show the caller."""


@dataclass
class Rejection:
    line: int
    reasons: list[str]


@dataclass
class ImportResult:
    orders: list[Order] = field(default_factory=list)
    rejected: list[Rejection] = field(default_factory=list)

    def report(self) -> dict[str, object]:
        return {"queued": len(self.orders), "rejected": [asdict(r) for r in self.rejected]}


def read_csv(data: bytes) -> ImportResult:
    if len(data) > MAX_BYTES:
        raise InvalidFile("The file is larger than 1 MB")
    try:
        text = data.decode("utf-8-sig")  # -sig: Excel adds an invisible mark at the start
    except UnicodeDecodeError:
        raise InvalidFile("The file is not UTF-8 text") from None

    reader = csv.DictReader(io.StringIO(text, newline=""), strict=True)
    result = ImportResult()
    seen: set[str] = set()
    try:
        check_header(reader.fieldnames)
        for number, row in enumerate(reader, start=1):
            if number > MAX_ROWS:
                raise InvalidFile(f"The file has more than {MAX_ROWS} orders")
            try:
                order = read_row(row)
                if order.order_id in seen:
                    raise ValueError("order_id: repeated in this file")
            except ValueError as error:
                result.rejected.append(Rejection(reader.line_num, explain(error)))
                continue
            seen.add(order.order_id)
            result.orders.append(order)
    except csv.Error:
        raise InvalidFile(f"The CSV is broken near line {reader.line_num}") from None
    return result


def check_header(names: object) -> None:
    columns = list(names) if isinstance(names, (list, tuple)) else []
    missing = REQUIRED - set(columns)
    if missing:
        raise InvalidFile(f"Missing columns: {', '.join(sorted(missing))}")
    if len(columns) != len(set(columns)) or set(columns) - REQUIRED - OPTIONAL:
        raise InvalidFile("The file has repeated or unknown columns")


def read_row(row: dict[str, str | None]) -> Order:
    # csv uses the key None for extra values, and the value None for missing ones.
    if None in row or None in row.values():
        raise ValueError("row: wrong number of values")
    values = {name: (value or "").strip() for name, value in row.items()}
    currency = values["currency"].lower()
    amount = values["amount"]
    if not AMOUNT.fullmatch(amount):
        raise ValueError("amount: must be a plain number such as 25.99")
    try:
        minor = to_minor(Decimal(amount), currency)
    except (InvalidOperation, ValueError):
        raise ValueError("amount: too many decimal places for the currency") from None
    return Order(
        order_id=values["order_id"],
        email=values["email"],
        customer_name=values.get("customer_name") or None,
        amount_total=minor,
        currency=currency,
        customer_note=values.get("customer_note", ""),
    )


def explain(error: ValueError) -> list[str]:
    """Which fields are wrong and why, without repeating the customer's data."""
    if isinstance(error, ValidationError):
        return [
            f"{e['loc'][0]}: {REASONS.get(str(e['loc'][0]), 'invalid')}" for e in error.errors()
        ]
    return [str(error)]


REASONS = {
    "order_id": "must be 1 to 200 letters, digits, - or _",
    "email": "not a valid email address",
    "currency": "must be a 3-letter code such as gbp",
    "customer_note": "longer than 500 characters",
}
