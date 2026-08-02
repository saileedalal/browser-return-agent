"""
config.py
---------
Central place for all settings used across the project.
Keeping everything here means no magic numbers/strings scattered in the code.
"""

# ---------- File paths ----------
EXCEL_FILE_PATH = "sample_returns.xlsx"
SHEET_NAME = "Returns"
LOG_FILE_PATH = "agent.log"

# Where Playwright keeps the logged-in browser session (cookies, storage etc.)
# Reusing this file lets the agent skip login on the next run if session is still valid.
BROWSER_STATE_FILE = "browser_state.json"

# ---------- Excel column names (must match header row exactly) ----------
COL_PLATFORM = "Platform"
COL_ORDER_ID = "Order ID"
COL_SKU = "SKU"
COL_TASK_STATUS = "Task Status"
COL_REASON = "Reason"
COL_RETURN_ID = "Return ID"
COL_RETURN_STATUS = "Return Status"
COL_REFUND_AMOUNT = "Refund Amount"
COL_TIMESTAMP = "Timestamp"

# ---------- Task status values ----------
STATUS_PENDING = "Pending"
STATUS_HUMAN_REVIEW = "Human Review"
STATUS_COMPLETED = "Completed"

# ---------- Human review reasons ----------
REASON_MISSING_INPUT = "Missing Input"
REASON_ORDER_NOT_FOUND = "Order Not Found"
REASON_SKU_NOT_FOUND = "SKU Not Found"
REASON_CAPTCHA = "Captcha"
REASON_UNEXPECTED_UI = "Unexpected UI"
REASON_OTP_TIMEOUT = "OTP Timeout"
REASON_BROWSER_FAILURE = "Browser Failure"

# ---------- Return eligibility outcomes ----------
ELIGIBLE = "Eligible"
ALREADY_RETURNED = "Already Returned"
OUT_OF_WINDOW = "Out of Window"

# ---------- Flipkart URLs ----------
FLIPKART_LOGIN_URL = "https://www.flipkart.com/account/login"
FLIPKART_ORDERS_URL = "https://www.flipkart.com/account/orders"

# ---------- Credentials ----------
# NOTE: For an MVP we simply read credentials from environment variables.
# Never hardcode real credentials in source code.
import os
FLIPKART_USERNAME = os.environ.get("FLIPKART_USERNAME", "")
FLIPKART_PASSWORD = os.environ.get("FLIPKART_PASSWORD", "")

# ---------- Return flow defaults ----------
# For the MVP we pick simple defaults. In a real product these could come
# from the Excel sheet itself (extra columns) or a config file.
DEFAULT_RETURN_REASON = "Item defective / not working"
DEFAULT_REFUND_METHOD = "Original payment method"
DEFAULT_PICKUP_OPTION = "Schedule pickup"

# ---------- Timing ----------
# Small delay (seconds) between UI actions so the site behaves like a real user
# and elements have time to render before the next interaction.
ACTION_DELAY_SECONDS = 1.5

# How long (ms) Playwright should wait for an element before giving up.
ELEMENT_TIMEOUT_MS = 30000
NAVIGATION_TIMEOUT_MS = 60000
ACTION_DELAY_SECONDS = 2
HEADLESS = False

# How long (seconds) to wait for the user to solve an OTP manually before
# giving up and marking the row for Human Review.
OTP_WAIT_TIMEOUT_SECONDS = 90

# ---------- Browser ----------
HEADLESS = False  # Keep visible for MVP so behaviour is easy to observe/debug.
