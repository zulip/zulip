import type {Page} from "puppeteer";

import {test_credentials} from "../../var/puppeteer/test_credentials";
import common from "../puppeteer_lib/common";

async function login_tests(page: Page): Promise<void> {
    await common.log_in(page, test_credentials.default_user);
    await common.log_out(page);
}

common.run_test(login_tests);
