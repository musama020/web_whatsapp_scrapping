from botasaurus.browser import browser, Driver
from botasaurus.user_agent import UserAgent
from botasaurus.window_size import WindowSize
import time

TARGET_CONTACT = "Muhammad Saim Byteforge"
SCROLL_UP_COUNT = 15

@browser(
    profile="whatsapp",
    # HASHED keeps the fingerprint consistent across every run for this profile.
    # An inconsistent user agent between sessions is the usual cause of WhatsApp's
    # "A database error occurred on your browser. Please relink your device." error.
    user_agent=UserAgent.HASHED,
    window_size=WindowSize.HASHED,
)
def scrape_whatsapp(driver: Driver, data):
    driver.get("https://web.whatsapp.com")

    print("--- ACTION REQUIRED ---")
    print("Please scan the QR code in the browser window.")
    print("The script will wait until the search bar is visible...")

    search_selector = 'input[placeholder="Search or start a new chat"]'

    try:
        driver.wait_for_element(search_selector, wait=120)
    except Exception as e:
        print(f"Timeout: Could not detect login. ({e})")
        return None

    print("Login detected! Starting automation...")
    time.sleep(2)

    driver.type(search_selector, TARGET_CONTACT)
    time.sleep(3)

    print(f"Searching for {TARGET_CONTACT}...")

    # Click the search-result row by matching the contact's name. The previous
    # approach (div.x1iyjqo2) found an element but clicking it did not open the
    # chat. Here we find the span[title=<name>] and click its clickable parent row.
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
    click_result = driver.run_js(click_js, {"name": TARGET_CONTACT})
    print(f"Found contact, click result: {click_result}")

    if click_result == "NOT_FOUND":
        print("Could not find contact in search results")
        return None

    time.sleep(3)

    # Verify the conversation actually opened (header shows the contact name).
    header_text = driver.run_js(
        "var h = document.querySelector('header');"
        "return h ? h.innerText : '';"
    )
    print(f"Header after click: {header_text!r}")
    if TARGET_CONTACT not in (header_text or ""):
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

    print("Chat opened. Pausing for inspection...")
    driver.prompt()

    scraped_messages = []
    seen_ids = set()

    print("Starting message extraction and scrolling...")

    for i in range(SCROLL_UP_COUNT):
        # Get all message containers with copyable-text
        message_elements = driver.select_all("div.copyable-text")
        print(f"Cycle {i+1}: Found {len(message_elements)} message elements")

        for msg in message_elements:
            try:
                # Get metadata from data-pre-plain-text attribute
                meta_data = msg.get_attribute("data-pre-plain-text")

                # Get text from span[data-testid="selectable-text"]
                text_span = msg.select("span[data-testid='selectable-text']", wait=None)
                text_content = text_span.text if text_span else ""

                if meta_data and text_content:
                    unique_id = f"{meta_data}_{text_content}"

                    if unique_id not in seen_ids:
                        seen_ids.add(unique_id)
                        scraped_messages.append({
                            "timestamp_info": meta_data.strip(),
                            "message": text_content.strip()
                        })
                        print(f"  → Scraped: {text_content[:50]}")
            except Exception as e:
                continue

        # Scroll up in the message container to load older messages
        scroll_result = driver.run_js(
            "var container = document.querySelector('div[tabindex=\"0\"][class*=\"x3psx0u\"]');"
            "if (container) { container.scrollTop -= 1000; return true; }"
            "return false;"
        )

        print(f"Scroll cycle {i+1}/{SCROLL_UP_COUNT} complete. Collected: {len(scraped_messages)}")
        time.sleep(1)

    print(f"--- SUCCESS ---")
    print(f"Total messages scraped: {len(scraped_messages)}")
    return scraped_messages

if __name__ == "__main__":
    scrape_whatsapp()
