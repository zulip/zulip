import assert from "node:assert/strict";

import type {Page} from "puppeteer";

import * as common from "./lib/common.ts";

async function open_tasks_overlay(page: Page): Promise<void> {
    const tasks_loaded = page.waitForResponse(
        (response) =>
            response.url().includes("/json/users/me/tasks") && response.status() === 200,
    );
    await page.waitForSelector("#tasks-toggle-button", {visible: true});
    await page.click("#tasks-toggle-button");
    await page.waitForSelector("#tasks-overlay", {visible: true});
    await tasks_loaded;
    await page.waitForFunction(() => {
        const el = document.querySelector("#tasks-content");
        if (el === null) {
            return false;
        }
        return !(el.textContent ?? "").includes("Loading tasks");
    });
}

async function close_tasks_overlay(page: Page): Promise<void> {
    await page.click("#close-tasks");
    await page.waitForFunction(() => {
        const overlay = document.querySelector("#tasks-overlay");
        return overlay === null || window.getComputedStyle(overlay).display === "none";
    });
}

async function post_task_for_last_message(page: Page, title: string, description: string): Promise<void> {
    await page.evaluate(
        async (task_title: string, task_description: string) => {
            const csrf = $('input[name="csrfmiddlewaretoken"]').attr("value");
            if (csrf === undefined) {
                throw new Error("missing csrf token");
            }
            const msg = zulip_test.current_msg_list?.last();
            if (msg === undefined) {
                throw new Error("no current message");
            }
            const body = new URLSearchParams();
            body.set("csrfmiddlewaretoken", csrf);
            body.set("title", task_title);
            body.set("description", task_description);
            const res = await fetch(`/json/messages/${String(msg.id)}/tasks`, {
                method: "POST",
                headers: {"Content-Type": "application/x-www-form-urlencoded"},
                body: body.toString(),
                credentials: "same-origin",
            });
            if (!res.ok) {
                throw new Error(`create task failed: ${String(res.status)} ${await res.text()}`);
            }
        },
        title,
        description,
    );
}

async function tasks_e2e_tests(page: Page): Promise<void> {
    await common.log_in(page);
    await page.click("#left-sidebar-navigation-list .top_left_all_messages");
    let message_list_id = await common.get_current_msg_list_id(page, true);
    await page.waitForSelector(
        `.message-list[data-message-list-id='${message_list_id}'] .message_row`,
        {visible: true},
    );

    await open_tasks_overlay(page);
    assert.equal(await common.get_text_from_selector(page, "#tasks-overlay h2"), "My Tasks");
    assert.ok((await common.get_text_from_selector(page, "#tasks-content")).includes("No tasks yet!"));
    await close_tasks_overlay(page);

    const title = "overlay task";

    await common.send_message(page, "stream", {
        stream_name: "Verona",
        topic: "tasks",
        content: "stream msg for task",
    });
    message_list_id = await common.get_current_msg_list_id(page, false);
    await post_task_for_last_message(page, title, "overlay body");

    await open_tasks_overlay(page);
    let content_text = await common.get_text_from_selector(page, "#tasks-content");
    assert.ok(content_text.includes(title));
    assert.ok((await page.$('#tasks-content a[href^="#narrow/stream/"]')) !== null);
    await close_tasks_overlay(page);

    await common.send_message(page, "stream", {
        stream_name: "Verona",
        topic: "tasks-search",
        content: "msg one",
    });
    await post_task_for_last_message(page, "findme", "");

    await common.send_message(
        page,
        "stream",
        {
            stream_name: "Verona",
            topic: "tasks-search",
            content: "msg two",
        },
        false,
    );
    await post_task_for_last_message(page, "other", "");

    await open_tasks_overlay(page);
    content_text = await common.get_text_from_selector(page, "#tasks-content");
    assert.ok(content_text.includes("findme"));
    assert.ok(content_text.includes("other"));

    await common.clear_and_type(page, "#tasks-search", "findme");
    await page.waitForFunction(() => {
        const el = document.querySelector("#tasks-content");
        if (el === null) {
            return false;
        }
        const t = el.textContent ?? "";
        return t.includes("findme") && !t.includes("other");
    });
    content_text = await common.get_text_from_selector(page, "#tasks-content");
    assert.ok(content_text.includes("Found 1 of 3 tasks"));

    await close_tasks_overlay(page);

    await open_tasks_overlay(page);
    assert.equal(await common.get_text_from_selector(page, "#tasks-overlay h2"), "My Tasks");
    await close_tasks_overlay(page);
    await open_tasks_overlay(page);
    assert.equal(await common.get_text_from_selector(page, "#tasks-overlay h2"), "My Tasks");
    await close_tasks_overlay(page);

    await common.send_message(page, "stream", {
        stream_name: "Verona",
        topic: "smoke-ext",
        content: "smoke ext body",
    });
    message_list_id = await common.get_current_msg_list_id(page, false);
    await post_task_for_last_message(page, "pending smoke", "");

    await open_tasks_overlay(page);
    const pending_btn = await page.$('#tasks-overlay .filter-tabs button[data-filter="pending"]');
    assert.ok(pending_btn !== null);
    await pending_btn!.click();
    await page.waitForFunction(() => {
        const el = document.querySelector("#tasks-content");
        return el !== null && (el.textContent ?? "").includes("pending smoke");
    });
    const completed_btn = await page.$('#tasks-overlay .filter-tabs button[data-filter="completed"]');
    assert.ok(completed_btn !== null);
    await completed_btn!.click();
    await page.waitForFunction(() => {
        const el = document.querySelector("#tasks-content");
        return el !== null && !(el.textContent ?? "").includes("pending smoke");
    });
    const all_btn = await page.$('#tasks-overlay .filter-tabs button[data-filter="all"]');
    assert.ok(all_btn !== null);
    await all_btn!.click();
    await page.waitForFunction(() => {
        const el = document.querySelector("#tasks-content");
        return el !== null && (el.textContent ?? "").includes("pending smoke");
    });
    await close_tasks_overlay(page);
}

await common.run_test(tasks_e2e_tests);
