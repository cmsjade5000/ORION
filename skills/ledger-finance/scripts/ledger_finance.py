#!/usr/bin/env python3
"""LEDGER financial analysis helper.

Parse transaction CSVs, summarize cash flow, compute category totals, and
estimate runway based on average monthly net.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional


DATE_FIELDS = (
    "date",
    "transaction_date",
    "posted_date",
    "posting_date",
)
AMOUNT_FIELDS = (
    "amount",
    "transaction_amount",
)
DEBIT_FIELDS = ("debit", "withdrawal", "outflow")
CREDIT_FIELDS = ("credit", "deposit", "inflow")
CATEGORY_FIELDS = ("category", "merchant_category", "type")
DESCRIPTION_FIELDS = ("description", "memo", "payee", "merchant")


@dataclass
class Transaction:
    date: dt.date
    amount: float
    category: str
    description: str


class LedgerFinanceError(Exception):
    pass


def parse_money(raw: str) -> float:
    if raw is None:
        raise LedgerFinanceError("Missing amount value")
    value = raw.strip()
    if value == "":
        raise LedgerFinanceError("Empty amount value")
    negative = False
    if value.startswith("(") and value.endswith(")"):
        negative = True
        value = value[1:-1]
    value = value.replace("$", "").replace(",", "")
    try:
        amount = float(value)
    except ValueError as exc:
        raise LedgerFinanceError(f"Invalid amount value: {raw}") from exc
    return -amount if negative else amount


def parse_date(raw: str) -> dt.date:
    if raw is None:
        raise LedgerFinanceError("Missing date value")
    value = raw.strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%Y/%m/%d", "%d-%m-%Y"):
        try:
            return dt.datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    try:
        return dt.date.fromisoformat(value)
    except ValueError as exc:
        raise LedgerFinanceError(f"Invalid date value: {raw}") from exc


def get_first_field(row: dict, fields: Iterable[str]) -> Optional[str]:
    for field in fields:
        if field in row and row[field] not in (None, ""):
            return row[field]
    return None


def resolve_amount(row: dict) -> float:
    amount_value = get_first_field(row, AMOUNT_FIELDS)
    if amount_value is not None:
        return parse_money(amount_value)

    debit_value = get_first_field(row, DEBIT_FIELDS)
    credit_value = get_first_field(row, CREDIT_FIELDS)
    if debit_value is None and credit_value is None:
        raise LedgerFinanceError(
            "Missing amount column. Provide amount or debit/credit columns."
        )

    debit = parse_money(debit_value) if debit_value is not None else 0.0
    credit = parse_money(credit_value) if credit_value is not None else 0.0
    return credit - debit


def load_transactions(path: Path) -> List[Transaction]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise LedgerFinanceError("CSV has no headers")
        normalized_fields = [field.strip().lower() for field in reader.fieldnames]
        field_map = dict(zip(reader.fieldnames, normalized_fields))

        transactions: List[Transaction] = []
        for row in reader:
            normalized_row = {
                field_map[key]: (value.strip() if isinstance(value, str) else value)
                for key, value in row.items()
            }
            date_value = get_first_field(normalized_row, DATE_FIELDS)
            if date_value is None:
                raise LedgerFinanceError("Missing date column")
            amount = resolve_amount(normalized_row)
            category = get_first_field(normalized_row, CATEGORY_FIELDS) or "Uncategorized"
            description = (
                get_first_field(normalized_row, DESCRIPTION_FIELDS) or ""
            )
            transactions.append(
                Transaction(
                    date=parse_date(date_value),
                    amount=amount,
                    category=category,
                    description=description,
                )
            )
    return transactions


def filter_transactions(
    transactions: Iterable[Transaction],
    start: Optional[dt.date],
    end: Optional[dt.date],
) -> List[Transaction]:
    filtered: List[Transaction] = []
    for tx in transactions:
        if start and tx.date < start:
            continue
        if end and tx.date > end:
            continue
        filtered.append(tx)
    return filtered


def monthly_totals(transactions: Iterable[Transaction]) -> dict:
    totals = defaultdict(float)
    for tx in transactions:
        month_key = tx.date.strftime("%Y-%m")
        totals[month_key] += tx.amount
    return dict(sorted(totals.items()))


def category_totals(transactions: Iterable[Transaction]) -> dict:
    totals = defaultdict(float)
    for tx in transactions:
        totals[tx.category] += tx.amount
    return dict(sorted(totals.items(), key=lambda item: item[1]))


def summary_stats(transactions: Iterable[Transaction]) -> dict:
    amounts = [tx.amount for tx in transactions]
    income = sum(value for value in amounts if value > 0)
    expenses = sum(-value for value in amounts if value < 0)
    net = sum(amounts)
    months = monthly_totals(transactions)
    month_values = list(months.values())
    avg_monthly_net = sum(month_values) / len(month_values) if month_values else 0.0
    avg_monthly_income = (
        income / len(month_values) if month_values else 0.0
    )
    avg_monthly_expense = (
        expenses / len(month_values) if month_values else 0.0
    )
    return {
        "transaction_count": len(amounts),
        "total_income": income,
        "total_expenses": expenses,
        "net": net,
        "months": months,
        "average_monthly_net": avg_monthly_net,
        "average_monthly_income": avg_monthly_income,
        "average_monthly_expense": avg_monthly_expense,
    }


def runway_from_summary(summary: dict, cash_balance: float) -> dict:
    burn = -summary["average_monthly_net"]
    if burn <= 0:
        return {
            "burn_rate": 0.0,
            "runway_months": None,
            "note": "Average monthly net is non-negative; runway not applicable.",
        }
    return {
        "burn_rate": burn,
        "runway_months": cash_balance / burn if burn else None,
        "note": "Runway is estimated using average monthly net burn.",
    }


def format_currency(value: float) -> str:
    return f"${value:,.2f}"


def print_summary(summary: dict, as_json: bool) -> None:
    if as_json:
        print(json.dumps(summary, indent=2))
        return
    print("Summary")
    print("--------")
    print(f"Transactions: {summary['transaction_count']}")
    print(f"Total income: {format_currency(summary['total_income'])}")
    print(f"Total expenses: {format_currency(summary['total_expenses'])}")
    print(f"Net: {format_currency(summary['net'])}")
    print(f"Avg monthly net: {format_currency(summary['average_monthly_net'])}")
    print(f"Avg monthly income: {format_currency(summary['average_monthly_income'])}")
    print(
        f"Avg monthly expense: {format_currency(summary['average_monthly_expense'])}"
    )
    print("\nMonthly net")
    for month, value in summary["months"].items():
        print(f"  {month}: {format_currency(value)}")


def print_categories(totals: dict, as_json: bool, limit: Optional[int]) -> None:
    if as_json:
        print(json.dumps(totals, indent=2))
        return
    print("Category totals (negative = spend, positive = income)")
    print("-----------------------------------------------------")
    items = list(totals.items())
    if limit:
        items = items[:limit]
    for category, total in items:
        print(f"{category:>20}: {format_currency(total)}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analyze financial transactions for LEDGER.",
    )
    parser.add_argument("--csv", required=True, help="Path to transaction CSV")
    parser.add_argument(
        "--start",
        help="Start date filter (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--end",
        help="End date filter (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output JSON",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("summary", help="Summarize cash flow")

    category_parser = subparsers.add_parser("category", help="Summarize by category")
    category_parser.add_argument(
        "--limit", type=int, help="Limit number of categories shown"
    )

    runway_parser = subparsers.add_parser("runway", help="Estimate cash runway")
    runway_parser.add_argument(
        "--cash",
        required=True,
        type=float,
        help="Current cash balance",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()
    path = Path(args.csv)
    if not path.exists():
        raise LedgerFinanceError(f"CSV not found: {path}")

    transactions = load_transactions(path)
    start = parse_date(args.start) if args.start else None
    end = parse_date(args.end) if args.end else None
    filtered = filter_transactions(transactions, start, end)

    if not filtered:
        raise LedgerFinanceError("No transactions after applying filters")

    if args.command == "summary":
        summary = summary_stats(filtered)
        print_summary(summary, args.json)
        return

    if args.command == "category":
        totals = category_totals(filtered)
        print_categories(totals, args.json, args.limit)
        return

    if args.command == "runway":
        summary = summary_stats(filtered)
        runway = runway_from_summary(summary, args.cash)
        payload = {"summary": summary, "runway": runway}
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            print_summary(summary, False)
            print("\nRunway")
            print("------")
            print(f"Burn rate: {format_currency(runway['burn_rate'])} / month")
            runway_months = runway["runway_months"]
            if runway_months is None:
                print(runway["note"])
            else:
                print(f"Estimated runway: {runway_months:.1f} months")
                print(runway["note"])
        return

    raise LedgerFinanceError(f"Unknown command: {args.command}")


if __name__ == "__main__":
    try:
        main()
    except LedgerFinanceError as exc:
        raise SystemExit(str(exc))
