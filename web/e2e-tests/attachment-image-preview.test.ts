import fs from "node:fs";

import type {Page} from "puppeteer";

import * as common from "./lib/common.ts";

const FILENAME = "zulip-icon-128x128.png";

async function test_attachment_delete_updates_image_preview(page: Page): Promise<void> {
    await common.log_in(page);
    await page.click("#left-sidebar-navigation-list .top_left_all_messages");
    await common.get_current_msg_list_id(page, true);

    // Read the image from the filesystem in Node and pass it as base64 into
    // the browser, so we can POST it to /json/user_uploads without needing
    // the webpack dev server to be running.
    const file_base64 = fs.readFileSync(`static/images/logo/${FILENAME}`).toString("base64");

    const {attachment_url, path_id} = await page.evaluate(
        async (filename: string, b64: string) => {
            const bytes = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
            const blob = new Blob([bytes], {type: "image/png"});
            const csrf =
                document.querySelector<HTMLInputElement>('input[name="csrfmiddlewaretoken"]')
                    ?.value ?? "";
            const form = new FormData();
            form.append("csrfmiddlewaretoken", csrf);
            form.append("file", blob, filename);
            const resp = await fetch("/json/user_uploads", {
                method: "POST",
                body: form,
            });
            const data = (await resp.json()) as {url: string};
            return {
                attachment_url: data.url,
                path_id: data.url.replace(/^\/user_uploads\//, ""),
            };
        },
        FILENAME,
        file_base64,
    );

    await page.keyboard.press("KeyC");
    await page.waitForSelector("#compose-textarea", {visible: true});
    await common.select_stream_in_compose_via_dropdown(page, "Verona");
    await common.clear_and_type(page, "#stream_message_recipient_topic", "attachment preview test");
    await common.clear_and_type(page, "#compose-textarea", `[${FILENAME}](${attachment_url})`);

    await page.click("#compose-send-button");

    await page.waitForFunction(
        () => {
            const imgs = [
                ...document.querySelectorAll<HTMLImageElement>("img.media-image-element"),
            ];
            return imgs.some((img) => img.complete && img.naturalWidth > 0);
        },
        {timeout: 15_000},
    );

    // Arm the response watcher before deleting so we don't miss the fetch
    // that update_media_previews_for_deleted_attachment fires.
    const thumbnail_invalidated = page.waitForResponse(
        (response) => response.url().includes(path_id) && response.status() === 404,
        {timeout: 15_000},
    );

    // Delete the attachment directly via the API, bypassing the settings UI
    await page.evaluate(async (p_id: string) => {
        const csrf =
            document.querySelector<HTMLInputElement>('input[name="csrfmiddlewaretoken"]')?.value ??
            "";
        const list_resp = await fetch("/json/attachments");
        const list_data = (await list_resp.json()) as {
            attachments: Array<{id: number; path_id: string}>;
        };
        const attachment = list_data.attachments.find((a) => a.path_id === p_id);
        if (!attachment) {
            throw new Error(`Attachment with path_id ${p_id} not found`);
        }
        await fetch(`/json/attachments/${attachment.id}`, {
            method: "DELETE",
            headers: {"X-CSRFToken": csrf},
        });
    }, path_id);

    await thumbnail_invalidated;
}

await common.run_test(test_attachment_delete_updates_image_preview);
