"use strict";

const assert = require("node:assert/strict");

const {make_stream} = require("./lib/example_stream.cjs");
const {zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const reply_snippet = zrequire("reply_snippet");
const sub_store = zrequire("sub_store");

function body(html) {
    return new DOMParser().parseFromString(html, "text/html").body;
}

function media(html) {
    return reply_snippet.classify_media_message(body(html));
}

run_test("classify image (legacy raw-content wrapper)", () => {
    assert.deepEqual(
        media(
            '<div class="message_inline_image">' +
                '<a href="/user_uploads/x/photo.png" title="photo.png">' +
                '<img src="/user_uploads/thumbnail/x/photo.png/840x560.webp"></a></div>',
        ),
        {
            type: "image",
            content: "photo.png",
            thumbnail_src: "/user_uploads/thumbnail/x/photo.png/840x560.webp",
        },
    );
});

run_test("classify modern inline image (bare img.inline-image)", () => {
    // Raw stored content of a `![...]` upload: a bare <img>, filename in alt,
    // thumbnail in src.
    assert.deepEqual(
        media(
            '<p><img class="inline-image" alt="pic.png" ' +
                'data-original-src="/user_uploads/x/pic.png" src="/thumb/pic.png"></p>',
        ),
        {type: "image", content: "pic.png", thumbnail_src: "/thumb/pic.png"},
    );
});

run_test("classify GIF by filename extension", () => {
    const snippet = media(
        '<div class="message_inline_image">' +
            '<a href="/u/anim.gif" title="anim.gif"><img src="/thumb/anim.gif"></a></div>',
    );
    assert.equal(snippet.type, "gif");
    assert.equal(snippet.content, "anim.gif");
});

run_test("classify image filename decoded from URL when no title", () => {
    const snippet = media(
        '<div class="message_inline_image">' +
            '<a href="/user_uploads/x/my%20photo.png"><img src="/thumb/x.webp"></a></div>',
    );
    assert.equal(snippet.type, "image");
    assert.equal(snippet.content, "my photo.png");
});

run_test("classify code block (first non-empty line as detail)", () => {
    assert.deepEqual(
        media(
            '<div class="codehilite" data-code-language="python"><pre>\nprint("hi")\n</pre></div>',
        ),
        {type: "code", content: 'print("hi")', thumbnail_src: ""},
    );
});

run_test("classify code block falls back to language, then bare", () => {
    assert.equal(
        media('<div class="codehilite" data-code-language="python"><pre>\n   \n</pre></div>')
            .content,
        "python",
    );
    assert.equal(media('<div class="codehilite"><pre>\n</pre></div>').content, "");
});

run_test("classify math block (LaTeX annotation as detail)", () => {
    assert.deepEqual(
        media(
            '<span class="katex-display"><span class="katex">' +
                '<annotation encoding="application/x-tex">x^2</annotation></span></span>',
        ),
        {type: "math", content: "x^2", thumbnail_src: ""},
    );
});

run_test("classify spoiler (header as detail)", () => {
    assert.deepEqual(
        media(
            '<div class="spoiler-block"><div class="spoiler-header"><p>Secret</p></div>' +
                '<div class="spoiler-content"><p>hidden</p></div></div>',
        ),
        {type: "spoiler", content: "Secret", thumbnail_src: ""},
    );
});

run_test("classify YouTube preview (video, thumbnail, link text)", () => {
    // A bare URL shows the URL as its link text.
    assert.deepEqual(
        media(
            '<p><a href="https://youtu.be/x">https://youtu.be/x</a></p>' +
                '<div class="youtube-video message_inline_image">' +
                '<a href="https://youtu.be/x"><img src="https://i.ytimg.com/vi/x/default.jpg"></a></div>',
        ),
        {
            type: "video",
            content: "https://youtu.be/x",
            thumbnail_src: "https://i.ytimg.com/vi/x/default.jpg",
        },
    );
    // A `[label](url)` link shows the custom label, not the thumbnail's anchor.
    assert.deepEqual(
        media(
            '<p><a href="https://youtu.be/x">Watch this</a></p>' +
                '<div class="youtube-video message_inline_image">' +
                '<a href="https://youtu.be/x"><img src="https://i.ytimg.com/vi/x/default.jpg"></a></div>',
        ),
        {
            type: "video",
            content: "Watch this",
            thumbnail_src: "https://i.ytimg.com/vi/x/default.jpg",
        },
    );
});

run_test("classify link/website embed (title + background-image thumbnail)", () => {
    const snippet = media(
        '<div class="message_embed">' +
            '<a class="message_embed_image" href="https://e.com" ' +
            'style="background-image: url(&quot;https://e.com/p.jpg&quot;)"></a>' +
            '<div class="message_embed_title"><a href="https://e.com">About us</a></div></div>',
    );
    assert.equal(snippet.type, "link");
    assert.equal(snippet.content, "About us");
    assert.equal(snippet.thumbnail_src, "https://e.com/p.jpg");
});

run_test("classify other oembed video (.embed-video: title + thumbnail)", () => {
    assert.deepEqual(
        media(
            '<div class="embed-video"><a title="Cool clip" href="https://vimeo.com/1">' +
                '<img src="/vimeo-thumb.jpg"></a></div>',
        ),
        {type: "video", content: "Cool clip", thumbnail_src: "/vimeo-thumb.jpg"},
    );
});

run_test("classify image with no filename source yields empty detail", () => {
    // No title/alt and no href: decode_filename_from_url("") returns "".
    assert.deepEqual(media('<div class="message_inline_image"><a><img></a></div>'), {
        type: "image",
        content: "",
        thumbnail_src: "",
    });
});

run_test("classify image tolerates an undecodable filename in the URL", () => {
    // A malformed %-escape makes decodeURIComponent throw; we fall back to "".
    assert.equal(
        media('<div class="message_inline_image"><a href="/u/bad%"><img></a></div>').content,
        "",
    );
});

run_test("classify link embed without a preview image has no thumbnail", () => {
    // extract_background_image_url(null) when there's no `.message_embed_image`.
    assert.equal(
        media(
            '<div class="message_embed"><div class="message_embed_title">' +
                '<a href="https://e.com">About</a></div></div>',
        ).thumbnail_src,
        "",
    );
});

run_test("classify uploaded video (filename + poster thumbnail)", () => {
    assert.deepEqual(
        media(
            '<div class="message_inline_video">' +
                '<a href="/u/clip.mp4" title="clip.mp4"><video poster="/poster.jpg"></video></a></div>',
        ),
        {type: "video", content: "clip.mp4", thumbnail_src: "/poster.jpg"},
    );
});

run_test("classify_media returns undefined for plain text", () => {
    assert.equal(media("<p>just some words</p>"), undefined);
});

run_test("classify poll widget (question as detail)", () => {
    assert.deepEqual(
        reply_snippet.classify_widget_message({
            submessages: [
                {
                    content: JSON.stringify({
                        widget_type: "poll",
                        extra_data: {question: "Lunch?", options: []},
                    }),
                },
            ],
        }),
        {type: "poll", content: "Lunch?", thumbnail_src: ""},
    );
});

run_test("classify poll widget reflects an edited question", () => {
    assert.equal(
        reply_snippet.classify_widget_message({
            submessages: [
                {content: JSON.stringify({widget_type: "poll", extra_data: {question: "Old?"}})},
                {content: JSON.stringify({type: "question", question: "New?"})},
            ],
        }).content,
        "New?",
    );
});

run_test("classify todo widget (title as detail; bare when none)", () => {
    assert.deepEqual(
        reply_snippet.classify_widget_message({
            submessages: [
                {
                    content: JSON.stringify({
                        widget_type: "todo",
                        extra_data: {task_list_title: "Chores"},
                    }),
                },
            ],
        }),
        {type: "todo", content: "Chores", thumbnail_src: ""},
    );
    assert.deepEqual(
        reply_snippet.classify_widget_message({
            submessages: [{content: JSON.stringify({widget_type: "todo", extra_data: {}})}],
        }),
        {type: "todo", content: "", thumbnail_src: ""},
    );
});

run_test("classify_widget reflects an edited title past a malformed event", () => {
    // A later submessage that isn't valid JSON is skipped, not fatal.
    assert.equal(
        reply_snippet.classify_widget_message({
            submessages: [
                {
                    content: JSON.stringify({
                        widget_type: "todo",
                        extra_data: {task_list_title: "A"},
                    }),
                },
                {content: "not json"},
                {content: JSON.stringify({type: "new_task_list_title", title: "B"})},
            ],
        }).content,
        "B",
    );
});

run_test("classify_widget returns undefined for non-widget messages", () => {
    assert.equal(reply_snippet.classify_widget_message({submessages: []}), undefined);
    assert.equal(reply_snippet.classify_widget_message({submessages: undefined}), undefined);
    assert.equal(
        reply_snippet.classify_widget_message({submessages: [{content: "not json"}]}),
        undefined,
    );
    // Valid JSON that isn't a widget object (e.g. a bare number).
    assert.equal(
        reply_snippet.classify_widget_message({submessages: [{content: "42"}]}),
        undefined,
    );
    // A widget type we don't render a snippet for.
    assert.equal(
        reply_snippet.classify_widget_message({
            submessages: [{content: JSON.stringify({widget_type: "zform"})}],
        }),
        undefined,
    );
});

run_test("localized_type_label uses the full descriptive name", () => {
    // Guards against abbreviating to "TODO": the badge is CSS-uppercased.
    assert.match(reply_snippet.localized_type_label("todo"), /Todo list$/u);
    assert.match(reply_snippet.localized_type_label("code"), /Code block$/u);
    assert.match(reply_snippet.localized_type_label("image"), /Image$/u);
    assert.match(reply_snippet.localized_type_label("video"), /Video$/u);
    assert.match(reply_snippet.localized_type_label("math"), /Math$/u);
    assert.match(reply_snippet.localized_type_label("link"), /Link$/u);
    assert.match(reply_snippet.localized_type_label("spoiler"), /Spoiler$/u);
});

run_test("render_reply_snippet caps an overlong detail", () => {
    const {content_html} = reply_snippet.render_reply_snippet({
        type: "image",
        content: "z".repeat(250),
        thumbnail_src: "",
    });
    // 200-char cap applies to the detail text, leaving the badge markup intact.
    assert.equal(content_html.match(/z/gu).length, 200);
});

run_test("build_type_badge_html wraps the label in a badge span", () => {
    assert.match(
        reply_snippet.build_type_badge_html("gif"),
        /^<span class="reply-type-badge">[^<]*GIF<\/span>$/u,
    );
});

run_test("render_reply_snippet emits badge + detail and a thumbnail slot", () => {
    const {content_html, thumbnail_html} = reply_snippet.render_reply_snippet({
        type: "image",
        content: "photo.png",
        thumbnail_src: "/t.webp",
    });
    assert.match(content_html, /^<span class="reply-type-badge">[^<]*Image<\/span> photo\.png$/u);
    assert.match(thumbnail_html, /^<img [^>]*class="reply-line-thumbnail"[^>]*>$/u);
    assert.match(thumbnail_html, /src="\/t\.webp"/u);
});

run_test("render_reply_snippet emits a bare badge and no thumbnail when empty", () => {
    const {content_html, thumbnail_html} = reply_snippet.render_reply_snippet({
        type: "poll",
        content: "",
        thumbnail_src: "",
    });
    assert.match(content_html, /^<span class="reply-type-badge">[^<]*Poll<\/span>$/u);
    assert.equal(thumbnail_html, "");
});

run_test("render_reply_snippet escapes the detail text", () => {
    const {content_html} = reply_snippet.render_reply_snippet({
        type: "image",
        content: "<script>evil",
        thumbnail_src: "",
    });
    assert.match(content_html, /&lt;script&gt;evil/u);
    // Case-insensitive and attribute-tolerant so this doesn't read as a
    // (broken) HTML sanitizer: the detail must never produce a real tag.
    assert.doesNotMatch(content_html, /<script[\s/>]/iu);
});

run_test("escape_html_text escapes markup characters", () => {
    assert.equal(reply_snippet.escape_html_text("<b>&"), "&lt;b&gt;&amp;");
});

run_test("condense_reply_line_html renders a list inline, comma-joined", () => {
    assert.equal(
        reply_snippet.condense_reply_line_html(
            body("<ul><li>Buy milk</li><li>Walk the dog</li></ul>"),
        ),
        "Buy milk, Walk the dog",
    );
});

run_test("condense_reply_line_html caps pathological input", () => {
    // The backstop cap is 4× the snippet length (CSS ellipsis does the visible
    // clipping); a 1000-char block is truncated to 800.
    assert.equal(
        reply_snippet.condense_reply_line_html(body(`<p>${"z".repeat(1000)}</p>`)).length,
        800,
    );
});

run_test("condense decorates a channel/topic link with its privacy icon", () => {
    sub_store.add_hydrated_sub(55, make_stream({stream_id: 55, name: "Rome"}));
    const html = reply_snippet.condense_reply_line_html(
        body(
            '<p><a class="stream-topic" data-stream-id="55" ' +
                'href="/#narrow/channel/55-Rome/topic/keurig">#Rome &gt; keurig</a></p>',
        ),
    );
    // The bare "#Rome" becomes a decorated channel name (privacy icon + name),
    // the topic is preserved, and it is no longer a nested <a>.
    assert.ok(html.includes("channel-privacy-type-icon"), html);
    assert.ok(html.includes("decorated-channel-name"), html);
    assert.ok(html.includes("Rome"), html);
    assert.ok(html.includes("&gt; keurig"), html);
    assert.ok(!html.includes("<a"), html);
});

run_test("condense leaves an unknown channel link as plain text", () => {
    // No sub in the store (e.g. a deleted channel): fall back to plain text.
    const html = reply_snippet.condense_reply_line_html(
        body(
            '<p><a class="stream-topic" data-stream-id="999" ' +
                'href="/#narrow/channel/999-Ghost/topic/x">#Ghost &gt; x</a></p>',
        ),
    );
    assert.equal(html, "#Ghost &gt; x");
});

run_test("condense decorates a message link using the stream id from its href", () => {
    // Message links carry no data-stream-id, so the stream id comes from the
    // href's /channel/{id}-name segment.
    sub_store.add_hydrated_sub(56, make_stream({stream_id: 56, name: "Paris"}));
    const html = reply_snippet.condense_reply_line_html(
        body(
            '<p><a class="message-link" ' +
                'href="/#narrow/channel/56-Paris/topic/x/near/9">#Paris &gt; x @ 💬</a></p>',
        ),
    );
    assert.ok(html.includes("channel-privacy-type-icon"), html);
    assert.ok(html.includes("Paris"), html);
    assert.ok(html.includes("&gt; x"), html);
    assert.ok(!html.includes("<a"), html);
});

run_test("condense unwraps a blockquote's paragraph into inline text", () => {
    // Replying to a quoted message: the first block is a blockquote wrapping a
    // <p>. The <p> must be unwrapped inline — a block <p> would escape the feed
    // reply card's own <p> and blank the snippet.
    assert.equal(
        reply_snippet.condense_reply_line_html(
            body("<blockquote><p>Quoting a message</p></blockquote>"),
        ),
        "Quoting a message",
    );
});

run_test("condense joins a blockquote's multiple paragraphs with a space", () => {
    assert.equal(
        reply_snippet.condense_reply_line_html(
            body("<blockquote><p>First</p><p>Second</p></blockquote>"),
        ),
        "First Second",
    );
});

run_test("condense leaves a channel link with no resolvable stream id as plain text", () => {
    // No data-stream-id and no /channel/{id} in the href: can't resolve the
    // channel, so fall back to unwrapping the link to plain text.
    const html = reply_snippet.condense_reply_line_html(
        body('<p><a class="message-link" href="/#narrow/is/starred">#Somewhere</a></p>'),
    );
    assert.equal(html, "#Somewhere");
});

// A quoted/forwarded message: an "X said:" attribution line, the quoted
// blockquote, and optionally the sender's own comment below it.
function quote_message(comment) {
    return body(
        '<p><span class="user-mention silent" data-user-id="11">Iago</span> ' +
            '<a href="/#narrow/channel/3-Verona/topic/x/near/5">said</a>:</p>' +
            "<blockquote><p>quoted text</p></blockquote>" +
            (comment === "" ? "" : `<p>${comment}</p>`),
    );
}

run_test("quote reply shows the sender's comment below the quote", () => {
    const root = quote_message("my comment");
    reply_snippet.drop_leading_quote_context(root);
    assert.equal(reply_snippet.condense_reply_line_html(root), "my comment");
});

run_test("quote reply with no comment falls back to the quoted content", () => {
    const root = quote_message("");
    reply_snippet.drop_leading_quote_context(root);
    assert.equal(reply_snippet.condense_reply_line_html(root), "quoted text");
});

run_test("quote-context skip does not misfire on a bare reply pointer", () => {
    // A reply pointer is exactly [mention, near-link] with no trailing text, even
    // when followed by a blockquote; it's left for drop_leading_reply_block.
    const root = body(
        '<p><span class="user-mention" data-user-id="11">Iago</span> ' +
            '<a href="/#narrow/channel/3-Verona/topic/x/near/5">snippet</a></p>' +
            "<blockquote><p>q</p></blockquote>",
    );
    reply_snippet.drop_leading_quote_context(root);
    assert.ok(root.querySelector("p > .user-mention") !== null);
});
