"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const {JSDOM} = require("jsdom");

const {set_global, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const dom = new JSDOM(`<!DOCTYPE html>`);
set_global("document", dom.window.document);
set_global("Node", dom.window.Node);

const pure_dom = zrequire("pure_dom");

function buddy_list_section_header() {
    return pure_dom.buddy_list_section_header({
        id: "some-id",
        header_text: "THIS CONVERSATION",
        is_collapsed: false,
    });
}

function view_all_subscribers() {
    return pure_dom.view_all_subscribers({
        stream_edit_hash: "some-stream-hash",
    });
}

function view_all_users() {
    return pure_dom.view_all_users();
}

function empty_list_widget_for_list() {
    return pure_dom.empty_list_widget_for_list({
        empty_list_message: "Your list is empty.",
    });
}

function poll_widget() {
    return pure_dom.poll_widget();
}

function buddy_info({user_id}) {
    return {
        href: "url",
        name: "test",
        user_id,
        profile_picture: "profile_picture_url",
        status_emoji_info: undefined,
        is_current_user: true,
        num_unread: 4,
        user_circle_class: "user-circle-active",
        status_text: "Some status text",
        has_status_text: true,
        user_list_style: {
            COMPACT: false,
            WITH_STATUS: false,
            WITH_AVATAR: true,
        },
        should_add_guest_user_indicator: false,
    };
}

function presence_row() {
    return pure_dom.presence_row(buddy_info({user_id: 101}));
}

function presence_rows() {
    return pure_dom.presence_rows({
        presence_rows: [
            buddy_info({user_id: 201}),
            buddy_info({user_id: 202}),
            buddy_info({user_id: 203}),
        ],
    });
}

function verify_template_equivalence(f, template_name) {
    const full_template_fn = path.resolve(__dirname, `../templates/${template_name}.hbs`);
    const widget = f();
    const expected = fs.readFileSync(full_template_fn, "utf8").trim().replace(".  ", ". ");
    const actual = widget.to_source("").trim();
    assert.equal(actual, expected);
}

run_test("template equivalence", () => {
    verify_template_equivalence(buddy_list_section_header, "buddy_list/section_header");
    verify_template_equivalence(view_all_subscribers, "buddy_list/view_all_subscribers");
    verify_template_equivalence(view_all_users, "buddy_list/view_all_users");
    verify_template_equivalence(empty_list_widget_for_list, "empty_list_widget_for_list");
    verify_template_equivalence(poll_widget, "widgets/poll_widget");
    verify_template_equivalence(presence_row, "presence_row");
    verify_template_equivalence(presence_rows, "presence_rows");
    // TODO: start looking at widget.as_raw_html();
});

run_test("dom check on presence_rows", () => {
    const widget = presence_rows();
    assert.ok(widget.as_raw_html().includes("user_sidebar_entry"));
});
