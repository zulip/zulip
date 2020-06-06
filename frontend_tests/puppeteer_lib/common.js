const path = require('path');
const puppeteer = require('puppeteer');
const assert = require("assert").strict;
const test_credentials = require('../../var/casper/test_credentials.js').test_credentials;

class CommonUtils {
    constructor() {
        this.browser = null;
        this.screenshot_id = 0;
        this.realm_url = "http://zulip.zulipdev.com:9981/";
    }

    async ensure_browser() {
        if (this.browser === null) {
            this.browser = await puppeteer.launch({
                args: [
                    '--window-size=1400,1024',
                    '--no-sandbox', '--disable-setuid-sandbox',
                ],
                defaultViewport: { width: 1280, height: 1024 },
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

        const root_dir = path.resolve(__dirname, '../../');
        const screenshot_path = path.join(root_dir, 'var/puppeteer', `${name}.png`);
        await page.screenshot({
            path: screenshot_path,
        });
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
        for (const name of Object.keys(params)) {
            const name_selector = `${form_selector} [name="${name}"]`;
            const value = params[name];
            if (typeof value === "boolean") {
                await page.$eval(name_selector, (el, value) => {
                    if (el.checked !== value) {
                        el.click();
                    }
                });
            } else {
                await page.type(name_selector, params[name]);
            }
        }
    }

    async log_in(page, credentials = null) {
        console.log("Logging in");
        await page.goto(this.realm_url + 'login/');
        assert.equal(this.realm_url + 'login/', page.url());
        if (credentials === null) {
            credentials = test_credentials.default_user;
        }
        // fill login form
        const params = {
            username: credentials.username,
            password: credentials.password,
        };
        await this.fill_form(page, '#login_form', params);

        // We wait until DOMContentLoaded event is fired to ensure that zulip JavaScript
        // is executed since some of our tests access those through page.evaluate. We use defer
        // tag for script tags that load JavaScript which means that whey will be executed after DOM
        // is parsed but before DOMContentLoaded event is fired.
        await Promise.all([
            page.waitForNavigation({ waitUntil: 'domcontentloaded' }),
            page.$eval('#login_form', form => form.submit()),
        ]);
    }

    async log_out(page) {
        await page.goto(this.realm_url);
        const menu_selector = '#settings-dropdown';
        const logout_selector = 'a[href="#logout"]';
        console.log("Loggin out");
        await page.waitForSelector(menu_selector, {visible: true});
        await page.click(menu_selector);
        await page.waitForSelector(logout_selector);
        await page.click(logout_selector);

        // Wait for a email input in login page so we know login
        // page is loaded. Then check that we are at the login url.
        await page.waitForSelector('input[name="username"]');
        assert(page.url().includes('/login/'));
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
