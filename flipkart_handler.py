"""
flipkart_handler.py
--------------------
All Playwright / Flipkart browser interactions live here.

NOTE ON SELECTORS:
This is an MVP prototype. Flipkart's actual DOM/selectors change often and
require live inspection to get exactly right. The selectors below are
written as clearly-labeled placeholders (CSS/text selectors that follow
Flipkart's typical page structure) so the workflow logic, error handling,
and Human Review behaviour are all correct and easy to wire up to the real
selectors after inspecting the live site with Playwright Inspector
(`playwright codegen flipkart.com`).
"""

import os
import time
from playwright.sync_api import (
    sync_playwright,
    TimeoutError as PlaywrightTimeoutError,
    Error as PlaywrightError,
)

import config
from logger import get_logger

logger = get_logger()


# ---------- Custom exceptions ----------
# These let flipkart_handler tell main.py exactly why it stopped, so main.py
# can write the right "Reason" into Excel and move to the next row.

class CaptchaDetected(Exception):
    """Raised when a captcha is shown. Agent must never try to bypass it."""
    pass


class OrderNotFound(Exception):
    pass


class SkuNotFound(Exception):
    pass


class OtpTimeout(Exception):
    pass


class UnexpectedUI(Exception):
    pass


class BrowserFailure(Exception):
    pass


class SessionExpired(Exception):
    """
    Raised when a session that was previously logged in becomes invalid
    mid-task (e.g. Flipkart redirects back to the login page). This is a
    TEMPORARY failure - the caller retries by logging in again, unlike the
    permanent failures above which go straight to Human Review.
    """
    pass


class FlipkartHandler:
    def __init__(self):
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None

    # ---------------------------------------------------------------
    # Browser lifecycle
    # ---------------------------------------------------------------
    def start_browser(self):
        """
        Launch the browser once and reuse it for every row.
        If a saved session (storage_state) exists, load it so we can skip
        login when the session is still valid.
        """
        try:
            self.playwright = sync_playwright().start()
            self.browser = self.playwright.chromium.launch(headless=config.HEADLESS)

            if os.path.exists(config.BROWSER_STATE_FILE):
                self.context = self.browser.new_context(
                    storage_state=config.BROWSER_STATE_FILE
                )
                logger.info("Opened Browser (reused saved session)")
            else:
                self.context = self.browser.new_context()
                logger.info("Opened Browser (new session)")

            self.page = self.context.new_page()

            # Explicit timeouts so slow/stuck pages fail fast and predictably
            # with a PlaywrightTimeoutError (which main.py retries) instead
            # of hanging indefinitely.
            self.page.set_default_timeout(config.ELEMENT_TIMEOUT_MS)
            self.page.set_default_navigation_timeout(config.NAVIGATION_TIMEOUT_MS)
        except Exception as e:
            raise BrowserFailure(f"Failed to start browser: {e}")

    def close_browser(self):
        """Save session state and close everything cleanly."""
        try:
            if self.context:
                self.context.storage_state(path=config.BROWSER_STATE_FILE)
                logger.info("Login successful.")
                logger.info("Browser session saved.")
                self.context.close()
            if self.browser:
                self.browser.close()
            if self.playwright:
                self.playwright.stop()
        except Exception as e:
            logger.error(f"Error while closing browser: {e}")

    def _delay(self):
        """Small delay between actions so the site behaves like a real user."""
        time.sleep(config.ACTION_DELAY_SECONDS)

    def _check_for_captcha(self):
        """
        Check the current page for a captcha. If found, stop immediately -
        the agent must never attempt to bypass it.
        """
        captcha_locator = self.page.locator("text=/captcha/i")
        if captcha_locator.count() > 0:
            raise CaptchaDetected("Captcha detected on page.")

    # ---------------------------------------------------------------
    # Login
    # ---------------------------------------------------------------
    def is_logged_in(self) -> bool:
        """
        Checks whether the user is already logged in.
        Instead of looking for a specific username or greeting,
        simply verify that Flipkart has not redirected us back
        to the login page.
        """

        self.page.goto(config.FLIPKART_ORDERS_URL)
        self._delay()
        self._check_for_captcha()

        return "login" not in self.page.url.lower()

    def login(self):
        """
        Manual login flow for the MVP.

        Flipkart's login UI (password vs OTP vs captcha challenges) changes
        too often to automate reliably, so instead of scripting the form we
        open the login page and let a human complete login in the visible
        browser window - then verify the result once they confirm it's done.
        """
        logger.info("Login required. Starting login flow.")
        self.page.goto(config.FLIPKART_LOGIN_URL)
        self._delay()
        self._check_for_captcha()

        print("Please complete the Flipkart login manually in the opened browser.")
        print("\nComplete the login in the browser window.")
        input("After you reach the Flipkart homepage, press ENTER...")

        if not self.is_logged_in():
            raise UnexpectedUI("Login could not be verified.")

        # Save the session so future runs can skip login entirely.
        self.context.storage_state(path=config.BROWSER_STATE_FILE)
        logger.info("Session saved.")

    # ---------------------------------------------------------------
    # Order / SKU / Eligibility / Return flow
    # ---------------------------------------------------------------
    def search_order(self, order_id: str):
        """Search for the order using its Order ID on the Orders page."""
        self.page.goto(config.FLIPKART_ORDERS_URL)
        self._delay()
        self._check_for_captcha()

        # A session that was valid at login time can still expire mid-run
        # (token expiry, server-side logout, etc). If we land back on the
        # login page here, treat it as a temporary failure so main.py can
        # log in again and retry this row.
        if "login" in self.page.url.lower():
            raise SessionExpired("Session expired - redirected to login while searching for order.")

        search_box = self.page.locator("input[placeholder*='Search your orders']")
        if search_box.count() == 0:
            raise UnexpectedUI("Order search box not found.")

        search_box.first.fill(order_id)
        search_box.first.press("Enter")
        self._delay()
        self._check_for_captcha()

        order_card = self.page.locator(f"text={order_id}")
        if order_card.count() == 0:
            raise OrderNotFound(f"Order {order_id} not found.")

        order_card.first.click()
        self._delay()
        logger.info(f"Found Order: {order_id}")

    def locate_product(self, sku: str):
        """On the Order Details page, confirm the SKU is present."""
        self._check_for_captcha()

        product_locator = self.page.locator(f"text={sku}")
        if product_locator.count() == 0:
            raise SkuNotFound(f"SKU {sku} not found in order.")

        logger.info(f"Found SKU: {sku}")

    def check_return_eligibility(self) -> str:
        """
        Inspect the Order Details page for the return eligibility status.
        Returns one of: config.ELIGIBLE / config.ALREADY_RETURNED / config.OUT_OF_WINDOW
        """
        self._check_for_captcha()

        if self.page.locator("text=/already returned/i").count() > 0:
            return config.ALREADY_RETURNED

        if self.page.locator("text=/return window.*closed|out of window/i").count() > 0:
            return config.OUT_OF_WINDOW

        if self.page.locator("button:has-text('Return')").count() > 0:
            return config.ELIGIBLE

        raise UnexpectedUI("Could not determine return eligibility from page.")

    def complete_return(self) -> dict:
        """
        Runs through the return flow:
        Select Return Reason -> Refund Method -> Pickup Option -> Confirm Return.
        Returns a dict with Return ID, Refund Amount and Return Status.
        """
        self._check_for_captcha()

        # Click "Return" to start the flow.
        self.page.locator("button:has-text('Return')").first.click()
        self._delay()
        self._check_for_captcha()

        # Select return reason.
        reason_option = self.page.locator(f"text={config.DEFAULT_RETURN_REASON}")
        if reason_option.count() == 0:
            raise UnexpectedUI("Return reason option not found.")
        reason_option.first.click()
        self._delay()

        # Select refund method.
        refund_option = self.page.locator(f"text={config.DEFAULT_REFUND_METHOD}")
        if refund_option.count() == 0:
            raise UnexpectedUI("Refund method option not found.")
        refund_option.first.click()
        self._delay()

        # Select pickup option.
        pickup_option = self.page.locator(f"text={config.DEFAULT_PICKUP_OPTION}")
        if pickup_option.count() == 0:
            raise UnexpectedUI("Pickup option not found.")
        pickup_option.first.click()
        self._delay()

        # Confirm return.
        confirm_button = self.page.locator("button:has-text('Confirm Return')")
        if confirm_button.count() == 0:
            raise UnexpectedUI("Confirm Return button not found.")
        confirm_button.first.click()
        self._delay()
        self._check_for_captcha()

        logger.info("Placed Return")

        # Capture confirmation details from the confirmation page.
        return self._capture_return_confirmation()

    def _capture_return_confirmation(self) -> dict:
        """Read Return ID / Refund Amount / Return Status off the confirmation page."""
        try:
            return_id_locator = self.page.locator("text=/Return ID[:\\s]*\\S+/i")
            refund_locator = self.page.locator("text=/Refund Amount[:\\s]*₹?\\S+/i")
            status_locator = self.page.locator("text=/Return Status[:\\s]*\\S+/i")

            return_id_text = return_id_locator.first.inner_text() if return_id_locator.count() > 0 else "Unknown"
            refund_text = refund_locator.first.inner_text() if refund_locator.count() > 0 else "Unknown"
            status_text = status_locator.first.inner_text() if status_locator.count() > 0 else "Return Initiated"

            return {
                "return_id": return_id_text,
                "refund_amount": refund_text,
                "return_status": status_text,
            }
        except Exception as e:
            raise UnexpectedUI(f"Could not capture return confirmation details: {e}")
