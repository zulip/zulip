import {strict as assert} from "assert";
import "css.escape";
import path from "path";
import timersPromises from "timers/promises";

import ErrorStackParser from "error-stack-parser";
import type {Browser, ConsoleMessage, ConsoleMessageLocation, ElementHandle, Page} from "puppeteer";
import puppeteer from "puppeteer";
import StackFrame from "stackframe";
import StackTraceGPS from "stacktrace-gps";

import {test_credentials} from "../../../var/puppeteer/test_credentials";

const root_dir = path.resolve(__dirname, "../../..");
const puppeteer_dir = path.join(root_dir, "var/puppeteer");

type Message = Record<string, string | boolean> & {
    recipient?: string;
    content: string;
    stream_name?: string;
};

let browser: Browser | null = null;
let screenshot_id = 0;
export const is_firefox = process.env.PUPPETEER_PRODUCT === "firefox";
let realm_url = "http://zulip.zulipdev.com:9981/";
const gps = new StackTraceGPS({ajax: async (url) => (await fetch(url)).text()});

let last_current_msg_list_id: number | undefined;

export const pm_recipient = {
    async set(page: Page, recipient: string): Promise<void> {
        // Without using the delay option here there seems to be
        // a flake where the typeahead doesn't show up.
        await page.type("#private_message_recipient", recipient, {delay: 100});

        // We use [style*="display: block"] here to distinguish
        // the visible typeahead menu from the invisible ones
        // meant for something else; e.g., the direct message
        // input typeahead is different from the topic input
        // typeahead but both can be present in the DOM.
        const entry = await page.waitForSelector('.typeahead[style*="display: block"] .active a', {
            visible: false,
        });
        await entry!.click();
    },

    async expect(page: Page, expected: string): Promise<void> {
        const actual_recipients = await page.evaluate(() => zulip_test.private_message_recipient());
        assert.equal(actual_recipients, expected);
    },
};

export const fullname: Record<string, string> = {
    cordelia: "Cordelia, Lear's daughter",
    othello: "Othello, the Moor of Venice",
    hamlet: "King Hamlet",
};

export const window_size = {
    width: 1400,
    height: 1024,
};

export async function ensure_browser(): Promise<Browser> {
    if (browser === null) {
        browser = await puppeteer.launch({
            args: [
                `--window-size=${window_size.width},${window_size.height}`,
                "--no-sandbox",
                "--disable-setuid-sandbox",
            ],
            // TODO: Change defaultViewport to 1280x1024 when puppeteer fixes the window size issue with firefox.
            // Here is link to the issue that is tracking the above problem https://github.com/puppeteer/puppeteer/issues/6442.
            defaultViewport: null,
            headless: true,
        });
    }
    return browser;
}

export async function get_page(): Promise<Page> {
    const browser = await ensure_browser();
    const page = await browser.newPage();
    return page;
}

export async function screenshot(page: Page, name: string | null = null): Promise<void> {
    if (name === null) {
        name = `${screenshot_id}`;
        screenshot_id += 1;
    }

    const screenshot_path = path.join(puppeteer_dir, `${name}.png`);
    await page.screenshot({
        path: screenshot_path,
    });
}

export async function page_url_with_fragment(page: Page): Promise<string> {
    // `page.url()` does not include the url fragment when running
    // Puppeteer with Firefox: https://github.com/puppeteer/puppeteer/issues/6787.
    //
    // This function hacks around that issue; once it's fixed in
    // puppeteer upstream, we can delete this function and return
    // its callers to using `page.url()`
    return await page.evaluate(() => window.location.href);
}

// This function will clear the existing value of the element and
// replace it with the text.
export async function clear_and_type(page: Page, selector: string, text: string): Promise<void> {
    // Select all text currently in the element.
    await page.click(selector, {clickCount: 3});
    await page.keyboard.press("Delete");
    await page.type(selector, text);
}

/**
 * This function takes a params object whose fields
 * are referenced by name attribute of an input field and
 * the input as a key.
 *
 * For example to fill:
 *  <form id="#demo">
 *     <input type="text" name="username">
 *     <input type="checkbox" name="terms">
 *  </form>
 *
 * You can call:
 * common.fill_form(page, '#demo', {
 *     username: 'Iago',
 *     terms: true
 * });
 */
export async function fill_form(
    page: Page,
    form_selector: string,
    params: Record<string, boolean | string>,
): Promise<void> {
    async function is_dropdown(page: Page, name: string): Promise<boolean> {
        return (await page.$(`select[name="${CSS.escape(name)}"]`)) !== null;
    }
    for (const name of Object.keys(params)) {
        const value = params[name];
        if (typeof value === "boolean") {
            await page.$eval(
                `${form_selector} input[name="${CSS.escape(name)}"]`,
                (el, value) => {
                    if (el.checked !== value) {
                        el.click();
                    }
                },
                value,
            );
        } else if (await is_dropdown(page, name)) {
            if (typeof value !== "string") {
                throw new TypeError(`Expected string for ${name}`);
            }
            await page.select(`${form_selector} select[name="${CSS.escape(name)}"]`, value);
        } else {
            await clear_and_type(page, `${form_selector} [name="${CSS.escape(name)}"]`, value);
        }
    }
}

export async function check_form_contents(
    page: Page,
    form_selector: string,
    params: Record<string, boolean | string>,
): Promise<void> {
    for (const name of Object.keys(params)) {
        const expected_value = params[name];
        if (typeof expected_value === "boolean") {
            assert.equal(
                await page.$eval(
                    `${form_selector} input[name="${CSS.escape(name)}"]`,
                    (el) => el.checked,
                ),
                expected_value,
                "Form content is not as expected.",
            );
        } else {
            assert.equal(
                await page.$eval(`${form_selector} [name="${CSS.escape(name)}"]`, (el) => {
                    if (!(el instanceof HTMLInputElement || el instanceof HTMLTextAreaElement)) {
                        throw new TypeError("Expected <input> or <textarea>");
                    }
                    return el.value;
                }),
                expected_value,
                "Form content is not as expected.",
            );
        }
    }
}

export async function get_element_text(element: ElementHandle): Promise<string> {
    const text = await (await element.getProperty("innerText")).jsonValue();
    assert.ok(typeof text === "string");
    return text;
}

export async function get_text_from_selector(page: Page, selector: string): Promise<string> {
    const elements = await page.$$(selector);
    const texts = await Promise.all(elements.map(async (element) => get_element_text(element)));
    return texts.join("").trim();
}

export async function check_compose_state(
    page: Page,
    params: Record<string, string>,
): Promise<void> {
    const form_params: Record<string, string> = {content: params.content};
    if (params.stream_name) {
        assert.equal(
            await get_text_from_selector(
                page,
                "#compose_select_recipient_widget .dropdown_widget_value",
            ),
            params.stream_name,
        );
    }
    if (params.topic) {
        form_params.stream_message_recipient_topic = params.topic;
    }
    await check_form_contents(page, "form#send_message_form", form_params);
}

export function has_class_x(class_name: string): string {
    return `contains(concat(" ", @class, " "), " ${class_name} ")`;
}

export async function get_stream_id(page: Page, stream_name: string): Promise<number | undefined> {
    return await page.evaluate(
        (stream_name: string) => zulip_test.get_stream_id(stream_name),
        stream_name,
    );
}

export async function get_user_id_from_name(page: Page, name: string): Promise<number | undefined> {
    if (fullname[name] !== undefined) {
        name = fullname[name];
    }
    return await page.evaluate((name: string) => zulip_test.get_user_id_from_name(name), name);
}

export async function get_internal_email_from_name(
    page: Page,
    name: string,
): Promise<string | undefined> {
    if (fullname[name] !== undefined) {
        name = fullname[name];
    }
    return await page.evaluate((fullname: string) => {
        const user_id = zulip_test.get_user_id_from_name(fullname);
        return user_id === undefined ? undefined : zulip_test.get_person_by_user_id(user_id).email;
    }, name);
}

export async function log_in(
    page: Page,
    credentials: {username: string; password: string} | null = null,
): Promise<void> {
    console.log("Logging in");
    await page.goto(realm_url + "login/");
    assert.equal(realm_url + "login/", page.url());
    if (credentials === null) {
        credentials = test_credentials.default_user;
    }
    // fill login form
    const params = {
        username: credentials.username,
        password: credentials.password,
    };
    await fill_form(page, "form#login_form", params);
    await page.$eval("form#login_form", (form) => {
        form.submit();
    });

    await page.waitForSelector("#inbox-main", {visible: true});
}

export async function log_out(page: Page): Promise<void> {
    await page.goto(realm_url);
    const menu_selector = "#personal-menu";
    const logout_selector = ".personal-menu-actions a.logout_button";
    console.log("Logging out");
    await page.waitForSelector(menu_selector, {visible: true});
    await page.click(menu_selector);
    await page.waitForSelector(logout_selector);
    await page.click(logout_selector);

    // Wait for a email input in login page so we know login
    // page is loaded. Then check that we are at the login url.
    await page.waitForSelector('input[name="username"]');
    assert.ok(page.url().includes("/login/"));
}

export function set_realm_url(new_realm_url: string): void {
    realm_url = new_realm_url;
}

export async function ensure_enter_does_not_send(page: Page): Promise<void> {
    // NOTE: Caller should ensure that the compose box is already open.
    await page.click("#send_later");
    await page.waitForSelector("#send_later_popover");
    const enter_sends = await page.$eval(
        ".enter_sends_choice input[value='true']",
        (el) => el.checked,
    );

    if (enter_sends) {
        const enter_sends_false_selector = ".enter_sends_choice input[value='false']";
        await page.waitForSelector(enter_sends_false_selector);
        await page.click(enter_sends_false_selector);
    }
}

export async function assert_compose_box_content(
    page: Page,
    expected_value: string,
): Promise<void> {
    const compose_box_element = await page.waitForSelector("textarea#compose-textarea");
    assert(compose_box_element !== null);
    const compose_box_content = await page.evaluate(
        (element) => element.value,
        compose_box_element,
    );
    assert.equal(
        compose_box_content,
        expected_value,
        `Compose box content did not match with the expected value '{${expected_value}}'`,
    );
}

export async function wait_for_fully_processed_message(page: Page, content: string): Promise<void> {
    // Wait in parallel for the message list scroll animation, which
    // interferes with Puppeteer accurately clicking on messages.
    const scroll_delay = timersPromises.setTimeout(400);

    await page.waitForFunction(
        (content: string) => {
            /*
                The tricky part about making sure that
                a message has actually been fully processed
                is that we'll "locally echo" the message
                first on the client.  Until the server
                actually acks the message, the message will
                have a temporary id and will not have all
                the normal message controls.
                For the Puppeteer tests, we want to avoid all
                the edge cases with locally echoed messages.
                In order to make sure a message is processed,
                we use internals to determine the following:
                    - has message_list even been updated with
                      the message with out content?
                    - has the locally_echoed flag been cleared?
                But for the final steps we look at the
                actual DOM (via JQuery):
                    - is it visible?
                    - does it look to have been
                      re-rendered based on server info?
            */
            const last_msg = zulip_test.current_msg_list?.last();
            if (last_msg === undefined) {
                return false;
            }

            if (last_msg.raw_content !== content) {
                return false;
            }

            if (last_msg.locally_echoed) {
                return false;
            }

            const $row = zulip_test.last_visible_row();
            if (zulip_test.row_id($row) !== last_msg.id) {
                return false;
            }

            /*
                Make sure the message is completely
                re-rendered from its original "local echo"
                version by looking for the star icon.  We
                don't add the star icon until the server
                responds.
            */
            return $row.find(".star").length === 1;
        },
        {},
        content,
    );

    await scroll_delay;
}

export async function select_stream_in_compose_via_dropdown(
    page: Page,
    stream_name: string,
): Promise<void> {
    console.log(`Clicking on 'compose_select_recipient_widget' to select ${stream_name}`);
    const menu_visible = (await page.$(".dropdown-list-container")) !== null;
    if (!menu_visible) {
        await page.waitForSelector("#compose_select_recipient_widget", {visible: true});
        await page.click("#compose_select_recipient_widget");
        await page.waitForSelector(".dropdown-list-container .list-item", {
            visible: true,
        });
    }
    const stream_to_select = `.dropdown-list-container .list-item[data-name="${stream_name}"]`;
    await page.waitForSelector(stream_to_select, {visible: true});
    await page.click(stream_to_select);
    assert((await page.$(".dropdown-list-container")) === null);
}

// Wait for any previous send to finish, then send a message.
export async function send_message(
    page: Page,
    type: "stream" | "private",
    params: Message,
): Promise<void> {
    // If a message is outside the view, we do not need
    // to wait for it to be processed later.
    const outside_view = params.outside_view;
    delete params.outside_view;

    // Compose box content should be empty before sending the message.
    await assert_compose_box_content(page, "");

    if (type === "stream") {
        await page.keyboard.press("KeyC");
    } else if (type === "private") {
        await page.keyboard.press("KeyX");
        const recipients = params.recipient!.split(", ");
        for (const recipient of recipients) {
            await pm_recipient.set(page, recipient);
        }
        delete params.recipient;
    } else {
        assert.fail("`send_message` got invalid message type");
    }

    if (params.stream_name) {
        await select_stream_in_compose_via_dropdown(page, params.stream_name);
        delete params.stream_name;
    }

    if (params.topic) {
        params.stream_message_recipient_topic = params.topic;
        delete params.topic;
    }

    await fill_form(page, 'form[action^="/json/messages"]', params);
    await assert_compose_box_content(page, params.content);
    await ensure_enter_does_not_send(page);
    await page.waitForSelector("#compose-send-button", {visible: true});
    await page.click("#compose-send-button");

    // Sending should clear compose box content.
    await assert_compose_box_content(page, "");

    if (!outside_view) {
        await wait_for_fully_processed_message(page, params.content);
    }

    // Close the compose box after sending the message.
    await page.evaluate(() => {
        zulip_test.cancel_compose();
    });
    // Make sure the compose box is closed.
    await page.waitForSelector("#compose-textarea", {hidden: true});
}

export async function send_multiple_messages(page: Page, msgs: Message[]): Promise<void> {
    for (const msg of msgs) {
        await send_message(page, msg.stream_name !== undefined ? "stream" : "private", msg);
    }
}

/**
 * This method returns a array, which is formatted as:
 *  [
 *    ['stream > topic', ['message 1', 'message 2']],
 *    ['You and Cordelia, Lear's daughter', ['message 1', 'message 2']]
 *  ]
 *
 * The messages are sorted chronologically.
 */
export async function get_rendered_messages(
    page: Page,
    message_list_id: number,
): Promise<[string, string[]][]> {
    const recipient_rows = await page.$$(
        `.message-list[data-message-list-id='${message_list_id}'] .recipient_row`,
    );
    return Promise.all(
        recipient_rows.map(async (element): Promise<[string, string[]]> => {
            const stream_label = await element.$(".stream_label");
            const stream_name = (await get_element_text(stream_label!)).trim();
            const topic_label = await element.$(".stream_topic a");
            const topic_name =
                topic_label === null ? "" : (await get_element_text(topic_label)).trim();
            let key = stream_name;
            if (topic_name !== "") {
                // If topic_name is '', then this is direct messages, so only
                // append > topic_name if we are not in 1:1 or group direct
                // messages.
                key = `${stream_name} > ${topic_name}`;
            }

            const messages = await Promise.all(
                (await element.$$(".message_row .message_content")).map(async (message_row) =>
                    (await get_element_text(message_row)).trim(),
                ),
            );

            return [key, messages];
        }),
    );
}

// This method takes in page, table to fetch the messages
// from, and expected messages. The format of expected
// message is { "stream > topic": [messages] }.
// The method will only check that all the messages in the
// messages array passed exist in the order they are passed.
export async function check_messages_sent(
    page: Page,
    message_list_id: number,
    messages: [string, string[]][],
): Promise<void> {
    await page.waitForSelector(`.message-list[data-message-list-id='${message_list_id}']`, {
        visible: true,
    });
    const rendered_messages = await get_rendered_messages(page, message_list_id);

    // We only check the last n messages because if we run
    // the test with --interactive there will be duplicates.
    const last_n_messages = rendered_messages.slice(-messages.length);
    assert.deepStrictEqual(last_n_messages, messages);
}

export async function open_streams_modal(page: Page): Promise<void> {
    const all_streams_selector = "#subscribe-to-more-streams";
    await page.waitForSelector(all_streams_selector, {visible: true});
    await page.click(all_streams_selector);

    await page.waitForSelector("#subscription_overlay.new-style", {visible: true});
    const url = await page_url_with_fragment(page);
    assert.ok(url.includes("#channels/all"));
}

export async function open_personal_menu(page: Page): Promise<void> {
    const menu_selector = "#personal-menu";
    await page.waitForSelector(menu_selector, {visible: true});
    await page.click(menu_selector);
}

export async function manage_organization(page: Page): Promise<void> {
    const menu_selector = "#settings-dropdown";
    await page.waitForSelector(menu_selector, {visible: true});
    await page.click(menu_selector);

    const organization_settings = '.link-item a[href="#organization"]';
    await page.waitForSelector(organization_settings, {visible: true});
    await page.click(organization_settings);
    await page.waitForSelector("#settings_overlay_container.show", {visible: true});

    const url = await page_url_with_fragment(page);
    assert.match(url, /^http:\/\/[^/]+\/#organization/, "Unexpected organization settings URL");

    const organization_settings_data_section = "li[data-section='organization-settings']";
    await page.click(organization_settings_data_section);
}

export async function select_item_via_typeahead(
    page: Page,
    field_selector: string,
    str: string,
    item: string,
): Promise<void> {
    console.log(`Looking in ${field_selector} to select ${str}, ${item}`);
    await clear_and_type(page, field_selector, str);
    const entry = await page.waitForSelector(
        `xpath///*[${has_class_x(
            "typeahead",
        )} and contains(@style, "display: block")]//li[contains(normalize-space(), "${item}")]//a`,
        {visible: true},
    );
    assert.ok(entry);
    await entry.hover();
    await page.evaluate((entry) => {
        if (!(entry instanceof HTMLElement)) {
            throw new TypeError("expected HTMLElement");
        }
        entry.click();
    }, entry);
}

export async function wait_for_modal_to_close(page: Page): Promise<void> {
    // This function will ensure that the mouse events are enabled for the background for further tests.
    await page.waitForFunction(
        () => document.querySelector(".overlay.show")?.getAttribute("style") === null,
    );
}

export async function wait_for_micromodal_to_open(page: Page): Promise<void> {
    // We manually add the `modal--open` class to the modal after the modal animation completes.
    await page.waitForFunction(() => document.querySelector(".modal--open") !== null);
}

export async function wait_for_micromodal_to_close(page: Page): Promise<void> {
    // This function will ensure that the mouse events are enabled for the background for further tests.
    await page.waitForFunction(() => document.querySelector(".modal--open") === null);
}

export async function run_test_async(test_function: (page: Page) => Promise<void>): Promise<void> {
    // Pass a page instance to test so we can take
    // a screenshot of it when the test fails.
    const browser = await ensure_browser();
    const page = await get_page();

    // Used to keep console messages in order after async source mapping
    let console_ready = Promise.resolve();

    page.on("console", (message: ConsoleMessage) => {
        const context = async ({
            url,
            lineNumber,
            columnNumber,
        }: ConsoleMessageLocation): Promise<string> => {
            let frame = new StackFrame({
                fileName: url,
                lineNumber: lineNumber === undefined ? undefined : lineNumber + 1,
                columnNumber: columnNumber === undefined ? undefined : columnNumber + 1,
            });
            try {
                frame = await gps.getMappedLocation(frame);
            } catch {
                // Ignore source mapping errors
            }
            if (frame.lineNumber === undefined || frame.columnNumber === undefined) {
                return String(frame.fileName);
            }
            return `${String(frame.fileName)}:${frame.lineNumber}:${frame.columnNumber}`;
        };

        const console_ready1 = console_ready;
        console_ready = (async () => {
            let output = `${await context(
                message.location(),
            )}: ${message.type()}: ${message.text()}`;
            if (message.type() === "trace") {
                for (const frame of message.stackTrace()) {
                    output += `\n    at ${await context(frame)}`;
                }
            }
            await console_ready1;
            console.log(output);
        })();
    });

    let page_errored = false;
    page.on("pageerror", (error: Error) => {
        page_errored = true;

        const console_ready1 = console_ready;
        console_ready = (async () => {
            const frames = await Promise.all(
                ErrorStackParser.parse(error).map(async (frame) => {
                    try {
                        frame = await gps.getMappedLocation(frame);
                    } catch {
                        // Ignore source mapping errors
                    }
                    return `\n    at ${String(frame.functionName)} (${String(
                        frame.fileName,
                    )}:${String(frame.lineNumber)}:${String(frame.columnNumber)})`;
                }),
            );
            await console_ready1;
            console.error("Page error:", error.message + frames.join(""));
        })();

        const console_ready2 = console_ready;
        console_ready = (async () => {
            try {
                // Take a screenshot, and increment the screenshot_id.
                await screenshot(page, `failure-${screenshot_id}`);
                screenshot_id += 1;
            } finally {
                await console_ready2;
                console.log("Closing page to stop the test...");
                await page.close();
            }
        })();
    });

    try {
        await test_function(page);
        await log_out(page);

        if (page_errored) {
            throw new Error("Page threw an error");
        }
    } catch (error: unknown) {
        if (!page_errored) {
            // Take a screenshot, and increment the screenshot_id.
            await screenshot(page, `failure-${screenshot_id}`);
            screenshot_id += 1;
        }

        throw error;
    } finally {
        await console_ready;
        await browser.close();
    }
}

export function run_test(test_function: (page: Page) => Promise<void>): void {
    run_test_async(test_function).catch((error: unknown) => {
        console.error(error);
        process.exit(1);
    });
}

export async function get_current_msg_list_id(
    page: Page,
    wait_for_change = false,
): Promise<number> {
    if (wait_for_change) {
        // Wait for the current_msg_list to change if the in the middle of switching narrows.
        // Also works as a way to verify that the current message list did change.
        // NOTE: This only checks if the current message list id changed from the last call to this function,
        // so, make sure to have a call to this function before changing to the narrow that you want to check.
        await page.waitForFunction(
            (last_current_msg_list_id) => {
                const current_msg_list = zulip_test.current_msg_list;
                return (
                    current_msg_list !== undefined &&
                    current_msg_list.id !== last_current_msg_list_id
                );
            },
            {},
            last_current_msg_list_id,
        );
    }
    last_current_msg_list_id = await page.evaluate(() => zulip_test.current_msg_list?.id);
    assert(last_current_msg_list_id !== undefined);
    return last_current_msg_list_id;
}
