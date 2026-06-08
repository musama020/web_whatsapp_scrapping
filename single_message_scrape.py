from botasaurus.browser import browser, Driver
from botasaurus.user_agent import UserAgent
from botasaurus.window_size import WindowSize
import time

TARGET_CONTACT = "Family Group"
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

    # JS that walks every message bubble (anchored on data-pre-plain-text) and
    # classifies it: text, image, video, audio/voice, document, sticker, or gif.
    # WhatsApp does not expose downloadable file URLs (media is encrypted), so for
    # non-text messages we capture type + any available label (filename, duration,
    # caption) instead of the file itself.
    extract_js = r"""
    var out = [];
    var nodes = document.querySelectorAll('div.copyable-text[data-pre-plain-text]');
    nodes.forEach(function(node) {
        var meta = node.getAttribute('data-pre-plain-text') || '';
        if (!meta) return;

        // The whole message bubble (climb up from the copyable-text anchor)
        var bubble = node.closest('[data-testid="msg-container"]') || node;

        var type = 'text';
        var content = '';
        var extra = {};

        // --- text ---
        var span = node.querySelector('span[data-testid="selectable-text"]');
        var text = span ? (span.innerText || '') : '';

        // --- audio / voice note ---
        if (bubble.querySelector('audio') ||
            bubble.querySelector('[data-icon="audio-play"], [data-icon="ptt-play"], [aria-label*="oice message"]')) {
            type = 'audio';
            // duration usually shown as 0:12 style text
            var durEl = bubble.querySelector('div[aria-label] ~ div, span');
            content = '[audio/voice message]';
        }
        // --- document / file ---
        else if (bubble.querySelector('[data-icon="document"], [data-icon^="document"]') ||
                 bubble.querySelector('[title][role="button"] [data-icon*="document"]')) {
            type = 'document';
            // filename is typically a title span in the document bubble
            var fnEl = bubble.querySelector('span[title]');
            var fname = fnEl ? fnEl.getAttribute('title') : '';
            content = '[document]' + (fname ? ' ' + fname : '');
            extra.filename = fname;
        }
        // --- image ---
        else if (bubble.querySelector('img[src^="blob:"]') ||
                 bubble.querySelector('div[aria-label="Open picture"], [data-icon="media-download"]')) {
            type = 'image';
            content = '[image]' + (text.trim() ? ' caption: ' + text : '');
            extra.caption = text.trim();
        }
        // --- video ---
        else if (bubble.querySelector('video') ||
                 bubble.querySelector('[data-icon="media-play"], span[data-icon="video-call"]')) {
            type = 'video';
            content = '[video]' + (text.trim() ? ' caption: ' + text : '');
            extra.caption = text.trim();
        }
        // --- sticker / gif ---
        else if (bubble.querySelector('[data-icon="media-gif"]')) {
            type = 'gif';
            content = '[gif]';
        }
        // --- plain text ---
        else if (text.trim()) {
            type = 'text';
            content = text;
        }
        // --- emoji-only fallback ---
        else {
            var emoji = node.querySelector('[data-plain-text]');
            if (emoji) { type = 'text'; content = emoji.getAttribute('data-plain-text') || ''; }
        }

        if (content) {
            out.push({ meta: meta, type: type, content: content, extra: extra });
        }
    });
    return out;
    """

    for i in range(SCROLL_UP_COUNT):
        rows = driver.run_js(extract_js) or []
        print(f"Cycle {i+1}: Found {len(rows)} message elements")

        for row in rows:
            try:
                meta_data = row.get("meta", "")
                msg_type = row.get("type", "text")
                content = row.get("content", "")
                extra = row.get("extra", {}) or {}

                if not (meta_data and content):
                    continue

                unique_id = f"{meta_data}_{content}"
                if unique_id not in seen_ids:
                    seen_ids.add(unique_id)
                    entry = {
                        "timestamp_info": meta_data.strip(),
                        "type": msg_type,
                        "message": content.strip(),
                    }
                    # only attach extra fields that have a value
                    for k, v in extra.items():
                        if v:
                            entry[k] = v
                    scraped_messages.append(entry)
                    print(f"  → [{msg_type}] {content.strip()[:50]}")
            except Exception:
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
