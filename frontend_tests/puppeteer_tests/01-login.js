"use strict";

const {test_credentials} = require("../../var/puppeteer/test_credentials");
const common = require("../puppeteer_lib/common");

async function login_tests(page) {
    await common.log_in(page, test_credentials.default_user);
    await common.log_out(page);
}

common.run_test(login_tests);
