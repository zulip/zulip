"use strict";

zrequire("hash_util");

const emoji = zrequire("emoji", "shared/js/emoji");
const emoji_codes = zrequire("emoji_codes", "generated/emoji/emoji_codes.json");
const fenced_code = zrequire("fenced_code", "shared/js/fenced_code");
const markdown_config = zrequire("markdown_config");
const marked = zrequire("marked", "third/marked/lib/marked");

zrequire("markdown");
zrequire("message_store");
const people = zrequire("people");
zrequire("stream_data");
zrequire("user_groups");

set_global("location", {
    origin: "http://zulip.zulipdev.com",
});

const emoji_params = {
    realm_emoji: {
        1: {
            id: 1,
            name: "burrito",
            source_url: "/static/generated/emoji/images/emoji/burrito.png",
            deactivated: false,
        },
    },
    emoji_codes,
};

set_global("page_params", {
    realm_users: [],
    realm_filters: [
        ["#(?P<id>[0-9]{2,8})", "https://trac.example.com/ticket/%(id)s"],
        ["ZBUG_(?P<id>[0-9]{2,8})", "https://trac2.zulip.net/ticket/%(id)s"],
        [
            "ZGROUP_(?P<id>[0-9]{2,8}):(?P<zone>[0-9]{1,8})",
            "https://zone_%(zone)s.zulip.net/ticket/%(id)s",
        ],
    ],
    translate_emoticons: false,
});

function Image() {
    return {};
}
set_global("Image", Image);
emoji.initialize(emoji_params);

const doc = "";
set_global("document", doc);

set_global("$", global.make_zjquery());

const cordelia = {
    full_name: "Cordelia Lear",
    user_id: 101,
    email: "cordelia@zulip.com",
};
people.add_active_user(cordelia);

people.add_active_user({
    full_name: "Leo",
    user_id: 102,
    email: "leo@zulip.com",
});

people.add_active_user({
    full_name: "Bobby <h1>Tables</h1>",
    user_id: 103,
    email: "bobby@zulip.com",
});

people.add_active_user({
    full_name: "Mark Twin",
    user_id: 104,
    email: "twin1@zulip.com",
});

people.add_active_user({
    full_name: "Mark Twin",
    user_id: 105,
    email: "twin2@zulip.com",
});

people.add_active_user({
    full_name: "Brother of Bobby|123",
    user_id: 106,
    email: "bobby2@zulip.com",
});

people.add_active_user({
    full_name: "& & &amp;",
    user_id: 107,
    email: "ampampamp@zulip.com",
});

people.initialize_current_user(cordelia.user_id);

const hamletcharacters = {
    name: "hamletcharacters",
    id: 1,
    description: "Characters of Hamlet",
    members: [cordelia.user_id],
};

const backend = {
    name: "Backend",
    id: 2,
    description: "Backend team",
    members: [],
};

const edgecase_group = {
    name: "Bobby <h1>Tables</h1>",
    id: 3,
    description: "HTML Syntax to check for Markdown edge cases.",
    members: [],
};

const amp_group = {
    name: "& & &amp;",
    id: 4,
    description: "Check ampersand escaping",
    members: [],
};

global.user_groups.add(hamletcharacters);
global.user_groups.add(backend);
global.user_groups.add(edgecase_group);
global.user_groups.add(amp_group);

const stream_data = global.stream_data;
const denmark = {
    subscribed: false,
    color: "blue",
    name: "Denmark",
    stream_id: 1,
    is_muted: true,
};
const social = {
    subscribed: true,
    color: "red",
    name: "social",
    stream_id: 2,
    is_muted: false,
    invite_only: true,
};
const edgecase_stream = {
    subscribed: true,
    color: "green",
    name: "Bobby <h1>Tables</h1>",
    stream_id: 3,
    is_muted: false,
};
const edgecase_stream_2 = {
    subscribed: true,
    color: "yellow",
    name: "Bobby <h1",
    stream_id: 4,
    is_muted: false,
};
const amp_stream = {
    subscribed: true,
    color: "orange",
    name: "& & &amp;",
    stream_id: 5,
    is_muted: false,
};
stream_data.add_sub(denmark);
stream_data.add_sub(social);
stream_data.add_sub(edgecase_stream);
stream_data.add_sub(edgecase_stream_2);
// Note: edgecase_stream cannot be mentioned because it is caught by
// streamTopicHandler and it would be parsed as edgecase_stream_2.
stream_data.add_sub(amp_stream);

// Check the default behavior of fenced code blocks
// works properly before Markdown is initialized.
run_test("fenced_block_defaults", () => {
    const input = "\n```\nfenced code\n```\n\nand then after\n";
    const expected =
        '\n\n<div class="codehilite"><pre><span></span><code>fenced code\n</code></pre></div>\n\n\n\nand then after\n\n';
    const output = fenced_code.process_fenced_code(input);
    assert.equal(output, expected);
});

markdown.initialize(page_params.realm_filters, markdown_config.get_helpers());

const markdown_data = global.read_fixture_data("markdown_test_cases.json");

run_test("markdown_detection", () => {
    const no_markup = [
        "This is a plaintext message",
        "This is a plaintext: message",
        "This is a :plaintext message",
        "This is a :plaintext message: message",
        "Contains a not an image.jpeg/ok file",
        "Contains a not an http://www.google.com/ok/image.png/stop file",
        "No png to be found here, a png",
        "No user mention **leo**",
        "No user mention @what there",
        "No group mention *hamletcharacters*",
        'We like to code\n~~~\ndef code():\n    we = "like to do"\n~~~',
        "This is a\nmultiline :emoji: here\n message",
        "This is an :emoji: message",
        "User Mention @**leo**",
        "User Mention @**leo f**",
        "User Mention @**leo with some name**",
        "Group Mention @*hamletcharacters*",
        "Stream #**Verona**",
    ];

    const markup = [
        "Contains a https://zulip.com/image.png file",
        "Contains a https://zulip.com/image.jpg file",
        "https://zulip.com/image.jpg",
        "also https://zulip.com/image.jpg",
        "https://zulip.com/image.jpg too",
        "Contains a zulip.com/foo.jpeg file",
        "Contains a https://zulip.com/image.png file",
        "twitter url https://twitter.com/jacobian/status/407886996565016579",
        "https://twitter.com/jacobian/status/407886996565016579",
        "then https://twitter.com/jacobian/status/407886996565016579",
        "twitter url http://twitter.com/jacobian/status/407886996565016579",
        "youtube url https://www.youtube.com/watch?v=HHZ8iqswiCw&feature=youtu.be&a",
    ];

    no_markup.forEach((content) => {
        assert.equal(markdown.contains_backend_only_syntax(content), false);
    });

    markup.forEach((content) => {
        assert.equal(markdown.contains_backend_only_syntax(content), true);
    });
});

run_test("marked_shared", () => {
    const tests = markdown_data.regular_tests;

    tests.forEach((test) => {
        // Ignore tests if specified
        if (test.ignore === true) {
            return;
        }

        const message = {raw_content: test.input};
        page_params.translate_emoticons = test.translate_emoticons || false;
        markdown.apply_markdown(message);
        const output = message.content;
        const error_message = `Failure in test: ${test.name}`;
        if (test.marked_expected_output) {
            global.markdown_assert.notEqual(test.expected_output, output, error_message);
            global.markdown_assert.equal(test.marked_expected_output, output, error_message);
        } else if (test.backend_only_rendering) {
            assert.equal(markdown.contains_backend_only_syntax(test.input), true);
        } else {
            global.markdown_assert.equal(test.expected_output, output, error_message);
        }
    });
});

run_test("message_flags", () => {
    let message = {raw_content: "@**Leo**"};
    markdown.apply_markdown(message);
    assert(!message.mentioned);
    assert(!message.mentioned_me_directly);

    message = {raw_content: "@**Cordelia Lear**"};
    markdown.apply_markdown(message);
    assert(message.mentioned);
    assert(message.mentioned_me_directly);

    message = {raw_content: "@**all**"};
    markdown.apply_markdown(message);
    assert(message.mentioned);
    assert(!message.mentioned_me_directly);
});

run_test("marked", () => {
    const test_cases = [
        {input: "hello", expected: "<p>hello</p>"},
        {input: "hello there", expected: "<p>hello there</p>"},
        {input: "hello **bold** for you", expected: "<p>hello <strong>bold</strong> for you</p>"},
        {
            input: "hello ***foo*** for you",
            expected: "<p>hello <strong><em>foo</em></strong> for you</p>",
        },
        {input: "__hello__", expected: "<p>__hello__</p>"},
        {
            input: "\n```\nfenced code\n```\n\nand then after\n",
            expected:
                '<div class="codehilite"><pre><span></span><code>fenced code\n</code></pre></div>\n\n\n<p>and then after</p>',
        },
        {
            input:
                "\n```\n    fenced code trailing whitespace            \n```\n\nand then after\n",
            expected:
                '<div class="codehilite"><pre><span></span><code>    fenced code trailing whitespace\n</code></pre></div>\n\n\n<p>and then after</p>',
        },
        {
            input: "* a\n* list \n* here",
            expected: "<ul>\n<li>a</li>\n<li>list </li>\n<li>here</li>\n</ul>",
        },
        {
            input: "\n```c#\nfenced code special\n```\n\nand then after\n",
            expected:
                '<div class="codehilite"><pre><span></span><code>fenced code special\n</code></pre></div>\n\n\n<p>and then after</p>',
        },
        {
            input: "\n```vb.net\nfenced code dot\n```\n\nand then after\n",
            expected:
                '<div class="codehilite"><pre><span></span><code>fenced code dot\n</code></pre></div>\n\n\n<p>and then after</p>',
        },
        {
            input: "Some text first\n* a\n* list \n* here\n\nand then after",
            expected:
                "<p>Some text first</p>\n<ul>\n<li>a</li>\n<li>list </li>\n<li>here</li>\n</ul>\n<p>and then after</p>",
        },
        {
            input: "1. an\n2. ordered \n3. list",
            expected: "<ol>\n<li>an</li>\n<li>ordered </li>\n<li>list</li>\n</ol>",
        },
        {
            input: "\n~~~quote\nquote this for me\n~~~\nthanks\n",
            expected: "<blockquote>\n<p>quote this for me</p>\n</blockquote>\n<p>thanks</p>",
        },
        {
            input: "This is a @**CordeLIA Lear** mention",
            expected:
                '<p>This is a <span class="user-mention" data-user-id="101">@Cordelia Lear</span> mention</p>',
        },
        {
            input: "These @ @**** are not mentions",
            expected: "<p>These @ @<em>**</em> are not mentions</p>",
        },
        {
            input: "These # #**** are not mentions",
            expected: "<p>These # #<em>**</em> are not mentions</p>",
        },
        {input: "These @* are not mentions", expected: "<p>These @* are not mentions</p>"},
        {
            input: "These #* #*** are also not mentions",
            expected: "<p>These #* #*** are also not mentions</p>",
        },
        {
            input: "This is a #**Denmark** stream link",
            expected:
                '<p>This is a <a class="stream" data-stream-id="1" href="/#narrow/stream/1-Denmark">#Denmark</a> stream link</p>',
        },
        {
            input: "This is #**Denmark** and #**social** stream links",
            expected:
                '<p>This is <a class="stream" data-stream-id="1" href="/#narrow/stream/1-Denmark">#Denmark</a> and <a class="stream" data-stream-id="2" href="/#narrow/stream/2-social">#social</a> stream links</p>',
        },
        {
            input: "And this is a #**wrong** stream link",
            expected: "<p>And this is a #**wrong** stream link</p>",
        },
        {
            input: "This is a #**Denmark>some topic** stream_topic link",
            expected:
                '<p>This is a <a class="stream-topic" data-stream-id="1" href="/#narrow/stream/1-Denmark/topic/some.20topic">#Denmark > some topic</a> stream_topic link</p>',
        },
        {
            input: "This has two links: #**Denmark>some topic** and #**social>other topic**.",
            expected:
                '<p>This has two links: <a class="stream-topic" data-stream-id="1" href="/#narrow/stream/1-Denmark/topic/some.20topic">#Denmark > some topic</a> and <a class="stream-topic" data-stream-id="2" href="/#narrow/stream/2-social/topic/other.20topic">#social > other topic</a>.</p>',
        },
        {
            input: "This is not a #**Denmark>** stream_topic link",
            expected: "<p>This is not a #**Denmark&gt;** stream_topic link</p>",
        },
        {
            input: "mmm...:burrito:s",
            expected:
                '<p>mmm...<img alt=":burrito:" class="emoji" src="/static/generated/emoji/images/emoji/burrito.png" title="burrito">s</p>',
        },
        {
            input: "This is an :poop: message",
            expected:
                '<p>This is an <span aria-label="poop" class="emoji emoji-1f4a9" role="img" title="poop">:poop:</span> message</p>',
        },
        {
            input: "\ud83d\udca9",
            expected:
                '<p><span aria-label="poop" class="emoji emoji-1f4a9" role="img" title="poop">:poop:</span></p>',
        },
        {
            input: "Silent mention: @_**Cordelia Lear**",
            expected:
                '<p>Silent mention: <span class="user-mention silent" data-user-id="101">Cordelia Lear</span></p>',
        },
        {
            input:
                "> Mention in quote: @**Cordelia Lear**\n\nMention outside quote: @**Cordelia Lear**",
            expected:
                '<blockquote>\n<p>Mention in quote: <span class="user-mention silent" data-user-id="101">Cordelia Lear</span></p>\n</blockquote>\n<p>Mention outside quote: <span class="user-mention" data-user-id="101">@Cordelia Lear</span></p>',
        },
        // Test only those realm filters which don't return True for
        // `contains_backend_only_syntax()`. Those which return True
        // are tested separately.
        {
            input: "This is a realm filter #1234 with text after it",
            expected:
                '<p>This is a realm filter <a href="https://trac.example.com/ticket/1234" title="https://trac.example.com/ticket/1234">#1234</a> with text after it</p>',
        },
        {input: "#1234is not a realm filter.", expected: "<p>#1234is not a realm filter.</p>"},
        {
            input: "A pattern written as #1234is not a realm filter.",
            expected: "<p>A pattern written as #1234is not a realm filter.</p>",
        },
        {
            input: "This is a realm filter with ZGROUP_123:45 groups",
            expected:
                '<p>This is a realm filter with <a href="https://zone_45.zulip.net/ticket/123" title="https://zone_45.zulip.net/ticket/123">ZGROUP_123:45</a> groups</p>',
        },
        {input: "Test *italic*", expected: "<p>Test <em>italic</em></p>"},
        {
            input: "T\n#**Denmark**",
            expected:
                '<p>T<br>\n<a class="stream" data-stream-id="1" href="/#narrow/stream/1-Denmark">#Denmark</a></p>',
        },
        {
            input: "T\n@**Cordelia Lear**",
            expected:
                '<p>T<br>\n<span class="user-mention" data-user-id="101">@Cordelia Lear</span></p>',
        },
        {
            input: "@**Mark Twin|104** and @**Mark Twin|105** are out to confuse you.",
            expected:
                '<p><span class="user-mention" data-user-id="104">@Mark Twin</span> and <span class="user-mention" data-user-id="105">@Mark Twin</span> are out to confuse you.</p>',
        },
        {input: "@**Invalid User|1234**", expected: "<p>@**Invalid User|1234**</p>"},
        {
            input: "@**Cordelia LeAR|103** has a wrong user_id.",
            expected: "<p>@**Cordelia LeAR|103** has a wrong user_id.</p>",
        },
        {
            input: "@**Brother of Bobby|123** is really the full name.",
            expected:
                '<p><span class="user-mention" data-user-id="106">@Brother of Bobby|123</span> is really the full name.</p>',
        },
        {
            input: "@**Brother of Bobby|123|106**",
            expected:
                '<p><span class="user-mention" data-user-id="106">@Brother of Bobby|123</span></p>',
        },
        {input: "T\n@hamletcharacters", expected: "<p>T<br>\n@hamletcharacters</p>"},
        {
            input: "T\n@*hamletcharacters*",
            expected:
                '<p>T<br>\n<span class="user-group-mention" data-user-group-id="1">@hamletcharacters</span></p>',
        },
        {input: "T\n@*notagroup*", expected: "<p>T<br>\n@*notagroup*</p>"},
        {
            input: "T\n@*backend*",
            expected:
                '<p>T<br>\n<span class="user-group-mention" data-user-group-id="2">@Backend</span></p>',
        },
        {input: "@*notagroup*", expected: "<p>@*notagroup*</p>"},
        {
            input: "This is a realm filter `hello` with text after it",
            expected: "<p>This is a realm filter <code>hello</code> with text after it</p>",
        },
        // Test the emoticon conversion
        {input: ":)", expected: "<p>:)</p>"},
        {
            input: ":)",
            expected:
                '<p><span aria-label="smile" class="emoji emoji-1f642" role="img" title="smile">:smile:</span></p>',
            translate_emoticons: true,
        },
        // Test HTML Escape in Custom Zulip Rules
        {
            input: "@**<h1>The Rogue One</h1>**",
            expected: "<p>@**&lt;h1&gt;The Rogue One&lt;/h1&gt;**</p>",
        },
        {
            input: "#**<h1>The Rogue One</h1>**",
            expected: "<p>#**&lt;h1&gt;The Rogue One&lt;/h1&gt;**</p>",
        },
        {
            input: ":<h1>The Rogue One</h1>:",
            expected: "<p>:&lt;h1&gt;The Rogue One&lt;/h1&gt;:</p>",
        },
        {input: "@**O'Connell**", expected: "<p>@**O&#39;Connell**</p>"},
        {
            input: "@*Bobby <h1>Tables</h1>*",
            expected:
                '<p><span class="user-group-mention" data-user-group-id="3">@Bobby &lt;h1&gt;Tables&lt;/h1&gt;</span></p>',
        },
        {
            input: "@*& &amp; &amp;amp;*",
            expected:
                '<p><span class="user-group-mention" data-user-group-id="4">@&amp; &amp; &amp;amp;</span></p>',
        },
        {
            input: "@**Bobby <h1>Tables</h1>**",
            expected:
                '<p><span class="user-mention" data-user-id="103">@Bobby &lt;h1&gt;Tables&lt;/h1&gt;</span></p>',
        },
        {
            input: "@**& &amp; &amp;amp;**",
            expected:
                '<p><span class="user-mention" data-user-id="107">@&amp; &amp; &amp;amp;</span></p>',
        },
        {
            input: "#**Bobby <h1>Tables</h1>**",
            expected:
                '<p><a class="stream-topic" data-stream-id="4" href="/#narrow/stream/4-Bobby-.3Ch1/topic/Tables.3C.2Fh1.3E">#Bobby &lt;h1 > Tables&lt;/h1&gt;</a></p>',
        },
        {
            input: "#**& &amp; &amp;amp;**",
            expected:
                '<p><a class="stream" data-stream-id="5" href="/#narrow/stream/5-.26-.26.20.26amp.3B">#&amp; &amp; &amp;amp;</a></p>',
        },
        {
            input: "#**& &amp; &amp;amp;>& &amp; &amp;amp;**",
            expected:
                '<p><a class="stream-topic" data-stream-id="5" href="/#narrow/stream/5-.26-.26.20.26amp.3B/topic/.26.20.26.20.26amp.3B">#&amp; &amp; &amp;amp; > &amp; &amp; &amp;amp;</a></p>',
        },
    ];

    test_cases.forEach((test_case) => {
        // Disable emoji conversion by default.
        page_params.translate_emoticons = test_case.translate_emoticons || false;

        const input = test_case.input;
        const expected = test_case.expected;

        const message = {raw_content: input};
        markdown.apply_markdown(message);
        const output = message.content;
        assert.equal(output, expected);
    });
});

run_test("topic_links", () => {
    let message = {type: "stream", topic: "No links here"};
    markdown.add_topic_links(message);
    assert.equal(message.topic_links.length, 0);

    message = {type: "stream", topic: "One #123 link here"};
    markdown.add_topic_links(message);
    assert.equal(message.topic_links.length, 1);
    assert.equal(message.topic_links[0], "https://trac.example.com/ticket/123");

    message = {type: "stream", topic: "Two #123 #456 link here"};
    markdown.add_topic_links(message);
    assert.equal(message.topic_links.length, 2);
    assert.equal(message.topic_links[0], "https://trac.example.com/ticket/123");
    assert.equal(message.topic_links[1], "https://trac.example.com/ticket/456");

    message = {type: "stream", topic: "New ZBUG_123 link here"};
    markdown.add_topic_links(message);
    assert.equal(message.topic_links.length, 1);
    assert.equal(message.topic_links[0], "https://trac2.zulip.net/ticket/123");

    message = {type: "stream", topic: "New ZBUG_123 with #456 link here"};
    markdown.add_topic_links(message);
    assert.equal(message.topic_links.length, 2);
    assert(message.topic_links.includes("https://trac2.zulip.net/ticket/123"));
    assert(message.topic_links.includes("https://trac.example.com/ticket/456"));

    message = {type: "stream", topic: "One ZGROUP_123:45 link here"};
    markdown.add_topic_links(message);
    assert.equal(message.topic_links.length, 1);
    assert.equal(message.topic_links[0], "https://zone_45.zulip.net/ticket/123");

    message = {type: "stream", topic: "Hello https://google.com"};
    markdown.add_topic_links(message);
    assert.equal(message.topic_links.length, 1);
    assert.equal(message.topic_links[0], "https://google.com");

    message = {type: "stream", topic: "#456 https://google.com https://github.com"};
    markdown.add_topic_links(message);
    assert.equal(message.topic_links.length, 3);
    assert(message.topic_links.includes("https://google.com"));
    assert(message.topic_links.includes("https://github.com"));
    assert(message.topic_links.includes("https://trac.example.com/ticket/456"));

    message = {type: "not-stream"};
    markdown.add_topic_links(message);
    assert.equal(message.topic_links.length, 0);
});

run_test("message_flags", () => {
    let input = "/me is testing this";
    let message = {topic: "No links here", raw_content: input};
    markdown.apply_markdown(message);

    assert.equal(message.is_me_message, true);
    assert(!message.unread);

    input = "/me is testing\nthis";
    message = {topic: "No links here", raw_content: input};
    markdown.apply_markdown(message);

    assert.equal(message.is_me_message, true);

    input = "testing this @**all** @**Cordelia Lear**";
    message = {topic: "No links here", raw_content: input};
    markdown.apply_markdown(message);

    assert.equal(message.is_me_message, false);
    assert.equal(message.mentioned, true);
    assert.equal(message.mentioned_me_directly, true);

    input = "test @**everyone**";
    message = {topic: "No links here", raw_content: input};
    markdown.apply_markdown(message);
    assert.equal(message.is_me_message, false);
    assert.equal(message.mentioned, true);
    assert.equal(message.mentioned_me_directly, false);

    input = "test @**stream**";
    message = {topic: "No links here", raw_content: input};
    markdown.apply_markdown(message);
    assert.equal(message.is_me_message, false);
    assert.equal(message.mentioned, true);
    assert.equal(message.mentioned_me_directly, false);

    input = "test @all";
    message = {topic: "No links here", raw_content: input};
    markdown.apply_markdown(message);
    assert.equal(message.mentioned, false);

    input = "test @everyone";
    message = {topic: "No links here", raw_content: input};
    markdown.apply_markdown(message);
    assert.equal(message.mentioned, false);

    input = "test @any";
    message = {topic: "No links here", raw_content: input};
    markdown.apply_markdown(message);
    assert.equal(message.mentioned, false);

    input = "test @alleycat.com";
    message = {topic: "No links here", raw_content: input};
    markdown.apply_markdown(message);
    assert.equal(message.mentioned, false);

    input = "test @*hamletcharacters*";
    message = {topic: "No links here", raw_content: input};
    markdown.apply_markdown(message);
    assert.equal(message.mentioned, true);

    input = "test @*backend*";
    message = {topic: "No links here", raw_content: input};
    markdown.apply_markdown(message);
    assert.equal(message.mentioned, false);

    input = "test @**invalid_user**";
    message = {topic: "No links here", raw_content: input};
    markdown.apply_markdown(message);
    assert.equal(message.mentioned, false);
});

run_test("backend_only_realm_filters", () => {
    const backend_only_realm_filters = [
        "Here is the PR-#123.",
        "Function abc() was introduced in (PR)#123.",
    ];
    backend_only_realm_filters.forEach((content) => {
        assert.equal(markdown.contains_backend_only_syntax(content), true);
    });
});

run_test("python_to_js_filter", () => {
    // The only way to reach python_to_js_filter is indirectly, hence the call
    // to update_realm_filter_rules.
    markdown.update_realm_filter_rules([["/a(?im)a/g"], ["/a(?L)a/g"]]);
    let actual_value = marked.InlineLexer.rules.zulip.realm_filters;
    let expected_value = [/\/aa\/g(?![\w])/gim, /\/aa\/g(?![\w])/g];
    assert.deepEqual(actual_value, expected_value);
    // Test case with multiple replacements.
    markdown.update_realm_filter_rules([
        ["#cf(?P<contest>[0-9]+)(?P<problem>[A-Z][0-9A-Z]*)", "http://google.com"],
    ]);
    actual_value = marked.InlineLexer.rules.zulip.realm_filters;
    expected_value = [/#cf([0-9]+)([A-Z][0-9A-Z]*)(?![\w])/g];
    assert.deepEqual(actual_value, expected_value);
    // Test incorrect syntax.
    blueslip.expect(
        "error",
        "python_to_js_filter: Invalid regular expression: /!@#@(!#&((!&(@#((?![\\w])/: Unterminated group",
    );
    markdown.update_realm_filter_rules([["!@#@(!#&((!&(@#(", "http://google.com"]]);
    actual_value = marked.InlineLexer.rules.zulip.realm_filters;
    expected_value = [];
    assert.deepEqual(actual_value, expected_value);
});

run_test("translate_emoticons_to_names", () => {
    // Simple test
    const test_text = "Testing :)";
    const expected = "Testing :smile:";
    const result = markdown.translate_emoticons_to_names(test_text);
    assert.equal(result, expected);

    // Extensive tests.
    // The following code loops over the test cases and each emoticon conversion
    // to generate multiple test cases.
    const testcases = [
        {name: "only emoticon", original: "<original>", expected: "<converted>"},
        {name: "space at start", original: " <original>", expected: " <converted>"},
        {name: "space at end", original: "<original> ", expected: "<converted> "},
        {name: "symbol at end", original: "<original>!", expected: "<converted>!"},
        {name: "symbol at start", original: "Hello,<original>", expected: "Hello,<converted>"},
        {name: "after a word", original: "Hello<original>", expected: "Hello<original>"},
        {name: "between words", original: "Hello<original>World", expected: "Hello<original>World"},
        {
            name: "end of sentence",
            original: "End of sentence. <original>",
            expected: "End of sentence. <converted>",
        },
        {
            name: "between symbols",
            original: "Hello.<original>! World.",
            expected: "Hello.<original>! World.",
        },
        {
            name: "before end of sentence",
            original: "Hello <original>!",
            expected: "Hello <converted>!",
        },
    ];
    for (const [shortcut, full_name] of Object.entries(emoji_codes.emoticon_conversions)) {
        for (const t of testcases) {
            const converted_value = full_name;
            let original = t.original;
            let expected = t.expected;
            original = original.replace(/(<original>)/g, shortcut);
            expected = expected
                .replace(/(<original>)/g, shortcut)
                .replace(/(<converted>)/g, converted_value);
            const result = markdown.translate_emoticons_to_names(original);
            assert.equal(result, expected);
        }
    }
});

run_test("missing unicode emojis", () => {
    const message = {raw_content: "\u{1f6b2}"};

    markdown.apply_markdown(message);
    assert.equal(
        message.content,
        '<p><span aria-label="bike" class="emoji emoji-1f6b2" role="img" title="bike">:bike:</span></p>',
    );

    // Now simulate that we don't know any emoji names.
    function fake_get_emoji_name(codepoint) {
        assert.equal(codepoint, "1f6b2");
        // return undefined
    }

    with_field(emoji, "get_emoji_name", fake_get_emoji_name, () => {
        markdown.apply_markdown(message);
    });

    assert.equal(message.content, "<p>\u{1f6b2}</p>");
});
