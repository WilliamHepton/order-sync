"""Converts between whole minor units and readable amounts."""

from decimal import Decimal

# Most currencies have 2 decimal places. These are Stripe's exceptions.
NO_DECIMALS = set("bif clp djf gnf jpy kmf krw mga pyg rwf ugx vnd vuv xaf xof xpf".split())
THREE_DECIMALS = set("bhd jod kwd omr tnd".split())


def decimal_places(currency: str) -> int:
    return 0 if currency in NO_DECIMALS else 3 if currency in THREE_DECIMALS else 2


def to_decimal(minor_units: int, currency: str) -> Decimal:
    return Decimal(minor_units).scaleb(-decimal_places(currency))


def to_minor(amount: Decimal, currency: str) -> int:
    minor = amount.scaleb(decimal_places(currency))
    if minor != minor.to_integral_value():
        raise ValueError("too many decimal places")
    return int(minor)
