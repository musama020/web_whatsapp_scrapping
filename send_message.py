from botasaurus.browser import browser, Driver
from botasaurus.user_agent import UserAgent
from botasaurus.window_size import WindowSize
import time

# --- Configure what to send and to whom ---
TARGET_CONTACT = "Muhammad Saim Byteforge"
MESSAGE_TO_SEND = "Hello from the automation script!"


@browser(
    profile="whatsapp",
    # HASHED keeps the fingerprint consistent across every run for this profile.
    # An inconsistent user agent between sessions is the usual cause of WhatsApp's
    # "A database error occurred on your browser. Please relink your device." error.
    user_agent=UserAgent.HASHED,
    window_size=WindowSize.HASHED,
)
def send_whatsapp_message(driver: Driver, data):
    # Allow the contact/message to be passed in via `data` (e.g. from the
    # scheduler). Fall back to the module-level constants when run directly.
    data = data or {}
    target_contact = data.get("contact", TARGET_CONTACT)
    message_to_send = data.get("message", MESSAGE_TO_SEND)

    driver.get("https://web.whatsapp.com")

    print("--- ACTION REQUIRED ---")
    print("Please scan the QR code in the browser window (if not already logged in).")
    print("The script will wait until the search bar is visible...")

    search_selector = 'input[placeholder="Search or start a new chat"]'

    try:
        driver.wait_for_element(search_selector, wait=120)
    except Exception as e:
        print(f"Timeout: Could not detect login. ({e})")
        return None

    print("Login detected! Starting automation...")
    time.sleep(2)

    # --- Search for the contact ---
    driver.type(search_selector, target_contact)
    time.sleep(3)
    print(f"Searching for {target_contact}...")

    # Click the search-result row by matching the contact's name (same proven
    # approach as the scraper: find span[title=<name>] and click its clickable row).
    click_js = r"""
    var target = args.name;
    var spans = document.querySelectorAll('span[title]');
    for (var i = 0; i < spans.length; i++) {
        var t = spans[i].getAttribute('title') || '';
        if (t === target || t.indexOf(target) !== -1) {
            var row = spans[i].closest('div[role="listitem"]')
                   || spans[i].closest('[role="button"]')
                   || spans[i].closest('div[tabindex]');
            if (row) { row.click(); return 'CLICKED:' + t; }
        }
    }
    return 'NOT_FOUND';
    """
    click_result = driver.run_js(click_js, {"name": target_contact})
    print(f"Found contact, click result: {click_result}")

    if click_result == "NOT_FOUND":
        print("Could not find contact in search results")
        return None

    time.sleep(3)

    # --- Verify the conversation actually opened ---
    header_text = driver.run_js(
        "var h = document.querySelector('header');"
        "return h ? h.innerText : '';"
    )
    print(f"Header after click: {header_text!r}")
    if target_contact not in (header_text or ""):
        # Fallback: press Enter in the search box to open the first result.
        print("Chat not open yet — pressing Enter in search box as fallback...")
        driver.run_js(
            "var s = document.querySelector('div[contenteditable=\"true\"][data-tab=\"3\"]')"
            " || document.querySelector('input[placeholder=\"Search or start a new chat\"]');"
            "if (s) { s.focus(); }"
        )
        time.sleep(1)
        driver.run_js(
            "var ev = new KeyboardEvent('keydown', {key:'Enter', code:'Enter', keyCode:13, which:13, bubbles:true});"
            "(document.activeElement || document.body).dispatchEvent(ev);"
        )
        time.sleep(3)
        header_text = driver.run_js(
            "var h = document.querySelector('header'); return h ? h.innerText : '';"
        )
        print(f"Header after fallback: {header_text!r}")

    # --- Type the message into the compose box ---
    # The compose input is a contenteditable div, NOT a normal input. The stable
    # selector is data-testid="conversation-compose-box-input".
    compose_selector = 'div[contenteditable="true"][data-testid="conversation-compose-box-input"]'

    compose_box = driver.select(compose_selector, wait=10)
    if not compose_box:
        # Fallback to the data-tab="10" contenteditable if testid changes
        compose_selector = 'div[contenteditable="true"][data-tab="10"]'
        compose_box = driver.select(compose_selector, wait=5)

    if not compose_box:
        print("Could not find the message input box.")
        return None

    print(f"Typing message: {message_to_send}")
    compose_box.click()
    time.sleep(0.5)
    # driver.type works on contenteditable; it dispatches real key events so
    # WhatsApp's Lexical editor registers the text and enables the Send button.
    driver.type(compose_selector, message_to_send)
    time.sleep(1)

    # --- Click the Send button ---
    # After typing, the mic button turns into a Send button (aria-label="Send").
    send_button = driver.select('button[aria-label="Send"]', wait=5)
    if send_button:
        print("Clicking Send button...")
        send_button.click()
    else:
        # Fallback: press Enter to send (WhatsApp sends on Enter by default).
        print("Send button not found — pressing Enter to send...")
        driver.run_js(
            "var box = document.querySelector(args.sel);"
            "if (box) {"
            "  box.focus();"
            "  var ev = new KeyboardEvent('keydown', {key:'Enter', code:'Enter', keyCode:13, which:13, bubbles:true});"
            "  box.dispatchEvent(ev);"
            "}",
            {"sel": compose_selector},
        )

    time.sleep(2)
    print("--- MESSAGE SENT ---")

    # When run interactively, pause so you can confirm. The scheduler passes
    # headless=True (or any truthy "unattended") to skip the blocking prompt.
    if not data.get("unattended"):
        print("Pausing for inspection. Press Enter in the terminal to close.")
        driver.prompt()

    return {"contact": target_contact, "message": message_to_send, "status": "sent"}


if __name__ == "__main__":
    send_whatsapp_message()
