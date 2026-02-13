"use strict";

const TEST_EMAIL_DOMAIN = "example.com";

const make_email = (local_part) => `${local_part}@${TEST_EMAIL_DOMAIN}`;
const make_email_prefix = (local_part) => `${local_part}@${TEST_EMAIL_DOMAIN.split(".")[0]}`;

exports.TEST_EMAIL_DOMAIN = TEST_EMAIL_DOMAIN;
exports.make_email = make_email;
exports.make_email_prefix = make_email_prefix;
