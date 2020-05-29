const path = require('path');
const puppeteer = require('puppeteer');
const assert = require("assert");

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

    async log_in(page, credentials) {
        console.log("Logging in");
        await page.goto(this.realm_url + 'login/');
        assert.equal(this.realm_url + 'login/', page.url());
        await page.type('#id_username', credentials.username);
        await page.type('#id_password', credentials.password);
        await page.$eval('#login_form', form => form.submit());
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
