const assert = require("assert").strict;
const path = require("path");

const puppeteer = require("puppeteer");

const test_credentials = require("../../var/casper/test_credentials.js").test_credentials;

class CommonUtils {
    constructor() {
        this.browser = null;
        this.screenshot_id = 0;
        this.realm_url = "http://zulip.zulipdev.com:9981/";
        this.pm_recipient = {
            async set(page, recipient) {
                await page.type("#private_message_recipient", recipient);
                await page.keyboard.press("Enter");
            },

            async expect(page, expected) {
                const actual_recipients = await page.evaluate(() =>
                    compose_state.private_message_recipient(),
                );
                assert.equal(actual_recipients, expected);
            },
        };
        this.fullname = {
            cordelia: "Cordelia Lear",
            othello: "Othello, the Moor of Venice",
            hamlet: "King Hamlet",
        };
    }

    async ensure_browser() {
        if (this.browser === null) {
            this.browser = await puppeteer.launch({
                args: ["--window-size=1400,1024", "--no-sandbox", "--disable-setuid-sandbox"],
                defaultViewport: {width: 1280, height: 1024},
                headless: true,
            });
        }
    }

    async get_page(url = null) {
        await this.ensure_browser();

        const page = await this.browser.newPage();
        if (url !== null) {
            await page.goto(url);
        }

        return page;
    }

    async screenshot(page, name = null) {
        if (name === null) {
            name = `${this.screenshot_id}`;
            this.screenshot_id += 1;
        }

        const root_dir = path.resolve(__dirname, "../../");
        const screenshot_path = path.join(root_dir, "var/puppeteer", `${name}.png`);
        await page.screenshot({
            path: screenshot_path,
        });
    }

    async assert_selector_doesnt_exist(page, selector) {
        await page.waitForFunction((selector) => $(selector === null), {}, selector);
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
    async fill_form(page, form_selector, params) {
        async function is_dropdown(page, name) {
            return (await page.$(`select[name="${name}"]`)) !== null;
        }
        for (const name of Object.keys(params)) {
            const name_selector = `${form_selector} [name="${name}"]`;
            const value = params[name];
            if (typeof value === "boolean") {
                await page.$eval(name_selector, (el, value) => {
                    if (el.checked !== value) {
                        el.click();
                    }
                });
            } else if (await is_dropdown(page, name)) {
                await page.select(name_selector, params[name]);
            } else {
                // clear any existing text in the input field before filling.
                await page.$eval(name_selector, (el) => {
                    el.value = "";
                });
                await page.type(name_selector, params[name]);
            }
        }
    }

    async check_form_contents(page, form_selector, params) {
        for (const name of Object.keys(params)) {
            const name_selector = `${form_selector} [name="${name}"]`;
            const expected_value = params[name];
            if (typeof expected_value === "boolean") {
                assert.equal(
                    await page.$eval(name_selector, (el) => el.checked),
                    expected_value,
                    "Form content is not as expected.",
                );
            } else {
                assert.equal(
                    await page.$eval(name_selector, (el) => el.value),
                    expected_value,
                    "Form content is not as expected.",
                );
            }
        }
    }

    async get_text_from_selector(page, selector) {
        return await page.evaluate((selector) => $(selector).text().trim(), selector);
    }

    async get_stream_id(page, stream_name) {
        return await page.evaluate(
            (stream_name) => stream_data.get_stream_id(stream_name),
            stream_name,
        );
    }

    async get_user_id_from_name(page, name) {
        if (this.fullname[name] !== undefined) {
            name = this.fullname[name];
        }
        return await page.evaluate((name) => people.get_user_id_from_name(name), name);
    }

    async get_internal_email_from_name(page, name) {
        if (this.fullname[name] !== undefined) {
            name = this.fullname[name];
        }
        return await page.evaluate((fullname) => {
            const user_id = people.get_user_id_from_name(fullname);
            return people.get_by_user_id(user_id).email;
        }, name);
    }

    async log_in(page, credentials = null) {
        console.log("Logging in");
        await page.goto(this.realm_url + "login/");
        assert.equal(this.realm_url + "login/", page.url());
        if (credentials === null) {
            credentials = test_credentials.default_user;
        }
        // fill login form
        const params = {
            username: credentials.username,
            password: credentials.password,
        };
        await this.fill_form(page, "#login_form", params);

        // We wait until DOMContentLoaded event is fired to ensure that zulip JavaScript
        // is executed since some of our tests access those through page.evaluate. We use defer
        // tag for script tags that load JavaScript which means that whey will be executed after DOM
        // is parsed but before DOMContentLoaded event is fired.
        await Promise.all([
            page.waitForNavigation({waitUntil: "domcontentloaded"}),
            page.$eval("#login_form", (form) => form.submit()),
        ]);
    }

    async log_out(page) {
        await page.goto(this.realm_url);
        const menu_selector = "#settings-dropdown";
        const logout_selector = 'a[href="#logout"]';
        console.log("Loggin out");
        await page.waitForSelector(menu_selector, {visible: true});
        await page.click(menu_selector);
        await page.waitForSelector(logout_selector);
        await page.click(logout_selector);

        // Wait for a email input in login page so we know login
        // page is loaded. Then check that we are at the login url.
        await page.waitForSelector('input[name="username"]');
        assert(page.url().includes("/login/"));
    }

    async ensure_enter_does_not_send(page) {
        await page.$eval("#enter_sends", (el) => {
            if (el.checked) {
                el.click();
            }
        });
    }

    async wait_for_fully_processed_message(page, content) {
        await page.waitFor(
            (content) => {
                /*
                The tricky part about making sure that
                a message has actually been fully processed
                is that we'll "locally echo" the message
                first on the client.  Until the server
                actually acks the message, the message will
                have a temporary id and will not have all
                the normal message controls.
                For the Casper tests, we want to avoid all
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
                const last_msg = current_msg_list.last();
                if (last_msg === undefined) {
                    return false;
                }

                if (last_msg.raw_content !== content) {
                    return false;
                }

                if (last_msg.locally_echoed) {
                    return false;
                }

                const row = rows.last_visible();
                if (rows.id(row) !== last_msg.id) {
                    return false;
                }

                /*
                Make sure the message is completely
                re-rendered from its original "local echo"
                version by looking for the star icon.  We
                don't add the star icon until the server
                responds.
            */
                return row.find(".star").length === 1;
            },
            {},
            content,
        );
    }

    // Wait for any previous send to finish, then send a message.
    async send_message(page, type, params) {
        // If a message is outside the view, we do not need
        // to wait for it to be processed later.
        const {outside_view} = params;
        delete params.outside_view;

        await page.waitForSelector("#compose-textarea");

        if (type === "stream") {
            await page.keyboard.press("KeyC");
        } else if (type === "private") {
            await page.keyboard.press("KeyX");
            const recipients = params.recipient.split(", ");
            for (let i = 0; i < recipients.length; i += 1) {
                await this.pm_recipient.set(page, recipients[i]);
            }
            delete params.recipient;
        } else {
            assert.fail("`send_message` got invalid message type");
        }

        if (params.stream) {
            params.stream_message_recipient_stream = params.stream;
            delete params.stream;
        }

        if (params.topic) {
            params.stream_message_recipient_topic = params.topic;
            delete params.topic;
        }

        await this.fill_form(page, 'form[action^="/json/messages"]', params);
        await this.ensure_enter_does_not_send(page);
        await page.waitForSelector("#compose-send-button", {visible: true});
        await page.click("#compose-send-button");

        // confirm if compose box is empty.
        const compose_box_element = await page.$("#compose-textarea");
        const compose_box_content = await page.evaluate(
            (element) => element.textContent,
            compose_box_element,
        );
        assert.equal(compose_box_content, "", "Compose box not empty after message sent");

        if (!outside_view) {
            await this.wait_for_fully_processed_message(page, params.content);
        }

        // Close the compose box after sending the message.
        await page.evaluate(() => {
            compose_actions.cancel();
        });
        // Make sure the compose box is closed.
        await page.waitForSelector("#compose-textarea", {hidden: true});
    }

    async send_multiple_messages(page, msgs) {
        for (let msg_index = 0; msg_index < msgs.length; msg_index += 1) {
            const msg = msgs[msg_index];
            await this.send_message(page, msg.stream !== undefined ? "stream" : "private", msg);
        }
    }

    /**
     * This method returns a array, which is formmated as:
     *  [
     *    ['stream > topic', ['message 1', 'message 2']],
     *    ['You and Cordelia Lear', ['message 1', 'message 2']]
     *  ]
     *
     * The messages are sorted chronologically.
     */
    async get_rendered_messages(page, table = "zhome") {
        return await page.evaluate((table) => {
            const data = [];
            const $recipient_rows = $(`#${table}`).find(".recipient_row");
            $.map($recipient_rows, (element) => {
                const $el = $(element);
                const stream_name = $el.find(".stream_label").text().trim();
                const topic_name = $el.find(".stream_topic a").text().trim();

                let key = stream_name;
                if (topic_name !== "") {
                    // If topic_name is '' then this is PMs, so only
                    // append > topic_name if we are not in PMs or Group PMs.
                    key = `${stream_name} > ${topic_name}`;
                }

                const messages = [];
                $.map($el.find(".message_row .message_content"), (message_row) => {
                    messages.push(message_row.innerText.trim());
                });

                data.push([key, messages]);
            });

            return data;
        }, table);
    }

    // This method takes in page, table to fetch the messages
    // from, and expected messages. The format of expected
    // message is { "stream > topic": [messages] }.
    // The method will only check that all the messages in the
    // messages array passed exist in the order they are passed.
    async check_messages_sent(page, table, messages) {
        await page.waitForSelector("#" + table);
        const rendered_messages = await this.get_rendered_messages(page, table);

        // We only check the last n messages because if we run
        // the test with --interactive there will be duplicates.
        const last_n_messages = rendered_messages.slice(-messages.length);
        assert.deepStrictEqual(last_n_messages, messages);
    }

    async run_test(test_function) {
        // Pass a page instance to test so we can take
        // a screenshot of it when the test fails.
        const page = await this.get_page();
        try {
            await test_function(page);
        } catch (e) {
            console.log(e);

            // Take a screenshot, and increment the screenshot_id.
            await this.screenshot(page, `failure-${this.screenshot_id}`);
            this.screenshot_id += 1;

            await this.browser.close();
            process.exit(1);
        } finally {
            this.browser.close();
        }
    }
}

const common = new CommonUtils();
module.exports = common;
