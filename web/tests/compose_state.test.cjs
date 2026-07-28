"use strict";

const assert = require("node:assert/strict");

const {make_realm} = require("./lib/example_realm.cjs");
const {make_stream} = require("./lib/example_stream.cjs");
const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test, noop} = require("./lib/test.cjs");
const $ = require("./lib/zjquery.cjs");

const compose_pm_pill = mock_esm("../src/compose_pm_pill");
// Every reply-serialization test overrides these, so the defaults are just
// overridable stubs (noop, like other mock_esm placeholders).
const markdown = mock_esm("../src/markdown", {render: noop});
const narrow_state = mock_esm("../src/narrow_state", {
    stream_name: noop,
    topic: noop,
});
const postprocess_content_mod = mock_esm("../src/postprocess_content", {
    postprocess_content: noop,
});

const compose_state = zrequire("compose_state");
const stream_data = zrequire("stream_data");
const {set_realm} = zrequire("state_data");

const realm = make_realm();
set_realm(realm);

run_test("private_message_recipient_emails", ({override}) => {
    override(compose_pm_pill, "get_emails", () => "fred@fred.org");
    assert.equal(compose_state.private_message_recipient_emails(), "fred@fred.org");
});

run_test("has_full_recipient", ({override}) => {
    $(`#compose_banners .topic_resolved`)[0].remove = noop;

    let user_ids;
    override(compose_pm_pill, "set_from_user_ids", (value) => {
        user_ids = value;
    });

    override(compose_pm_pill, "get_user_ids", () => user_ids);

    compose_state.set_message_type("stream");
    compose_state.set_stream_id("");
    compose_state.topic("");
    assert.equal(compose_state.has_full_recipient(), false);

    compose_state.topic("foo");
    assert.equal(compose_state.has_full_recipient(), false);

    stream_data.add_sub_for_tests(make_stream({name: "bar", stream_id: 99}));
    compose_state.set_stream_id(99);
    assert.equal(compose_state.has_full_recipient(), true);

    compose_state.set_message_type("private");
    compose_state.set_private_message_recipient_ids([]);
    assert.equal(compose_state.has_full_recipient(), false);

    compose_state.set_private_message_recipient_ids([123]);
    assert.equal(compose_state.has_full_recipient(), true);
});

// Helpers for the reply serialization tests: build a stub textarea +
// reply element tree that get_message_with_raw_reply_content can walk.
function build_reply_dom({textarea_value, full_name, user_id, silent, href, link_text}, label) {
    const $textarea = $.create(`textarea-${label}`);
    $textarea.val(textarea_value);

    const $container = $.create(`container-${label}`);
    $textarea.set_closest_results(
        "#message-content-container, .edit-content-container",
        $container,
    );

    const $reply = $.create(`reply-${label}`);
    $container.set_find_results(".reply", $reply);

    const $mention = $.create(`mention-${label}`);
    if (silent) {
        $mention.addClass("silent");
    }
    $mention.attr("data-user-id", String(user_id));
    $mention.attr("data-full-name", full_name);
    $mention.set_matches(".user-mention", true);
    $mention.set_matches(".referenced-message-link", false);

    const $link = $.create(`link-${label}`);
    $link.attr("href", href);
    $link.text(link_text);
    $link.set_matches(".user-mention", false);
    $link.set_matches(".referenced-message-link", true);

    // .children(selector) iterates real .children and filters with .matches().
    $reply.set_children([$mention[0], $link[0]]);

    return {$textarea, $reply, $mention, $link};
}

run_test("get_message_with_raw_reply_content returns body when no reply present", () => {
    const $textarea = $.create("plain-textarea");
    $textarea.val("hello world  ");

    const $container = $.create("plain-container");
    $textarea.set_closest_results(
        "#message-content-container, .edit-content-container",
        $container,
    );
    $container.set_find_results(".reply", $.create("empty-reply", {elements: []}));

    // Trailing whitespace is trimmed.
    assert.equal(compose_state.get_message_with_raw_reply_content($textarea), "hello world");
});

run_test("get_message_with_raw_reply_content emits non-silent mention", () => {
    const {$textarea} = build_reply_dom(
        {
            textarea_value: "Sounds good.",
            full_name: "Hamlet",
            user_id: 5,
            silent: false,
            href: "/#narrow/channel/9-devel/topic/grail/near/42",
            link_text: "Hello world",
        },
        "non-silent",
    );

    assert.equal(
        compose_state.get_message_with_raw_reply_content($textarea),
        "translated: @**Hamlet|5** [Hello world](/#narrow/channel/9-devel/topic/grail/near/42)\n\nSounds good.",
    );
});

run_test("get_message_with_raw_reply_content emits silent mention", () => {
    const {$textarea} = build_reply_dom(
        {
            textarea_value: "Sounds good.",
            full_name: "Hamlet",
            user_id: 5,
            silent: true,
            href: "/#narrow/channel/9-devel/topic/grail/near/42",
            link_text: "Hello world",
        },
        "silent",
    );

    assert.equal(
        compose_state.get_message_with_raw_reply_content($textarea),
        "translated: @_**Hamlet|5** [Hello world](/#narrow/channel/9-devel/topic/grail/near/42)\n\nSounds good.",
    );
});

run_test("get_message_with_raw_reply_content uses data-full-name, not displayed text", () => {
    // The displayed username always carries a leading `@` in the reply UI
    // — never strip from it during serialization. Use data-full-name.
    const {$textarea, $mention} = build_reply_dom(
        {
            textarea_value: "",
            full_name: "Hamlet",
            user_id: 5,
            silent: false,
            href: "/#narrow/channel/9-devel/topic/grail/near/42",
            link_text: "Hi",
        },
        "displayed-text",
    );
    // Even if some other code populated the displayed text wrongly, we
    // serialize from data-full-name.
    $mention.text("@WRONG-DISPLAYED-NAME");

    assert.equal(
        compose_state.get_message_with_raw_reply_content($textarea),
        "translated: @**Hamlet|5** [Hi](/#narrow/channel/9-devel/topic/grail/near/42)\n\n",
    );
});

run_test(
    "render_reply_and_get_parsed_message strips reply prefix when reply HTML rendered",
    ({override}) => {
        override(markdown, "render", () => ({content: "<markdown-output/>"}));
        override(
            postprocess_content_mod,
            "postprocess_content",
            () =>
                `<p><span class="reply"><span class="user-mention reply-user-mention" data-user-id="5" data-full-name="Hamlet">@Hamlet</span><a class="referenced-message-link" href="/url">Hi</a></span></p><p>Body</p>`,
        );

        const $container = $.create("reply-container-render");
        let html_written;
        $container.html = (value) => {
            html_written = value;
        };
        $container.hasClass = () => false;

        const message =
            "@**Hamlet|5** [Hi](/#narrow/channel/9-devel/topic/grail/near/42)\n\nBody text";
        const remainder = compose_state.render_reply_and_get_parsed_message(message, $container);

        assert.equal(remainder, "Body text");
        assert.match(html_written, /<span class="reply">/u);
    },
);

run_test(
    "render_reply_and_get_parsed_message strips reply prefix without a container",
    ({override}) => {
        // The message-edit flow calls this without a container to get the
        // stripped body for the textarea (the container doesn't exist yet).
        // If the strip were gated on the container, the reply markdown would
        // stay in the textarea and get duplicated on every save.
        override(markdown, "render", () => ({content: "<markdown-output/>"}));
        override(
            postprocess_content_mod,
            "postprocess_content",
            () =>
                `<p><span class="reply"><span class="user-mention reply-user-mention" data-user-id="5" data-full-name="Hamlet">@Hamlet</span><a class="referenced-message-link" href="/url">Hi</a></span></p><p>Body</p>`,
        );

        const message =
            "@**Hamlet|5** [Hi](/#narrow/channel/9-devel/topic/grail/near/42)\n\nBody text";
        const remainder = compose_state.render_reply_and_get_parsed_message(message);

        assert.equal(remainder, "Body text");
    },
);

run_test(
    "render_reply_and_get_parsed_message returns message unchanged when no reply",
    ({override}) => {
        override(markdown, "render", () => ({content: "<markdown-output/>"}));
        // postprocess output has NO .reply element → render_reply leaves the
        // message alone.
        override(postprocess_content_mod, "postprocess_content", () => "<p>Just a body</p>");

        const $container = $.create("no-reply-container");
        $container.hasClass = () => false;

        const message = "Just a body";
        const remainder = compose_state.render_reply_and_get_parsed_message(message, $container);

        assert.equal(remainder, message);
    },
);

run_test("delink_leading_reply_snippet de-links the pointer, keeps body", () => {
    // Quoting a reply: the leading reply line's snippet is a link to the
    // referenced message; inside a quote it would render as a stray blue link.
    // De-linking keeps the snippet text and the body, just drops the link.
    assert.equal(
        compose_state.delink_leading_reply_snippet(
            "@**Desdemona|9** [Original message.](http://host/#narrow/channel/3-Verona/topic/x/near/32)\n\nWorks for me!",
        ),
        "@**Desdemona|9** Original message.\n\nWorks for me!",
    );
    // Silent reply mention is handled too.
    assert.equal(
        compose_state.delink_leading_reply_snippet(
            "@_**Iago|5** [photo.png](http://host/#narrow/dm/7-Othello/near/42)\n\nBody",
        ),
        "@_**Iago|5** photo.png\n\nBody",
    );
    // A normal message that merely opens with a mention and a non-message link
    // is left untouched (no `/near/<id>`).
    const not_a_reply = "@**Iago|5** [the docs](https://example.com)\n\nrest";
    assert.equal(compose_state.delink_leading_reply_snippet(not_a_reply), not_a_reply);
    assert.equal(compose_state.delink_leading_reply_snippet("Just a body"), "Just a body");
});

run_test("serialize_reply_link_content converts unicode emoji to characters", () => {
    // Real DOM (not zjquery stubs): the server's rendered emoji span has
    // class `emoji emoji-<codepoint>`. We convert that to the Unicode
    // character so the markdown processor on the receiving side renders
    // it as an emoji (it doesn't reliably expand `:+1:` style shortcodes
    // inside link text).
    const doc = new DOMParser().parseFromString(
        '<a class="referenced-message-link" href="/url">' +
            'Hi <span aria-label="thumbs_up" class="emoji emoji-1f44d" role="img" title="thumbs_up">:+1:</span> ' +
            '<span aria-label="wave" class="emoji emoji-1f44b" role="img" title="wave">:wave:</span>' +
            "</a>",
        "text/html",
    );
    const link_el = doc.body.firstElementChild;
    const $link = {0: link_el, length: 1};
    assert.equal(compose_state.serialize_reply_link_content($link), "Hi 👍 👋");
});

run_test("serialize_reply_link_content keeps realm emoji shortcode", () => {
    // Realm (custom) emoji render as <img class="emoji" alt=":custom:">.
    // We can't convert those to Unicode, so we keep the shortcode in the
    // alt attribute — realm emoji shortcodes do round-trip through markdown.
    const doc = new DOMParser().parseFromString(
        '<a class="referenced-message-link" href="/url">' +
            'Hello <img alt=":custom:" class="emoji" src="/realm-emoji/x.png" title="custom">' +
            "</a>",
        "text/html",
    );
    const link_el = doc.body.firstElementChild;
    const $link = {0: link_el, length: 1};
    assert.equal(compose_state.serialize_reply_link_content($link), "Hello :custom:");
});

run_test(
    "render_reply_and_get_parsed_message uses narrow_state for edit container",
    ({override}) => {
        let postprocess_args;
        override(markdown, "render", () => ({content: "<markdown-output/>"}));
        override(postprocess_content_mod, "postprocess_content", (html, stream, topic_name) => {
            postprocess_args = {html, stream, topic_name};
            return "<p>No reply</p>";
        });
        override(narrow_state, "stream_name", () => "narrow-stream");
        override(narrow_state, "topic", () => "narrow-topic");

        const $container = $.create("edit-reply-container");
        $container.hasClass = (cls) => cls === "message-edit-reply-container";

        compose_state.render_reply_and_get_parsed_message("any message", $container);
        assert.deepEqual(
            {stream: postprocess_args.stream, topic: postprocess_args.topic_name},
            {stream: "narrow-stream", topic: "narrow-topic"},
        );
    },
);
