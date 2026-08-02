# Return Agent (MVP)

A simple browser automation agent that reads pending return requests from an
Excel sheet, processes them on Flipkart using Playwright, and writes the
results (or a Human Review reason) back to Excel immediately after each row.

This is a prototype, built to match the product workflow exactly - not a
production system. Code is kept intentionally simple and readable.

## How it works

1. **Read Excel** - scans `sample_returns.xlsx` for every row where
   `Task Status = Pending`.
2. **Validate** - if `Platform`, `Order ID`, or `SKU` is missing, the row is
   marked `Human Review` / `Missing Input` and the agent moves on.
3. **Open Flipkart** - one browser session is opened and reused for every
   row. Logs in only if not already logged in.
4. **Search Order** - looks up the order by Order ID. Not found ->
   `Human Review` / `Order Not Found`.
5. **Locate Product** - finds the item by SKU. Not found -> `Human Review` /
   `SKU Not Found`.
6. **Check eligibility** - Eligible / Already Returned / Out of Window.
   The last two are written to Excel as completed (no return needed) and the
   agent moves on.
7. **Complete the return** - for eligible items: selects Return Reason,
   Refund Method, Pickup Option, and confirms.
8. **Capture results** - Return ID, Refund Amount, Return Status.
9. **Update Excel immediately** - every row is saved to disk as soon as it's
   processed, never batched until the end.
10. **Repeat** until no pending rows remain.

If anything unexpected happens (captcha, unexpected UI, OTP timeout, browser
crash) the agent **never retries endlessly** - it writes the reason to the
`Reason` column, sets `Task Status = Human Review`, and continues with the
next row.

### Retry logic (temporary failures only)

A small, separate class of failures is treated as *temporary* rather than
permanent, and gets retried automatically before giving up:

- Network timeouts
- Playwright timeouts (slow/stuck pages, elements that never appear)
- Expired sessions (Flipkart silently logs the session out mid-run)

These are retried up to `config.MAX_RETRIES` (default 3) times, with a
`config.RETRY_DELAY_SECONDS` pause between attempts. An expired session
triggers a fresh login before the next attempt. If all attempts are
exhausted, the row is marked `Task Status = Failed` (kept separate from
`Human Review`, since it's an infrastructure issue, not a data/UI problem
a human needs to look at).

Permanent failures - captcha, missing input, order/SKU not found, OTP
timeout, unexpected UI - are **never** retried; they go straight to
`Human Review` on the first occurrence, exactly as before.

### Run summary

At the end of every run, a summary is logged and printed:

```
===== RUN SUMMARY =====
Total Tasks:      5
Completed:        2
Already Returned: 0
Out of Window:    1
Human Review:     1
Failed:           1
Execution Time:   0m 42s
========================
```

## Project structure

```
return-agent/
├── main.py               # Orchestrates the full workflow
├── excel_handler.py       # Reads/writes the Excel sheet (openpyxl)
├── flipkart_handler.py    # All Playwright/Flipkart browser logic
├── logger.py               # Timestamped logging setup
├── config.py                # All settings, column names, statuses, timing
├── requirements.txt
├── sample_returns.xlsx     # Sample input sheet
└── README.md
```

## Setup

```bash
pip install -r requirements.txt
playwright install chromium
```

Set your Flipkart credentials as environment variables (never hardcode them):

```bash
export FLIPKART_USERNAME="your_email_or_phone"
export FLIPKART_PASSWORD="your_password"
```

If Flipkart uses OTP login instead of password login, the agent will pause
and wait (up to `OTP_WAIT_TIMEOUT_SECONDS` in `config.py`) for you to type the
OTP into the browser window manually.

## Running

```bash
python main.py
```

The agent will:
- Open a visible Chromium window (set `HEADLESS = True` in `config.py` to
  run headless once selectors are confirmed against the live site).
- Process every `Pending` row in `sample_returns.xlsx`.
- Update the sheet after every single row.
- Log every action, with timestamps, to both the console and `agent.log`.

## Excel columns

| Column | Meaning |
|---|---|
| Platform | Marketplace name (only `Flipkart` is automated in this MVP) |
| Order ID | Order to search for |
| SKU | Item within the order |
| Task Status | `Pending` / `Completed` / `Human Review` |
| Reason | Filled in only for Human Review rows |
| Return ID | Captured from Flipkart after a successful return |
| Return Status | e.g. `Refund Processed`, `Already Returned`, `Out of Window` |
| Refund Amount | Captured from Flipkart |
| Timestamp | When the row was last updated |

## Notes on selectors

The CSS/text selectors in `flipkart_handler.py` are written to match
Flipkart's typical page structure, but marketplace UIs change over time.
Before running against the live site, verify/update the selectors using:

```bash
playwright codegen flipkart.com
```

## Human Review reasons

The agent writes one of these into the `Reason` column whenever it stops
working on a row instead of retrying:

- `Missing Input`
- `Order Not Found`
- `SKU Not Found`
- `Captcha`
- `Unexpected UI`
- `OTP Timeout`
- `Browser Failure`
- `Unsupported Platform` (row names a platform other than Flipkart)

Separately, a row that exhausts all retry attempts on a *temporary* failure
(network timeout, Playwright timeout, expired session) is marked
`Task Status = Failed` with `Reason = Max Retries Exceeded (Temporary Failure)`
instead of Human Review - see "Retry logic" above.

## Design notes (why it's kept simple)

- No database, no queue, no retries with backoff - just a straightforward
  loop over Excel rows.
- One browser session reused across rows (via `context.storage_state`) so
  the agent doesn't log in over and over.
- Every row is saved to Excel the moment it's processed, so a crash midway
  through never loses completed work.
- All "magic values" (column names, statuses, timing, URLs) live in
  `config.py` so behaviour can be tuned without touching the logic.
