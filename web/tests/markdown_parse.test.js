"use strict";

const {strict: assert} = require("assert");

const url_template_lib = require("url-template");

const {zrequire} = require("./lib/namespace");
const {run_test} = require("./lib/test");

const markdown = zrequire("markdown");
const linkifiers = zrequire("linkifiers");

const my_id = 101;

const user_map = new Map();
user_map.set(my_id, "Me Myself");
user_map.set(105, "greg");

function get_actual_name_from_user_id(user_id) {
    return user_map.get(user_id);
}

function get_user_id_from_name(name) {
    for (const [user_id, _name] of user_map.entries()) {
        if (name === _name) {
            return user_id;
        }
    }

    /* istanbul ignore next */
    throw new Error(`unexpected name ${name}`);
}

function is_valid_full_name_and_user_id(name, user_id) {
    return user_map.has(user_id) && user_map.get(user_id) === name;
}

function my_user_id() {
    return my_id;
}

function is_valid_user_id(user_id) {
    return user_map.has(user_id);
}

const staff_group = {
    id: 201,
    name: "Staff",
};

const user_group_map = new Map();
user_group_map.set(staff_group.name, staff_group);

function get_user_group_from_name(name) {
    return user_group_map.get(name);
}

function is_member_of_user_group(user_id, user_group_id) {
    assert.equal(user_group_id, staff_group.id);
    assert.equal(user_id, my_id);
    return true;
}

const social = {
    stream_id: 301,
    name: "social",
};

const sub_map = new Map();
sub_map.set(social.name, social);

function get_stream_by_name(name) {
    return sub_map.get(name);
}

function stream_hash(stream_id) {
    return `stream-${stream_id}`;
}

function stream_topic_hash(stream_id, topic) {
    return `stream-${stream_id}-topic-${topic}`;
}

function get_emoticon_translations() {
    return [
        {regex: /(:\))/g, replacement_text: ":smile:"},
        {regex: /(<3)/g, replacement_text: ":heart:"},
    ];
}

const emoji_map = new Map();
emoji_map.set("smile", "1f642");
emoji_map.set("alien", "1f47d");

function get_emoji_codepoint(emoji_name) {
    return emoji_map.get(emoji_name);
}

function get_emoji_name(codepoint) {
    for (const [emoji_name, _codepoint] of emoji_map.entries()) {
        if (codepoint === _codepoint) {
            return emoji_name;
        }
    }

    /* istanbul ignore next */
    throw new Error(`unexpected codepoint ${codepoint}`);
}

const realm_emoji_map = new Map();
realm_emoji_map.set("heart", "/images/emoji/heart.bmp");

function get_realm_emoji_url(emoji_name) {
    return realm_emoji_map.get(emoji_name);
}

const regex = /#foo(\d+)(?!\w)/g;
const linkifier_map = new Map();
linkifier_map.set(regex, {
    url_template: url_template_lib.parse("http://foo.com/{id}"),
    group_number_to_name: {1: "id"},
});

function get_linkifier_map() {
    return linkifier_map;
}

const helper_config = {
    // user stuff
    get_actual_name_from_user_id,
    get_user_id_from_name,
    is_valid_full_name_and_user_id,
    is_valid_user_id,
    my_user_id,

    // user groups
    get_user_group_from_name,
    is_member_of_user_group,

    // stream hashes
    get_stream_by_name,
    stream_hash,
    stream_topic_hash,

    // settings
    should_translate_emoticons: () => true,

    // emojis
    get_emoji_codepoint,
    get_emoji_name,
    get_emoticon_translations,
    get_realm_emoji_url,

    // linkifiers
    get_linkifier_map,
};

function assert_parse(raw_content, expected_content) {
    const {content} = markdown.parse({raw_content, helper_config});
    assert.equal(content, expected_content);
}

run_test("basics", () => {
    assert_parse("boring", "<p>boring</p>");
    assert_parse("**bold**", "<p><strong>bold</strong></p>");
});

run_test("user mentions", () => {
    assert_parse("@**greg**", '<p><span class="user-mention" data-user-id="105">@greg</span></p>');

    assert_parse("@**|105**", '<p><span class="user-mention" data-user-id="105">@greg</span></p>');

    assert_parse(
        "@**greg|105**",
        '<p><span class="user-mention" data-user-id="105">@greg</span></p>',
    );

    assert_parse(
        "@**Me Myself|101**",
        '<p><span class="user-mention" data-user-id="101">@Me Myself</span></p>',
    );
});

run_test("user group mentions", () => {
    assert_parse(
        "@*Staff*",
        '<p><span class="user-group-mention" data-user-group-id="201">@Staff</span></p>',
    );
});

run_test("stream links", () => {
    assert_parse(
        "#**social**",
        '<p><a class="stream" data-stream-id="301" href="/stream-301">#social</a></p>',
    );

    assert_parse(
        "#**social>lunch**",
        '<p><a class="stream-topic" data-stream-id="301" href="/stream-301-topic-lunch">#social &gt; lunch</a></p>',
    );
});

run_test("emojis", () => {
    assert_parse(
        "yup :)",
        '<p>yup <span aria-label="smile" class="emoji emoji-1f642" role="img" title="smile">:smile:</span></p>',
    );
    assert_parse(
        "I <3 JavaScript",
        '<p>I <img alt=":heart:" class="emoji" src="/images/emoji/heart.bmp" title="heart"> JavaScript</p>',
    );
    assert_parse(
        "Mars Attacks! \uD83D\uDC7D",
        '<p>Mars Attacks! <span aria-label="alien" class="emoji emoji-1f47d" role="img" title="alien">:alien:</span></p>',
    );
});

run_test("linkifiers", () => {
    assert_parse(
        "see #foo12345 for details",
        '<p>see <a href="http://foo.com/12345" title="http://foo.com/12345">#foo12345</a> for details</p>',
    );
});

function assert_topic_links(topic, expected_links) {
    const topic_links = markdown.get_topic_links({
        topic,
        get_linkifier_map: linkifiers.get_linkifier_map,
    });
    assert.deepEqual(topic_links, expected_links);
}

run_test("topic links", () => {
    linkifiers.initialize([{pattern: "#foo(?P<id>\\d+)", url_template: "http://foo.com/{id}"}]);
    assert_topic_links("progress on #foo101 and #foo102", [
        {
            text: "#foo101",
            url: "http://foo.com/101",
        },
        {
            text: "#foo102",
            url: "http://foo.com/102",
        },
    ]);
});

run_test("topic links repeated", () => {
    // Links generated from repeated patterns should preserve the order.
    const topic =
        "#foo101 https://google.com #foo102 #foo103 https://google.com #foo101 #foo102 #foo103";
    linkifiers.initialize([{pattern: "#foo(?P<id>\\d+)", url_template: "http://foo.com/{id}"}]);
    assert_topic_links(topic, [
        {
            text: "#foo101",
            url: "http://foo.com/101",
        },
        {
            text: "https://google.com",
            url: "https://google.com",
        },
        {
            text: "#foo102",
            url: "http://foo.com/102",
        },
        {
            text: "#foo103",
            url: "http://foo.com/103",
        },
        {
            text: "https://google.com",
            url: "https://google.com",
        },
        {
            text: "#foo101",
            url: "http://foo.com/101",
        },
        {
            text: "#foo102",
            url: "http://foo.com/102",
        },
        {
            text: "#foo103",
            url: "http://foo.com/103",
        },
    ]);
});

run_test("topic links overlapping", () => {
    linkifiers.initialize([
        {pattern: "[a-z]+(?P<id>1\\d+) #[a-z]+", url_template: "http://a.com/{id}"},
        {pattern: "[a-z]+(?P<id>1\\d+)", url_template: "http://b.com/{id}"},
        {pattern: ".+#(?P<id>[a-z]+)", url_template: "http://wildcard.com/{id}"},
        {pattern: "#(?P<id>[a-z]+)", url_template: "http://c.com/{id}"},
    ]);
    // b.com's pattern should be matched while it overlaps with c.com's.
    assert_topic_links("#foo100", [
        {
            text: "foo100",
            url: "http://b.com/100",
        },
    ]);
    // a.com's pattern should be matched while it overlaps with b.com's, wildcard.com's and c.com's.
    assert_topic_links("#asd123 #asd", [
        {
            text: "asd123 #asd",
            url: "http://a.com/123",
        },
    ]);
    // a.com's pattern do not match, wildcard.com's and b.com's patterns should match
    // and the links are ordered by the matched index.
    assert_topic_links("/#asd #foo100", [
        {
            text: "/#asd",
            url: "http://wildcard.com/asd",
        },
        {
            text: "foo100",
            url: "http://b.com/100",
        },
    ]);
    assert_topic_links("foo.anything/#asd", [
        {
            text: "foo.anything/#asd",
            url: "http://wildcard.com/asd",
        },
    ]);

    // While the raw URL "http://foo.com/foo100" appears before b.com's match "foo100",
    // we prioritize the linkifier match first.
    assert_topic_links("http://foo.com/foo100", [
        {
            text: "foo100",
            url: "http://b.com/100",
        },
    ]);

    // Here the raw URL "https://foo.com/#asd" appears after wildcard.com's match "something https://foo.com/#asd".
    // The latter is prioritized and the raw URL does not get included.
    assert_topic_links("something https://foo.com/#asd", [
        {
            text: "something https://foo.com/#asd",
            url: "http://wildcard.com/asd",
        },
    ]);
});

run_test("topic links ordering by priority", () => {
    // The same test case is also implemented in zerver/tests/test_markdown.py
    linkifiers.initialize([
        {pattern: "http", url_template: "http://example.com/"},
        {pattern: "b#(?P<id>[a-z]+)", url_template: "http://example.com/b/{id}"},
        {
            pattern: "a#(?P<aid>[a-z]+) b#(?P<bid>[a-z]+)",
            url_template: "http://example.com/a/{aid}/b/%(bid)",
        },
        {pattern: "a#(?P<id>[a-z]+)", url_template: "http://example.com/a/{id}"},
    ]);

    // There should be 5 link matches in the topic, if ordered from the most priortized to the least:
    // 1. "http" (linkifier)
    // 2. "b#bar" (linkifier)
    // 3. "a#asd b#bar" (linkifier)
    // 4. "a#asd" (linkifier)
    // 5. "http://foo.com" (raw URL)
    // When there are overlapping matches, the one that appears earlier in the list should
    // have a topic link generated.
    // For this test case, while "a#asd" and "a#asd b#bar" both match and they overlap,
    // there is a match "b#bar" with a higher priority, preventing "a#asd b#bar" from being matched.
    assert_topic_links("http://foo.com a#asd b#bar", [
        {
            text: "http",
            url: "http://example.com/",
        },
        {
            text: "a#asd",
            url: "http://example.com/a/asd",
        },
        {
            text: "b#bar",
            url: "http://example.com/b/bar",
        },
    ]);
});
