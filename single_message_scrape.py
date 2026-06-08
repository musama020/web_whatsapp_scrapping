from botasaurus.browser import browser, Driver
import time

TARGET_CONTACT = "Muhammad Saim Byteforge"
SCROLL_UP_COUNT = 15

@browser(profile="whatsapp")
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

    first_result = driver.select('div.x1iyjqo2', wait=5)
    if first_result:
        print(f"Found contact, clicking...")
        first_result.click()
        time.sleep(3)
    else:
        print("Could not find contact in search results")
        return None

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
