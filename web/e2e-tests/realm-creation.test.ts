import {strict as assert} from "assert";

import type {Page} from "puppeteer";
import {z} from "zod";

import * as common from "./lib/common";

const email = "alice@test.example.com";
const organization_name = "Awesome Organization";
const host = "zulipdev.com:9981";

async function realm_creation_tests(page: Page): Promise<void> {
    await page.goto("http://" + host + "/new/");

    // submit the email for realm creation.
    await page.waitForSelector("#email");
    await page.type("#email", email);
    await page.type("#id_team_name", organization_name);
    await page.$eval("input#realm_in_root_domain", (el) => {
        el.click();
    });

    await Promise.all([
        page.waitForNavigation(),
        page.$eval("form#create_realm", (form) => {
            form.submit();
        }),
    ]);

    // Make sure confirmation email is sent.
    assert.ok(page.url().includes("/accounts/new/send_confirm/?email=alice%40test.example.com"));

    // Special endpoint enabled only during tests for extracting confirmation key
    await page.goto("http://" + host + "/confirmation_key/");

    // Open the confirmation URL
    const page_content = await page.evaluate(() => document.querySelector("body")!.textContent);
    assert(page_content !== null);
    const {confirmation_key} = z
        .object({confirmation_key: z.string()})
        .parse(JSON.parse(page_content));
    const confirmation_url = `http://${host}/accounts/do_confirm/${confirmation_key}`;
    await page.goto(confirmation_url);

    // We wait until the DOMContentLoaded event because we want the code
    // that focuses the first input field to run before we run our tests to avoid
    // flakes. Without waiting for DOMContentLoaded event, in rare cases, the
    // first input is focused when we are typing something for other fields causing
    // validation errors. The code for focusing the input is wrapped in jQuery
    // $() calls which runs when DOMContentLoaded is fired.
    await page.waitForNavigation({waitUntil: "domcontentloaded"});

    // Make sure the realm creation page is loaded correctly by
    // checking the text in <p> tag under pitch class is as expected.
    await page.waitForSelector(".pitch");
    const text_in_pitch = await page.evaluate(
        () => document.querySelector(".pitch p")!.textContent,
    );
    assert.equal(text_in_pitch, "Enter your account details to complete registration.");

    // fill the form.
    const params = {
        full_name: "Alice",
        password: "passwordwhichisnotreallycomplex",
        terms: true,
        how_realm_creator_found_zulip: "other",
        how_realm_creator_found_zulip_other_text: "test",
    };
    // For some reason, page.click() does not work this for particular checkbox
    // so use page.$eval here to call the .click method in the browser.
    await common.fill_form(page, "#registration", params);
    await page.$eval("form#registration", (form) => {
        form.submit();
    });

    // Check if realm is created and user is logged in by checking if
    // element of id `lightbox_overlay` exists.
    await page.waitForSelector("#lightbox_overlay"); // if element doesn't exist,timeout error raises

    // Updating common.realm_url because we are redirecting to it when logging out.
    common.set_realm_url(page.url());
}

common.run_test(realm_creation_tests);
