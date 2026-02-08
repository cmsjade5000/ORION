---
name: ledger-finance
description: "Python financial analysis tooling for LEDGER. Use to analyze transaction CSVs, summarize cash flow, compute burn/runway, and break down spend by category when money, budgets, or tradeoffs are central."
---

# LEDGER Finance Toolkit (Python)

Use the bundled script to analyze transaction CSVs and summarize cash flow for LEDGER tasks. Keep outputs descriptive and avoid prescriptive advice.

## Expected CSV Columns

The script is flexible but needs:
- A date column: `date`, `transaction_date`, `posted_date`, or `posting_date`
- An amount column: `amount` or `transaction_amount`

Optional columns:
- Debit/credit columns instead of `amount`: `debit`/`credit`, `withdrawal`/`deposit`, or `outflow`/`inflow`
- Category columns: `category`, `merchant_category`, or `type`
- Description columns: `description`, `memo`, `payee`, or `merchant`

Notes:
- Amounts follow sign convention (positive = inflow, negative = outflow). Parentheses indicate negatives.
- Dates support `YYYY-MM-DD`, `MM/DD/YYYY`, `YYYY/MM/DD`, `DD-MM-YYYY`.

## Quick Commands

Summarize cash flow:

```bash
python3 skills/ledger-finance/scripts/ledger_finance.py --csv path/to/transactions.csv summary
```

Summarize by category:

```bash
python3 skills/ledger-finance/scripts/ledger_finance.py --csv path/to/transactions.csv category --limit 10
```

Estimate runway (cash balance required):

```bash
python3 skills/ledger-finance/scripts/ledger_finance.py --csv path/to/transactions.csv runway --cash 25000
```

## Output Guidance

- Use the summary to highlight net, average monthly net, and top spending categories.
- When runway is negative or not applicable, surface that clearly without judgment.
- Always phrase recommendations as tradeoffs and options, not directives.
