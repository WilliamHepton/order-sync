"""Turns whole minor units into a readable amount."""

from decimal import Decimal

# Most currencies have 2 decimal places. These are Stripe's exceptions.
NO_DECIMALS = set("bif clp djf gnf jpy kmf krw mga pyg rwf ugx vnd vuv xaf xof xpf".split())
THREE_DECIMALS = set("bhd jod kwd omr tnd".split())


def to_decimal(minor_units: int, currency: str) -> Decimal:
    places = 0 if currency in NO_DECIMALS else 3 if currency in THREE_DECIMALS else 2
    return Decimal(minor_units).scaleb(-places)
