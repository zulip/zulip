import assert from "node:assert/strict";
import type {Page} from "puppeteer";
import * as common from "./lib/common.ts";

//centralized selectors for better maintainability
// used copilot for some suggestions in this file
const SELECTORS = {
    draftsButton: ".top_left_drafts",
    draftsOverlay: "#draft_overlay",
    draftsTable: "#drafts_table",
    overlayMessageRow: ".overlay-message-row",
    streamRecipientTopic: "#stream_message_recipient_topic",
    sendMessageForm: "form#send_message_form",
    privateMessageRecipient: "#private_message_recipient",
    composeCloseButton: "#compose_close",
    newConversationButton: "#new_conversation_button",
    markdownPreviewButton: "#compose .markdown_preview",
    draftsListEmpty: ".drafts-list",
};

//helper functions
async function waitForSelector(page: Page, selector: string, options = {}): Promise<void> {
    await page.waitForSelector(selector, options);
}

async function clickElement(page: Page, selector: string): Promise<void> {
    await waitForSelector(page, selector, {visible: true});
    await page.click(selector);
}

async function getTextFromSelector(page: Page, selector: string): Promise<string> {
    return await common.get_text_from_selector(page, selector);
}

async function assertText(page: Page, selector: string, expectedText: string, message?: string): Promise<void> {
    const actualText = await getTextFromSelector(page, selector);
    assert.strictEqual(actualText, expectedText, message || `Expected text: ${expectedText}, Found: ${actualText}`);
}

async function getDraftCount(page: Page): Promise<number> {
    return await page.$$eval(`${SELECTORS.draftsTable} ${SELECTORS.overlayMessageRow}`, (rows) => rows.length);
}

//more specific test actions
async function testEmptyDrafts(page: Page): Promise<void> {
    console.log("Testing empty drafts...");
    await clickElement(page, SELECTORS.draftsButton);
    await waitForSelector(page, SELECTORS.draftsOverlay);
    await assertText(page, SELECTORS.draftsListEmpty, "No drafts.", "Drafts list should be empty");
    await clickElement(page, `${SELECTORS.draftsOverlay} .exit`);
    console.log("Empty drafts test completed.");
}

async function createStreamMessageDraft(page: Page): Promise<void> {
    console.log("Creating stream message draft...");
    await page.keyboard.press("KeyC");
    await waitForSelector(page, SELECTORS.streamRecipientTopic);
    await common.select_stream_in_compose_via_dropdown(page, "Denmark");
    await common.fill_form(page, SELECTORS.sendMessageForm, {
        content: "Test stream message.",
    });
    await page.type(SELECTORS.streamRecipientTopic, "tests", {delay: 100});
    await clickElement(page, SELECTORS.composeCloseButton);
    console.log("Stream message draft created.");
}

async function createPrivateMessageDraft(page: Page): Promise<void> {
    console.log("Creating private message draft...");
    await page.keyboard.press("KeyX");
    await waitForSelector(page, SELECTORS.privateMessageRecipient);
    await common.fill_form(page, SELECTORS.sendMessageForm, {content: "Test direct message."});
    await common.pm_recipient.set(page, "cordelia@zulip.com");
    await common.pm_recipient.set(page, "hamlet@zulip.com");
    await clickElement(page, SELECTORS.composeCloseButton);
    console.log("Private message draft created.");
}

async function testDraftRestoration(page: Page): Promise<void> {
    console.log("Testing draft restoration...");
    const draftsCount = await getDraftCount(page);
    assert.strictEqual(draftsCount, 2, "Drafts improperly loaded.");
    await assertText(
        page,
        `${SELECTORS.draftsTable} ${SELECTORS.overlayMessageRow} .message_header_stream .stream_label`,
        "Denmark",
    );
    await assertText(
        page,
        `${SELECTORS.draftsTable} ${SELECTORS.overlayMessageRow} .message_header_stream .stream_topic`,
        "tests",
    );
    console.log("Draft restoration test completed.");
}

//main test runner
async function draftsTest(page: Page): Promise<void> {
    console.log("Starting drafts tests...");
    await common.log_in(page);
    await testEmptyDrafts(page);
    await createStreamMessageDraft(page);
    await createPrivateMessageDraft(page);
    await testDraftRestoration(page);
    console.log("Drafts tests completed successfully.");
}

common.run_test(draftsTest);
