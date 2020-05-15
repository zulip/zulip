const path = require('path');
const puppeteer = require('puppeteer');

class CommonUtils {
    constructor() {
        this.browser = null;
        this.screenshot_id = 0;
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

    async run_test(test_function) {
        try {
            await test_function();
        } catch (e) {
            console.log(e);
            await this.browser.close();
            process.exit(1);
        } finally {
            this.browser.close();
        }
    }
}

const common = new CommonUtils();
module.exports = common;
