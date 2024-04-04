"use strict";

const {strict: assert} = require("assert");

const markdown_test_cases = require("../../zerver/tests/fixtures/markdown_test_cases");

const markdown_assert = require("./lib/markdown_assert");
const {mock_esm, set_global, zrequire} = require("./lib/namespace");
const {run_test} = require("./lib/test");
const {page_params, user_settings} = require("./lib/zpage_params");

const example_realm_linkifiers = [
    {
        pattern: "#(?P<id>[0-9]{2,8})",
        url_template: "https://trac.example.com/ticket/{id}",
        id: 1,
    },
    {
        pattern: "ZBUG_(?P<id>[0-9]{2,8})",
        url_template: "https://trac2.zulip.net/ticket/{id}",
        id: 2,
    },
    {
        pattern: "ZGROUP_(?P<id>[0-9]{2,8}):(?P<zone>[0-9]{1,8})",
        url_template: "https://zone_{zone}.zulip.net/ticket/{id}",
        id: 3,
    },
    {
        // For example, this linkifier matches:
        // FOO_abcde;e;zulip;luxembourg;foo;23;testing
        // which expands to:
        // https://zone_e.zulip.net/ticket/luxembourg/abcde?name=foo&chapter=23#testi
        // This exercises different URL template supported syntax.
        pattern:
            "FOO_(?P<id>[a-f]{5});(?P<zone>[a-f]);(?P<domain>[a-z]+);(?P<location>[a-z]+);(?P<name>[a-z]{2,8});(?P<chapter>[0-9]{2,3});(?P<fragment>[a-z]{2,8})",
        url_template:
            "https://zone_{zone}{.domain}.net/ticket{/location}{/id}{?name,chapter}{#fragment:5}",
        id: 4,
    },
];
user_settings.translate_emoticons = false;

set_global("document", {compatMode: "CSS1Compat"});

mock_esm("../src/settings_data", {
    user_can_access_all_other_users: () => false,
});

const emoji = zrequire("emoji");
const emoji_codes = zrequire("../../static/generated/emoji/emoji_codes.json");
const linkifiers = zrequire("linkifiers");
const fenced_code = zrequire("../shared/src/fenced_code");
const markdown_config = zrequire("markdown_config");
const markdown = zrequire("markdown");
const people = zrequire("people");
const pygments_data = zrequire("pygments_data");
const stream_data = zrequire("stream_data");
const user_groups = zrequire("user_groups");

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

emoji.initialize(emoji_params);
fenced_code.initialize(pygments_data);

const cordelia = {
    full_name: "Cordelia, Lear's daughter",
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

people.add_inaccessible_user(108);

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
    description: "HTML syntax to check for Markdown edge cases.",
    members: [],
};

const amp_group = {
    name: "& & &amp;",
    id: 4,
    description: "Check ampersand escaping",
    members: [],
};

user_groups.add(hamletcharacters);
user_groups.add(backend);
user_groups.add(edgecase_group);
user_groups.add(amp_group);

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

markdown.initialize(markdown_config.get_helpers());
linkifiers.initialize(example_realm_linkifiers);

function test(label, f) {
    run_test(label, (helpers) => {
        page_params.realm_users = [];
        linkifiers.update_linkifier_rules(example_realm_linkifiers);
        f(helpers);
    });
}

test("markdown_detection", () => {
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
        "Twitter URL https://twitter.com/jacobian/status/407886996565016579",
        "https://twitter.com/jacobian/status/407886996565016579",
        "then https://twitter.com/jacobian/status/407886996565016579",
        "Twitter URL http://twitter.com/jacobian/status/407886996565016579",
        "YouTube URL https://www.youtube.com/watch?v=HHZ8iqswiCw&feature=youtu.be&a",
    ];

    for (const content of no_markup) {
        assert.equal(markdown.contains_backend_only_syntax(content), false);
    }

    for (const content of markup) {
        assert.equal(markdown.contains_backend_only_syntax(content), true);
    }
});

test("marked_shared", () => {
    const tests = markdown_test_cases.regular_tests;

    for (const test of tests) {
        // Ignore tests if specified
        /* istanbul ignore if */
        if (test.ignore === true) {
            continue;
        }

        let message = {raw_content: test.input};
        user_settings.translate_emoticons = test.translate_emoticons || false;
        message = {
            ...message,
            ...markdown.render(message.raw_content),
        };
        const output = message.content;
        const error_message = `Failure in test: ${test.name}`;
        if (test.marked_expected_output) {
            markdown_assert.notEqual(test.expected_output, output, error_message);
            markdown_assert.equal(test.marked_expected_output, output, error_message);
        } else if (test.backend_only_rendering) {
            assert.equal(markdown.contains_backend_only_syntax(test.input), true);
        } else {
            markdown_assert.equal(test.expected_output, output, error_message);
        }
    }
});

test("message_flags", () => {
    let message = {raw_content: "@**Leo**"};
    message = {
        ...message,
        ...markdown.render(message.raw_content),
    };
    assert.ok(!message.flags.includes("mentioned"));

    message = {raw_content: "@**Cordelia, Lear's daughter**"};
    message = {
        ...message,
        ...markdown.render(message.raw_content),
    };
    assert.ok(message.flags.includes("mentioned"));

    message = {raw_content: "@**all**"};
    message = {
        ...message,
        ...markdown.render(message.raw_content),
    };
    assert.ok(message.flags.includes("stream_wildcard_mentioned"));
    assert.ok(!message.flags.includes("topic_wildcard_mentioned"));

    message = {raw_content: "@**topic**"};
    message = {
        ...message,
        ...markdown.render(message.raw_content),
    };
    assert.ok(!message.flags.includes("stream_wildcard_mentioned"));
    assert.ok(message.flags.includes("topic_wildcard_mentioned"));
});

test("marked", () => {
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
                '<div class="codehilite"><pre><span></span><code>fenced code\n</code></pre></div>\n<p>and then after</p>',
        },
        {
            input: "\n```\n    fenced code trailing whitespace            \n```\n\nand then after\n",
            expected:
                '<div class="codehilite"><pre><span></span><code>    fenced code trailing whitespace\n</code></pre></div>\n<p>and then after</p>',
        },
        {
            input: "* a\n* list \n* here",
            expected: "<ul>\n<li>a</li>\n<li>list </li>\n<li>here</li>\n</ul>",
        },
        {
            input: "\n```c#\nfenced code special\n```\n\nand then after\n",
            expected:
                '<div class="codehilite" data-code-language="C#"><pre><span></span><code>fenced code special\n</code></pre></div>\n<p>and then after</p>',
        },
        {
            input: "\n```vb.net\nfenced code dot\n```\n\nand then after\n",
            expected:
                '<div class="codehilite" data-code-language="VB.net"><pre><span></span><code>fenced code dot\n</code></pre></div>\n<p>and then after</p>',
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
            input: "This is a @**CordeLIA, Lear's daughter** mention",
            expected:
                '<p>This is a <span class="user-mention" data-user-id="101">@Cordelia, Lear&#39;s daughter</span> mention</p>',
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
                '<p>This is a <a class="stream-topic" data-stream-id="1" href="/#narrow/stream/1-Denmark/topic/some.20topic">#Denmark &gt; some topic</a> stream_topic link</p>',
        },
        {
            input: "This has two links: #**Denmark>some topic** and #**social>other topic**.",
            expected:
                '<p>This has two links: <a class="stream-topic" data-stream-id="1" href="/#narrow/stream/1-Denmark/topic/some.20topic">#Denmark &gt; some topic</a> and <a class="stream-topic" data-stream-id="2" href="/#narrow/stream/2-social/topic/other.20topic">#social &gt; other topic</a>.</p>',
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
            input: "\uD83D\uDCA9",
            expected:
                '<p><span aria-label="poop" class="emoji emoji-1f4a9" role="img" title="poop">:poop:</span></p>',
        },
        {
            input: "Silent mention: @_**Cordelia, Lear's daughter**",
            expected:
                '<p>Silent mention: <span class="user-mention silent" data-user-id="101">Cordelia, Lear&#39;s daughter</span></p>',
        },
        {
            input: "> Mention in quote: @**Cordelia, Lear's daughter**\n\nMention outside quote: @**Cordelia, Lear's daughter**",
            expected:
                '<blockquote>\n<p>Mention in quote: <span class="user-mention silent" data-user-id="101">Cordelia, Lear&#39;s daughter</span></p>\n</blockquote>\n<p>Mention outside quote: <span class="user-mention" data-user-id="101">@Cordelia, Lear&#39;s daughter</span></p>',
        },
        {
            input: "Stream Wildcard mention: @**all**\nStream Wildcard silent mention: @_**all**",
            expected:
                '<p>Stream Wildcard mention: <span class="user-mention" data-user-id="*">@all</span><br>\nStream Wildcard silent mention: <span class="user-mention silent" data-user-id="*">all</span></p>',
        },
        {
            input: "> Stream Wildcard mention in quote: @**all**\n\n> Another stream wildcard mention in quote: @_**all**",
            expected:
                '<blockquote>\n<p>Stream Wildcard mention in quote: <span class="user-mention silent" data-user-id="*">all</span></p>\n</blockquote>\n<blockquote>\n<p>Another stream wildcard mention in quote: <span class="user-mention silent" data-user-id="*">all</span></p>\n</blockquote>',
        },
        {
            input: "```quote\nStream Wildcard mention in quote: @**all**\n```\n\n```quote\nAnother stream wildcard mention in quote: @_**all**\n```",
            expected:
                '<blockquote>\n<p>Stream Wildcard mention in quote: <span class="user-mention silent" data-user-id="*">all</span></p>\n</blockquote>\n<blockquote>\n<p>Another stream wildcard mention in quote: <span class="user-mention silent" data-user-id="*">all</span></p>\n</blockquote>',
        },
        {
            input: "Topic Wildcard mention: @**topic**\nTopic Wildcard silent mention: @_**topic**",
            expected:
                '<p>Topic Wildcard mention: <span class="topic-mention">@topic</span><br>\nTopic Wildcard silent mention: <span class="topic-mention silent">topic</span></p>',
        },
        {
            input: "> Topic Wildcard mention in quote: @**topic**\n\n> Another topic wildcard mention in quote: @_**topic**",
            expected:
                '<blockquote>\n<p>Topic Wildcard mention in quote: <span class="topic-mention silent">topic</span></p>\n</blockquote>\n<blockquote>\n<p>Another topic wildcard mention in quote: <span class="topic-mention silent">topic</span></p>\n</blockquote>',
        },
        {
            input: "```quote\nTopic Wildcard mention in quote: @**topic**\n```\n\n```quote\nAnother topic wildcard mention in quote: @_**topic**\n```",
            expected:
                '<blockquote>\n<p>Topic Wildcard mention in quote: <span class="topic-mention silent">topic</span></p>\n</blockquote>\n<blockquote>\n<p>Another topic wildcard mention in quote: <span class="topic-mention silent">topic</span></p>\n</blockquote>',
        },
        {
            input: "User group mention: @*backend*\nUser group silent mention: @_*hamletcharacters*",
            expected:
                '<p>User group mention: <span class="user-group-mention" data-user-group-id="2">@Backend</span><br>\nUser group silent mention: <span class="user-group-mention silent" data-user-group-id="1">hamletcharacters</span></p>',
        },
        {
            input: "> User group mention in quote: @*backend*\n\n> Another user group mention in quote: @*hamletcharacters*",
            expected:
                '<blockquote>\n<p>User group mention in quote: <span class="user-group-mention silent" data-user-group-id="2">Backend</span></p>\n</blockquote>\n<blockquote>\n<p>Another user group mention in quote: <span class="user-group-mention silent" data-user-group-id="1">hamletcharacters</span></p>\n</blockquote>',
        },
        {
            input: "```quote\nUser group mention in quote: @*backend*\n```\n\n```quote\nAnother user group mention in quote: @*hamletcharacters*\n```",
            expected:
                '<blockquote>\n<p>User group mention in quote: <span class="user-group-mention silent" data-user-group-id="2">Backend</span></p>\n</blockquote>\n<blockquote>\n<p>Another user group mention in quote: <span class="user-group-mention silent" data-user-group-id="1">hamletcharacters</span></p>\n</blockquote>',
        },
        // Test only those linkifiers which don't return True for
        // `contains_backend_only_syntax()`. Those which return True
        // are tested separately.
        {
            input: "This is a linkifier #1234 with text after it",
            expected:
                '<p>This is a linkifier <a href="https://trac.example.com/ticket/1234" title="https://trac.example.com/ticket/1234">#1234</a> with text after it</p>',
        },
        {
            input: "This is a complicated linkifier FOO_abcde;e;zulip;luxembourg;foo;23;testing with text after it",
            expected:
                '<p>This is a complicated linkifier <a href="https://zone_e.zulip.net/ticket/luxembourg/abcde?name=foo&amp;chapter=23#testi" title="https://zone_e.zulip.net/ticket/luxembourg/abcde?name=foo&amp;chapter=23#testi">FOO_abcde;e;zulip;luxembourg;foo;23;testing</a> with text after it</p>',
        },
        {input: "#1234is not a linkifier.", expected: "<p>#1234is not a linkifier.</p>"},
        {
            input: "A pattern written as #1234is not a linkifier.",
            expected: "<p>A pattern written as #1234is not a linkifier.</p>",
        },
        {
            input: "This is a linkifier with ZGROUP_123:45 groups",
            expected:
                '<p>This is a linkifier with <a href="https://zone_45.zulip.net/ticket/123" title="https://zone_45.zulip.net/ticket/123">ZGROUP_123:45</a> groups</p>',
        },
        {input: "Test *italic*", expected: "<p>Test <em>italic</em></p>"},
        {
            input: "T\n#**Denmark**",
            expected:
                '<p>T<br>\n<a class="stream" data-stream-id="1" href="/#narrow/stream/1-Denmark">#Denmark</a></p>',
        },
        {
            input: "T\n@**Cordelia, Lear's daughter**",
            expected:
                '<p>T<br>\n<span class="user-mention" data-user-id="101">@Cordelia, Lear&#39;s daughter</span></p>',
        },
        {
            input: "@**Mark Twin|104** and @**Mark Twin|105** are out to confuse you.",
            expected:
                '<p><span class="user-mention" data-user-id="104">@Mark Twin</span> and <span class="user-mention" data-user-id="105">@Mark Twin</span> are out to confuse you.</p>',
        },
        {input: "@**Invalid User|1234**", expected: "<p>@**Invalid User|1234**</p>"},
        {
            input: "@**Cordelia, Lear's daughter|103** has a wrong user_id.",
            expected: "<p>@**Cordelia, Lear&#39;s daughter|103** has a wrong user_id.</p>",
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
        {
            input: "@**|106** valid user id.",
            expected:
                '<p><span class="user-mention" data-user-id="106">@Brother of Bobby|123</span> valid user id.</p>',
        },
        {
            input: "@**|123|106** comes under user|id case.",
            expected: "<p>@**|123|106** comes under user|id case.</p>",
        },
        {
            input: "@**|108** mention inaccessible user using ID.",
            expected: "<p>@**|108** mention inaccessible user using ID.</p>",
        },
        {
            input: "@**Unknown user|108** mention inaccessible user using name and ID.",
            expected: "<p>@**Unknown user|108** mention inaccessible user using name and ID.</p>",
        },
        {input: "@**|1234** invalid id.", expected: "<p>@**|1234** invalid id.</p>"},
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
            input: "This is a linkifier `hello` with text after it",
            expected: "<p>This is a linkifier <code>hello</code> with text after it</p>",
        },
        // Test the emoticon conversion
        {input: ":)", expected: "<p>:)</p>"},
        {
            input: ":)",
            expected:
                '<p><span aria-label="smile" class="emoji emoji-1f642" role="img" title="smile">:smile:</span></p>',
            translate_emoticons: true,
        },
        // Test HTML escaping in custom Zulip rules
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
                '<p><a class="stream-topic" data-stream-id="4" href="/#narrow/stream/4-Bobby-.3Ch1/topic/Tables.3C.2Fh1.3E">#Bobby &lt;h1 &gt; Tables&lt;/h1&gt;</a></p>',
        },
        {
            input: "#**& &amp; &amp;amp;**",
            expected:
                '<p><a class="stream" data-stream-id="5" href="/#narrow/stream/5-.26-.26-.26amp.3B">#&amp; &amp; &amp;amp;</a></p>',
        },
        {
            input: "#**& &amp; &amp;amp;>& &amp; &amp;amp;**",
            expected:
                '<p><a class="stream-topic" data-stream-id="5" href="/#narrow/stream/5-.26-.26-.26amp.3B/topic/.26.20.26.20.26amp.3B">#&amp; &amp; &amp;amp; &gt; &amp; &amp; &amp;amp;</a></p>',
        },
    ];

    for (const test_case of test_cases) {
        // Disable emoji conversion by default.
        user_settings.translate_emoticons = test_case.translate_emoticons || false;

        const input = test_case.input;
        const expected = test_case.expected;

        const message = markdown.render(input);
        const output = message.content;
        assert.equal(output, expected);
    }
});

test("topic_links", () => {
    let message = {type: "stream", topic: "No links here"};
    message.topic_links = markdown.get_topic_links(message.topic);
    assert.equal(message.topic_links.length, 0);

    message = {type: "stream", topic: "One #123 link here"};
    message.topic_links = markdown.get_topic_links(message.topic);
    assert.equal(message.topic_links.length, 1);
    assert.deepEqual(message.topic_links[0], {
        url: "https://trac.example.com/ticket/123",
        text: "#123",
    });

    message = {type: "stream", topic: "Two #123 #456 link here"};
    message.topic_links = markdown.get_topic_links(message.topic);
    assert.equal(message.topic_links.length, 2);
    assert.deepEqual(message.topic_links[0], {
        url: "https://trac.example.com/ticket/123",
        text: "#123",
    });
    assert.deepEqual(message.topic_links[1], {
        url: "https://trac.example.com/ticket/456",
        text: "#456",
    });

    message = {type: "stream", topic: "New ZBUG_123 link here"};
    message.topic_links = markdown.get_topic_links(message.topic);
    assert.equal(message.topic_links.length, 1);
    assert.deepEqual(message.topic_links[0], {
        url: "https://trac2.zulip.net/ticket/123",
        text: "ZBUG_123",
    });

    message = {type: "stream", topic: "New ZBUG_123 with #456 link here"};
    message.topic_links = markdown.get_topic_links(message.topic);
    assert.equal(message.topic_links.length, 2);
    assert.deepEqual(message.topic_links[0], {
        url: "https://trac2.zulip.net/ticket/123",
        text: "ZBUG_123",
    });
    assert.deepEqual(message.topic_links[1], {
        url: "https://trac.example.com/ticket/456",
        text: "#456",
    });

    message = {type: "stream", topic: "One ZGROUP_123:45 link here"};
    message.topic_links = markdown.get_topic_links(message.topic);
    assert.equal(message.topic_links.length, 1);
    assert.deepEqual(message.topic_links[0], {
        url: "https://zone_45.zulip.net/ticket/123",
        text: "ZGROUP_123:45",
    });

    message = {type: "stream", topic: "Hello https://google.com"};
    message.topic_links = markdown.get_topic_links(message.topic);
    assert.equal(message.topic_links.length, 1);
    assert.deepEqual(message.topic_links[0], {
        url: "https://google.com",
        text: "https://google.com",
    });

    message = {type: "stream", topic: "#456 https://google.com https://github.com"};
    message.topic_links = markdown.get_topic_links(message.topic);
    assert.equal(message.topic_links.length, 3);
    assert.deepEqual(message.topic_links[0], {
        url: "https://trac.example.com/ticket/456",
        text: "#456",
    });
    assert.deepEqual(message.topic_links[1], {
        url: "https://google.com",
        text: "https://google.com",
    });
    assert.deepEqual(message.topic_links[2], {
        url: "https://github.com",
        text: "https://github.com",
    });

    message = {type: "not-stream"};
    message.topic_links = markdown.get_topic_links(message.topic);
    assert.equal(message.topic_links.length, 0);

    message = {type: "stream", topic: "FOO_abcde;e;zulip;luxembourg;foo;23;testing"};
    message.topic_links = markdown.get_topic_links(message.topic);
    assert.equal(message.topic_links.length, 1);
    assert.deepEqual(message.topic_links[0], {
        url: "https://zone_e.zulip.net/ticket/luxembourg/abcde?name=foo&chapter=23#testi",
        text: "FOO_abcde;e;zulip;luxembourg;foo;23;testing",
    });
});

test("message_flags", () => {
    let input = "/me is testing this";
    let message = {topic: "No links here", raw_content: input};
    message = {
        ...message,
        ...markdown.render(message.raw_content),
    };

    assert.equal(message.is_me_message, true);
    assert.ok(!message.unread);

    input = "/me is testing\nthis";
    message = {topic: "No links here", raw_content: input};
    message = {
        ...message,
        ...markdown.render(message.raw_content),
    };

    assert.equal(message.is_me_message, true);

    input = "testing this @**all** @**Cordelia, Lear's daughter**";
    message = {topic: "No links here", raw_content: input};
    message = {
        ...message,
        ...markdown.render(message.raw_content),
    };
    assert.equal(message.is_me_message, false);
    assert.equal(message.flags.includes("mentioned"), true);
    assert.equal(message.flags.includes("stream_wildcard_mentioned"), true);
    assert.equal(message.flags.includes("topic_wildcard_mentioned"), false);

    input = "test @**everyone**";
    message = {topic: "No links here", raw_content: input};
    message = {
        ...message,
        ...markdown.render(message.raw_content),
    };
    assert.equal(message.is_me_message, false);
    assert.equal(message.flags.includes("stream_wildcard_mentioned"), true);
    assert.equal(message.flags.includes("topic_wildcard_mentioned"), false);
    assert.equal(message.flags.includes("mentioned"), false);

    input = "test @**stream**";
    message = {topic: "No links here", raw_content: input};
    message = {
        ...message,
        ...markdown.render(message.raw_content),
    };
    assert.equal(message.is_me_message, false);
    assert.equal(message.flags.includes("stream_wildcard_mentioned"), true);
    assert.equal(message.flags.includes("topic_wildcard_mentioned"), false);
    assert.equal(message.flags.includes("mentioned"), false);

    input = "test @**channel**";
    message = {topic: "No links here", raw_content: input};
    message = {
        ...message,
        ...markdown.render(message.raw_content),
    };
    assert.equal(message.is_me_message, false);
    assert.equal(message.flags.includes("stream_wildcard_mentioned"), true);
    assert.equal(message.flags.includes("topic_wildcard_mentioned"), false);
    assert.equal(message.flags.includes("mentioned"), false);

    input = "test @**topic**";
    message = {topic: "No links here", raw_content: input};
    message = {
        ...message,
        ...markdown.render(message.raw_content),
    };
    assert.equal(message.is_me_message, false);
    assert.equal(message.flags.includes("stream_wildcard_mentioned"), false);
    assert.equal(message.flags.includes("topic_wildcard_mentioned"), true);
    assert.equal(message.flags.includes("mentioned"), false);

    input = "test @all";
    message = {topic: "No links here", raw_content: input};
    message = {
        ...message,
        ...markdown.render(message.raw_content),
    };
    assert.equal(message.flags.includes("stream_wildcard_mentioned"), false);
    assert.equal(message.flags.includes("topic_wildcard_mentioned"), false);
    assert.equal(message.flags.includes("mentioned"), false);

    input = "test @everyone";
    message = {topic: "No links here", raw_content: input};
    message = {
        ...message,
        ...markdown.render(message.raw_content),
    };
    assert.equal(message.flags.includes("stream_wildcard_mentioned"), false);
    assert.equal(message.flags.includes("topic_wildcard_mentioned"), false);
    assert.equal(message.flags.includes("mentioned"), false);

    input = "test @topic";
    message = {topic: "No links here", raw_content: input};
    message = {
        ...message,
        ...markdown.render(message.raw_content),
    };
    assert.equal(message.flags.includes("stream_wildcard_mentioned"), false);
    assert.equal(message.flags.includes("topic_wildcard_mentioned"), false);
    assert.equal(message.flags.includes("mentioned"), false);

    input = "test @any";
    message = {topic: "No links here", raw_content: input};
    message = {
        ...message,
        ...markdown.render(message.raw_content),
    };
    assert.equal(message.flags.includes("stream_wildcard_mentioned"), false);
    assert.equal(message.flags.includes("topic_wildcard_mentioned"), false);
    assert.equal(message.flags.includes("mentioned"), false);

    input = "test @alleycat.com";
    message = {topic: "No links here", raw_content: input};
    message = {
        ...message,
        ...markdown.render(message.raw_content),
    };
    assert.equal(message.flags.includes("stream_wildcard_mentioned"), false);
    assert.equal(message.flags.includes("topic_wildcard_mentioned"), false);
    assert.equal(message.flags.includes("mentioned"), false);

    input = "test @*hamletcharacters*";
    message = {topic: "No links here", raw_content: input};
    message = {
        ...message,
        ...markdown.render(message.raw_content),
    };
    assert.equal(message.flags.includes("stream_wildcard_mentioned"), false);
    assert.equal(message.flags.includes("topic_wildcard_mentioned"), false);
    assert.equal(message.flags.includes("mentioned"), true);

    input = "test @*backend*";
    message = {topic: "No links here", raw_content: input};
    message = {
        ...message,
        ...markdown.render(message.raw_content),
    };
    assert.equal(message.flags.includes("stream_wildcard_mentioned"), false);
    assert.equal(message.flags.includes("topic_wildcard_mentioned"), false);
    assert.equal(message.flags.includes("mentioned"), false);

    input = "test @**invalid_user**";
    message = {topic: "No links here", raw_content: input};
    message = {
        ...message,
        ...markdown.render(message.raw_content),
    };
    assert.equal(message.flags.includes("stream_wildcard_mentioned"), false);
    assert.equal(message.flags.includes("topic_wildcard_mentioned"), false);
    assert.equal(message.flags.includes("mentioned"), false);

    input = "test @_**all**";
    message = {topic: "No links here", raw_content: input};
    message = {
        ...message,
        ...markdown.render(message.raw_content),
    };
    assert.equal(message.flags.includes("stream_wildcard_mentioned"), false);
    assert.equal(message.flags.includes("topic_wildcard_mentioned"), false);
    assert.equal(message.flags.includes("mentioned"), false);

    input = "> test @**all**";
    message = {topic: "No links here", raw_content: input};
    message = {
        ...message,
        ...markdown.render(message.raw_content),
    };
    assert.equal(message.flags.includes("stream_wildcard_mentioned"), false);
    assert.equal(message.flags.includes("topic_wildcard_mentioned"), false);
    assert.equal(message.flags.includes("mentioned"), false);

    input = "test @_**topic**";
    message = {topic: "No links here", raw_content: input};
    message = {
        ...message,
        ...markdown.render(message.raw_content),
    };
    assert.equal(message.flags.includes("stream_wildcard_mentioned"), false);
    assert.equal(message.flags.includes("topic_wildcard_mentioned"), false);
    assert.equal(message.flags.includes("mentioned"), false);

    input = "> test @**topic**";
    message = {topic: "No links here", raw_content: input};
    message = {
        ...message,
        ...markdown.render(message.raw_content),
    };
    assert.equal(message.flags.includes("stream_wildcard_mentioned"), false);
    assert.equal(message.flags.includes("topic_wildcard_mentioned"), false);
    assert.equal(message.flags.includes("mentioned"), false);

    input = "test @_*hamletcharacters*";
    message = {topic: "No links here", raw_content: input};
    message = {
        ...message,
        ...markdown.render(message.raw_content),
    };
    assert.equal(message.flags.includes("stream_wildcard_mentioned"), false);
    assert.equal(message.flags.includes("topic_wildcard_mentioned"), false);
    assert.equal(message.flags.includes("mentioned"), false);

    input = "> test @*hamletcharacters*";
    message = {topic: "No links here", raw_content: input};
    message = {
        ...message,
        ...markdown.render(message.raw_content),
    };
    assert.equal(message.flags.includes("stream_wildcard_mentioned"), false);
    assert.equal(message.flags.includes("topic_wildcard_mentioned"), false);
    assert.equal(message.flags.includes("mentioned"), false);
});

test("backend_only_linkifiers", () => {
    const backend_only_linkifiers = [
        "Here is the PR-#123.",
        "Function abc() was introduced in (PR)#123.",
    ];
    for (const content of backend_only_linkifiers) {
        assert.equal(markdown.contains_backend_only_syntax(content), true);
    }
});

test("translate_emoticons_to_names", () => {
    const get_emoticon_translations = emoji.get_emoticon_translations;

    function translate_emoticons_to_names(src) {
        return markdown.translate_emoticons_to_names({src, get_emoticon_translations});
    }

    // Simple test
    const test_text = "Testing :)";
    const expected = "Testing :smile:";
    const result = translate_emoticons_to_names(test_text);
    assert.equal(result, expected);

    // Extensive tests.
    // The following code loops over the test cases and each emoticon conversion
    // to generate multiple test cases.
    for (const [shortcut, full_name] of Object.entries(emoji_codes.emoticon_conversions)) {
        for (const {original, expected} of [
            {name: `only emoticon`, original: shortcut, expected: full_name},
            {name: `space at start`, original: ` ${shortcut}`, expected: ` ${full_name}`},
            {name: `space at end`, original: `${shortcut} `, expected: `${full_name} `},
            {name: `symbol at end`, original: `${shortcut}!`, expected: `${full_name}!`},
            {
                name: `symbol at start`,
                original: `Hello,${shortcut}`,
                expected: `Hello,${full_name}`,
            },
            {name: `after a word`, original: `Hello${shortcut}`, expected: `Hello${shortcut}`},
            {
                name: `between words`,
                original: `Hello${shortcut}World`,
                expected: `Hello${shortcut}World`,
            },
            {
                name: `end of sentence`,
                original: `End of sentence. ${shortcut}`,
                expected: `End of sentence. ${full_name}`,
            },
            {
                name: `between symbols`,
                original: `Hello.${shortcut}! World.`,
                expected: `Hello.${shortcut}! World.`,
            },
            {
                name: `before end of sentence`,
                original: `Hello ${shortcut}!`,
                expected: `Hello ${full_name}!`,
            },
        ]) {
            const result = translate_emoticons_to_names(original);
            assert.equal(result, expected);
        }
    }
});

test("parse_non_message", () => {
    assert.equal(markdown.parse_non_message("type `/day`"), "<p>type <code>/day</code></p>");
});

test("missing unicode emojis", ({override}) => {
    let message = {raw_content: "\u{1F6B2}"};

    message = {
        ...message,
        ...markdown.render(message.raw_content),
    };
    assert.equal(
        message.content,
        '<p><span aria-label="bike" class="emoji emoji-1f6b2" role="img" title="bike">:bike:</span></p>',
    );

    // Now simulate that we don't know this emoji name.
    override(emoji_codes.codepoint_to_name, "1f6b2", undefined);

    markdown.initialize(markdown_config.get_helpers());
    message = {
        ...message,
        ...markdown.render(message.raw_content),
    };
    assert.equal(message.content, "<p>\u{1F6B2}</p>");
});

test("katex_throws_unexpected_exceptions", ({override_rewire}) => {
    const message = {raw_content: "$$a$$"};
    override_rewire(markdown, "katex", {
        renderToString() {
            throw new Error("some-exception");
        },
    });
    assert.throws(() => markdown.render(message.raw_content), {
        name: "Error",
        message: "some-exception\nPlease report this to https://zulip.com/development-community/",
    });
});
