import json

import azure.functions as func
import pytest

from function_app import import_csv
from order_sync.csv_import import InvalidFile, read_csv
from order_sync.models import Order

HEADER = "order_id,email,customer_name,amount,currency,customer_note\n"
GOOD = "csv-1,ada@example.com,Test Customer,25.99,GBP,Leave at the door\n"


def read(rows: str) -> tuple[list[Order], list[list[str]]]:
    result = read_csv((HEADER + rows).encode())
    return result.orders, [r.reasons for r in result.rejected]


def test_good_row_becomes_an_order() -> None:
    orders, rejected = read(GOOD)
    assert rejected == []
    assert orders[0].amount_total == 2599
    assert orders[0].currency == "gbp"
    assert orders[0].customer_note == "Leave at the door"


@pytest.mark.parametrize(
    ("row", "reason"),
    [
        ("bad/id,a@example.com,,1,gbp,\n", "order_id: must be 1 to 200 letters, digits, - or _"),
        ("csv-1,not-an-email,,1,gbp,\n", "email: not a valid email address"),
        ("csv-1,a@example.com,,-1,gbp,\n", "amount: must be a plain number such as 25.99"),
        ("csv-1,a@example.com,,1e3,gbp,\n", "amount: must be a plain number such as 25.99"),
        ("csv-1,a@example.com,,NaN,gbp,\n", "amount: must be a plain number such as 25.99"),
        ("csv-1,a@example.com,,1.005,gbp,\n", "amount: too many decimal places for the currency"),
        ("csv-1,a@example.com,,1.5,jpy,\n", "amount: too many decimal places for the currency"),
        ("csv-1,a@example.com,,1,pounds,\n", "currency: must be a 3-letter code such as gbp"),
        ("csv-1,a@example.com\n", "row: wrong number of values"),
        ("csv-1,a@example.com,,1,gbp,,extra\n", "row: wrong number of values"),
        (f"csv-1,a@example.com,,1,gbp,{'x' * 501}\n", "customer_note: longer than 500 characters"),
    ],
)
def test_bad_row_is_explained(row: str, reason: str) -> None:
    orders, rejected = read(row)
    assert orders == []
    assert rejected == [[reason]]


def test_every_problem_in_a_row_is_listed() -> None:
    _, rejected = read("bad/id,not-an-email,,1,gbp,\n")
    assert len(rejected[0]) == 2


def test_repeated_order_is_rejected_once() -> None:
    orders, rejected = read(GOOD + GOOD)
    assert len(orders) == 1
    assert rejected == [["order_id: repeated in this file"]]


def test_line_numbers_allow_for_multi_line_notes() -> None:
    rows = 'csv-1,a@example.com,,1,gbp,"two\nlines"\ncsv-2,bad,,1,gbp,\n'
    result = read_csv((HEADER + rows).encode())
    assert result.rejected[0].line == 4


def test_excel_file_is_accepted() -> None:
    data = b"\xef\xbb\xbf" + (HEADER + GOOD).replace("\n", "\r\n").encode()
    assert len(read_csv(data).orders) == 1


@pytest.mark.parametrize(
    "data",
    [
        b"",
        b"order_id,email\n",
        b"order_id,email,amount,currency,extra\n",
        b"order_id,email,amount,currency,email\n",
        b"\xff\xfe",
        b"x" * 1_000_001,
        (HEADER + 'csv-1,"broken').encode(),
        (HEADER + "".join(f"csv-{n},a@example.com,,1,gbp,\n" for n in range(1001))).encode(),
    ],
)
def test_unusable_file_is_refused(data: bytes) -> None:
    with pytest.raises(InvalidFile):
        read_csv(data)


class FakeOut(func.Out[list[str]]):
    value: list[str] | None = None

    def set(self, val: list[str]) -> None:
        self.value = val

    def get(self) -> list[str] | None:  # type: ignore[override]
        return self.value


def call(data: bytes) -> tuple[func.HttpResponse, list[str] | None]:
    request = func.HttpRequest("POST", "/api/orders/import", body=data)
    out = FakeOut()
    return import_csv(request, out), out.value


def test_fifty_rows_with_five_bad() -> None:
    rows = "".join(
        f"csv-{n},{'bad' if n % 10 == 0 else 'a@example.com'},,1,gbp,\n" for n in range(1, 51)
    )
    response, queued = call((HEADER + rows).encode())
    report = json.loads(response.get_body())
    assert response.status_code == 200
    assert report["queued"] == 45
    assert [r["line"] for r in report["rejected"]] == [11, 21, 31, 41, 51]
    assert queued is not None and len(queued) == 45
    assert Order.model_validate_json(queued[0]).order_id == "csv-1"


def test_report_does_not_repeat_customer_data() -> None:
    response, queued = call((HEADER + "csv-1,secret-person,,1,gbp,\n").encode())
    assert b"secret-person" not in response.get_body()
    assert queued is None


def test_bad_file_is_a_400() -> None:
    response, queued = call(b"nonsense")
    assert response.status_code == 400
    assert queued is None
