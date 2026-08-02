"""
main.py
-------
Entry point. Orchestrates the full workflow described in the product spec:

1. Read Excel, find Pending rows.
2. Validate required fields.
3. Open Flipkart (reuse browser session, login if needed).
4. Search order by Order ID.
5. Locate product by SKU.
6. Check return eligibility.
7. If eligible, complete the return flow.
8. Capture Return ID / Refund Amount / Return Status.
9. Update Excel immediately (never wait until all rows finish).
10. Move to next pending row.

The agent never endlessly retries - any failure is written to Excel as
"Human Review" with a clear reason, and the agent moves on.
"""

import config
from excel_handler import ExcelHandler
from flipkart_handler import (
    FlipkartHandler,
    CaptchaDetected,
    OrderNotFound,
    SkuNotFound,
    OtpTimeout,
    UnexpectedUI,
    BrowserFailure,
)
from logger import get_logger

logger = get_logger()


def process_row(excel: ExcelHandler, flipkart: FlipkartHandler, row: dict):
    """Run the full return workflow for a single Excel row."""
    row_num = row["row_num"]
    platform = row["platform"]
    order_id = row["order_id"]
    sku = row["sku"]

    # ---- Step 2: validate required fields ----
    if not platform or not order_id or not sku:
        excel.mark_human_review(row_num, config.REASON_MISSING_INPUT)
        return

    # This MVP only automates Flipkart. Any other platform in the sheet
    # is out of scope and goes to Human Review rather than being silently skipped.
    if platform.strip().lower() != "flipkart":
        excel.mark_human_review(row_num, "Unsupported Platform")
        return

    # ---- Steps 3-8: browser workflow ----
    # Any exception raised below is a known, expected failure mode
    # (captcha, order/SKU not found, OTP timeout, unexpected UI, browser
    # failure) and is handled by the except blocks in run().
    if not flipkart.is_logged_in():
        flipkart.login()

    flipkart.search_order(order_id)
    flipkart.locate_product(sku)

    eligibility = flipkart.check_return_eligibility()

    if eligibility == config.ALREADY_RETURNED:
        excel.update_row(
            row_num,
            task_status=config.STATUS_COMPLETED,
            return_status=config.ALREADY_RETURNED,
            set_timestamp=True,
        )
        logger.info(f"Row {row_num}: item already returned. Task Complete.")
        return

    if eligibility == config.OUT_OF_WINDOW:
        excel.update_row(
            row_num,
            task_status=config.STATUS_COMPLETED,
            return_status=config.OUT_OF_WINDOW,
            set_timestamp=True,
        )
        logger.info(f"Row {row_num}: return window closed. Task Complete.")
        return

    # eligibility == config.ELIGIBLE -> run the return flow
    result = flipkart.complete_return()

    # ---- Step 9: update Excel immediately ----
    excel.update_row(
        row_num,
        task_status=config.STATUS_COMPLETED,
        return_id=result["return_id"],
        return_status=result["return_status"],
        refund_amount=result["refund_amount"],
        set_timestamp=True,
    )
    logger.info(f"Task Complete for row {row_num}")


def run():
    logger.info("Started Task")

    excel = ExcelHandler()
    pending_rows = excel.get_pending_rows()

    if not pending_rows:
        logger.info("No pending tasks found. Nothing to do.")
        return

    flipkart = FlipkartHandler()
    browser_started = False

    # ---- Step 10: loop until no pending tasks remain ----
    for row in pending_rows:
        row_num = row["row_num"]
        try:
            # Fields might be missing - validate before touching the browser
            # so we don't open a browser session just to reject the row.
            if not row["platform"] or not row["order_id"] or not row["sku"]:
                excel.mark_human_review(row_num, config.REASON_MISSING_INPUT)
                continue

            # Open the browser only once, the first time it's actually needed,
            # and reuse it for every row after that.
            if not browser_started:
                flipkart.start_browser()
                browser_started = True

            process_row(excel, flipkart, row)

        except CaptchaDetected:
            logger.error(f"Row {row_num}: captcha detected. Stopping this row.")
            excel.mark_human_review(row_num, config.REASON_CAPTCHA)

        except OrderNotFound:
            excel.mark_human_review(row_num, config.REASON_ORDER_NOT_FOUND)

        except SkuNotFound:
            excel.mark_human_review(row_num, config.REASON_SKU_NOT_FOUND)

        except OtpTimeout:
            excel.mark_human_review(row_num, config.REASON_OTP_TIMEOUT)

        except UnexpectedUI as e:
            logger.error(f"Row {row_num}: unexpected UI - {e}")
            excel.mark_human_review(row_num, config.REASON_UNEXPECTED_UI)

        except BrowserFailure as e:
            # Browser itself is broken - no point continuing to the next row.
            logger.error(f"Browser failure: {e}")
            excel.mark_human_review(row_num, config.REASON_BROWSER_FAILURE)
            break

        except Exception as e:
            # Catch-all safety net: never crash the whole run because of one
            # row. Log it, mark for human review, and move on.
            logger.error(f"Row {row_num}: unexpected error - {e}")
            excel.mark_human_review(row_num, config.REASON_UNEXPECTED_UI)

    if browser_started:
        flipkart.close_browser()
        logger.info("Closed Browser")

    logger.info("All pending tasks processed. Task Complete.")


if __name__ == "__main__":
    run()
