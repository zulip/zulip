"use strict";

const assert = require("node:assert/strict");

require("./lib/i18n.cjs");
const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

mock_esm("../src/ui_util", {
    parse_html: (html) => html,
});

const preview_urls = zrequire("preview_urls");

run_test("github_issue_icon_name", () => {
    assert.equal(preview_urls.github_issue_icon_name({state: "open", state_reason: null}), "open");
    assert.equal(
        preview_urls.github_issue_icon_name({state: "open", state_reason: "reopened"}),
        "open",
    );
    assert.equal(
        preview_urls.github_issue_icon_name({state: "closed", state_reason: "completed"}),
        "closed-completed",
    );
    assert.equal(
        preview_urls.github_issue_icon_name({state: "closed", state_reason: "not_planned"}),
        "closed-not_planned",
    );
    assert.equal(
        preview_urls.github_issue_icon_name({state: "closed", state_reason: null}),
        "closed",
    );
});

run_test("github_pull_request_icon_name", () => {
    assert.equal(
        preview_urls.github_pull_request_icon_name({state: "open", draft: false, merged_at: null}),
        "open",
    );
    assert.equal(
        preview_urls.github_pull_request_icon_name({state: "open", draft: true, merged_at: null}),
        "open-draft",
    );
    assert.equal(
        preview_urls.github_pull_request_icon_name({
            state: "closed",
            draft: false,
            merged_at: null,
        }),
        "closed",
    );
    assert.equal(
        preview_urls.github_pull_request_icon_name({
            state: "closed",
            draft: false,
            merged_at: "2026-01-01T00:00:00Z",
        }),
        "closed-merged",
    );
    // A merged pull request renders as merged even if `draft` is somehow set.
    assert.equal(
        preview_urls.github_pull_request_icon_name({
            state: "closed",
            draft: true,
            merged_at: "2026-01-01T00:00:00Z",
        }),
        "closed-merged",
    );
});

run_test("set_url_preview_tooltip_content", ({mock_template}) => {
    let template_data;
    mock_template("url_preview_tooltip.hbs", false, (data) => {
        template_data = data;
        return "<stub-html>";
    });

    let content;
    const instance = {
        setContent(rendered) {
            content = rendered;
        },
    };

    preview_urls.set_url_preview_tooltip_content(
        {
            platform: "github",
            type: "issue",
            title: "Fix the bug",
            owner: "zulip",
            repo: "zulip",
            number: "19710",
            author: "alya",
            state: "closed",
            state_reason: "completed",
        },
        instance,
    );
    assert.equal(template_data.title, "Fix the bug");
    assert.equal(template_data.details, "translated: zulip/zulip#19710 opened by alya");
    assert.equal(template_data.icon_path, "/static/images/github/issue/closed-completed.svg");
    assert.equal(content, "<stub-html>");

    preview_urls.set_url_preview_tooltip_content(
        {
            platform: "github",
            type: "pull_request",
            title: "Add the feature",
            owner: "zulip",
            repo: "zulip",
            number: "42",
            author: "brijsiyag",
            state: "open",
            draft: true,
            merged_at: null,
        },
        instance,
    );
    assert.equal(template_data.icon_path, "/static/images/github/pull_request/open-draft.svg");
    assert.equal(template_data.details, "translated: zulip/zulip#42 opened by brijsiyag");

    // An unrecognized platform (only reachable if a future schema variant is
    // added without a matching case) is ignored rather than crashing.
    content = undefined;
    preview_urls.set_url_preview_tooltip_content({platform: "gitlab"}, instance);
    assert.equal(content, undefined);
});
