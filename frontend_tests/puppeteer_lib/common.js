const puppeteer = require('puppeteer');

class CommonUtils {
    constructor() {
        this.browser = null;
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
}

const common = new CommonUtils();
module.exports = common;
