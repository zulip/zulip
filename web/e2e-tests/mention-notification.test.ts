import assert from "node:assert/strict";
import {execFileSync} from "node:child_process";

import type {Page} from "puppeteer";

import * as common from "./lib/common.ts";

async function api(
    page: Page,
    path: string,
    method: string,
    parameters: Record<string, string> = {},
): Promise<Record<string, unknown>> {
    return await page.evaluate(
        async ({path, method, parameters}) => {
            const csrf = document.querySelector<HTMLInputElement>(
                "input[name=csrfmiddlewaretoken]",
            )?.value;
            if (!csrf) {
                throw new Error("Missing CSRF token");
            }
            const query = new URLSearchParams(parameters);
            const response = await fetch(method === "GET" ? `${path}?${query}` : path, {
                method,
                headers: {
                    "X-CSRFToken": csrf,
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                ...(method !== "GET" && {body: query}),
            });
            const data = await response.json();
            if (!response.ok || data.result !== "success") {
                throw new Error(JSON.stringify(data));
            }
            return data;
        },
        {path, method, parameters},
    );
}

async function notification_count(page: Page): Promise<number> {
    const data = await api(page, "/json/messages", "GET", {
        anchor: "newest",
        num_before: "100",
        num_after: "0",
        apply_markdown: "false",
    });
    const messages = data["messages"] as {type: string; content: string; sender_email: string}[];
    const notifications = messages.filter(
        (message) =>
            message.type === "private" &&
            message.sender_email === "notification-bot@zulip.com" &&
            message.content.includes("CoreX notification integration"),
    );
    return notifications.length;
}

async function start_mention(page: Page): Promise<void> {
    await page.bringToFront();
    await page.keyboard.press("KeyC");
    await page.waitForSelector("#compose-textarea", {visible: true});
    await common.select_stream_in_compose_via_dropdown(page, "CoreX notifications");
    await common.fill_form(page, "form#send_message_form", {
        stream_message_recipient_topic: "CoreX notification integration",
    });
    await common.select_item_via_typeahead(
        page,
        "#compose-textarea",
        "@Othello",
        common.fullname.othello,
    );
    await page.waitForSelector("#compose_banners .notify-mentioned-user", {visible: true});
}

async function send(page: Page): Promise<number> {
    const response = page.waitForResponse(
        (response) =>
            response.url().endsWith("/json/messages") && response.request().method() === "POST",
    );
    await page.click("#compose-send-button");
    const result = await response;
    assert.equal(result.status(), 200);
    const data = await result.json();
    assert.equal(data.result, "success");
    await page.waitForFunction(() => {
        const textarea = document.querySelector<HTMLTextAreaElement>("#compose-textarea");
        return textarea?.value === "";
    });
    return data.id as number;
}

async function test_notifications(page: Page): Promise<void> {
    await common.log_in(page);
    const email = "othello@zulip.com";
    const password = execFileSync("./manage.py", ["print_initial_password", email], {
        encoding: "utf8",
    })
        .split("\n")
        .find((line) => line.startsWith(email))
        ?.trim()
        .split(/\s+/)[1];
    assert.ok(password);
    await api(page, "/json/users/me/subscriptions", "POST", {
        subscriptions: JSON.stringify([{name: "CoreX notifications"}]),
    });
    await page.waitForFunction(() => zulip_test.get_stream_id("CoreX notifications") !== undefined);
    const context = await page.browser().createBrowserContext();
    const recipient = await context.newPage();
    try {
        await common.log_in(recipient, {username: email, password});
        const subscriptions_before = await api(recipient, "/json/users/me/subscriptions", "GET");
        assert.equal(await notification_count(recipient), 0);

        await start_mention(page);
        await send(page);
        assert.equal(await notification_count(recipient), 0);

        await start_mention(page);
        const notify = "#compose_banners .notify-mentioned-user";
        await page.focus(notify);
        await page.keyboard.press("Tab");
        await page.keyboard.down("Shift");
        await page.keyboard.press("Tab");
        await page.keyboard.up("Shift");
        assert.equal(await page.$eval(notify, (button) => button === document.activeElement), true);
        await page.keyboard.press("Space");
        await page.waitForFunction(
            (selector) => document.querySelector(selector)?.getAttribute("aria-pressed") === "true",
            {},
            notify,
        );
        assert.equal(await notification_count(recipient), 0);
        for (const width of [1920, 1280, 768, 480]) {
            await page.setViewport({width, height: 1024});
            await common.screenshot(page, `mention-notification-selected-${width}`);
            const bounds = await page.$eval(notify, (button) => {
                const rect = button.getBoundingClientRect();
                return {left: rect.left, right: rect.right, width: rect.width};
            });
            assert.ok(bounds.width > 0 && bounds.left >= 0 && bounds.right <= width);
        }
        await page.setViewport({width: 1400, height: 1024});
        await api(page, "/json/settings", "PATCH", {color_scheme: "2"});
        await page.waitForSelector(":root.dark-theme");
        await common.screenshot(page, "mention-notification-dark");
        await page.locator("#compose_banners .recipient_not_subscribed").wait();
        const banner = await page.$("#compose_banners .recipient_not_subscribed");
        assert.ok(banner);
        await banner.screenshot({path: "var/puppeteer/mention-notification-banner.png"});
        await api(page, "/json/settings", "PATCH", {color_scheme: "3"});
        const original_id = await send(page);
        assert.equal(await notification_count(recipient), 1);
        const messages = await api(recipient, "/json/messages", "GET", {
            anchor: "newest",
            num_before: "100",
            num_after: "0",
            apply_markdown: "false",
        });
        const dm = (messages["messages"] as {type: string; content: string}[]).find(
            (message) =>
                message.type === "private" && message.content.includes(`/near/${original_id}`),
        );
        assert.ok(dm);
        assert.ok(dm.content.includes("quote"));
        assert.deepEqual(
            await api(recipient, "/json/users/me/subscriptions", "GET"),
            subscriptions_before,
        );

        await start_mention(page);
        await page.click(notify);
        await common.clear_and_type(page, "#compose-textarea", "Removed mention");
        await page.waitForSelector(notify, {hidden: true});
        await send(page);
        assert.equal(await notification_count(recipient), 1);

        await start_mention(page);
        await page.click(notify);
        await common.select_stream_in_compose_via_dropdown(page, "Verona");
        await send(page);
        assert.equal(await notification_count(recipient), 1);

        await start_mention(page);
        await page.click(notify);
        await page.keyboard.press("Escape");
        await page.waitForSelector("#compose-textarea", {hidden: true});
        await start_mention(page);
        assert.equal(
            await page.$eval(notify, (button) => button.getAttribute("aria-pressed")),
            "false",
        );
        await send(page);
        assert.equal(await notification_count(recipient), 1);
        await start_mention(page);
        const subscribe = "#compose_banners .recipient_not_subscribed .secondary-button";
        await page.click(subscribe);
        await page.waitForSelector("#compose_banners .recipient_not_subscribed", {hidden: true});
        const subscribed = await api(recipient, "/json/users/me/subscriptions", "GET");
        assert.ok(
            (subscribed["subscriptions"] as {name: string}[]).some(
                (subscription) => subscription.name === "CoreX notifications",
            ),
        );
        console.log("CoreX integration: one explicit DM, zero duplicate or stale-intent DMs");
    } finally {
        await context.close();
    }
}

await common.run_test(test_notifications);
