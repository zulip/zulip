/*global Dict */
zrequire('hash_util');
zrequire('katex', 'node_modules/katex/dist/katex.min.js');
zrequire('marked', 'third/marked/lib/marked');
zrequire('util');
zrequire('fenced_code');
zrequire('stream_data');
zrequire('people');
zrequire('user_groups');
zrequire('emoji_codes', 'generated/emoji/emoji_codes');
zrequire('emoji');
zrequire('message_store');
zrequire('markdown');

global.patch_builtin('window', {
    location: {
        origin: 'http://zulip.zulipdev.com',
    },
});

set_global('page_params', {
    realm_users: [],
    realm_emoji: {
        1: {id: 1,
            name: 'burrito',
            source_url: '/static/generated/emoji/images/emoji/burrito.png',
            deactivated: false,
        },
    },
    realm_filters: [
        [
            "#(?P<id>[0-9]{2,8})",
            "https://trac.zulip.net/ticket/%(id)s",
        ],
        [
            "ZBUG_(?P<id>[0-9]{2,8})",
            "https://trac2.zulip.net/ticket/%(id)s",
        ],
        [
            "ZGROUP_(?P<id>[0-9]{2,8}):(?P<zone>[0-9]{1,8})",
            "https://zone_%(zone)s.zulip.net/ticket/%(id)s",
        ],
    ],
    translate_emoticons: false,
});

set_global('blueslip', global.make_zblueslip());

set_global('Image', function () {
    return {};
});
emoji.initialize();

var doc = "";
set_global('document', doc);

set_global('$', global.make_zjquery());

set_global('feature_flags', {local_echo: true});

var people = global.people;

var cordelia = {
    full_name: 'Cordelia Lear',
    user_id: 101,
    email: 'cordelia@zulip.com',
};
people.add(cordelia);

people.add({
    full_name: 'Leo',
    user_id: 102,
    email: 'leo@zulip.com',
});

people.add({
    full_name: 'Bobby <h1>Tables</h1>',
    user_id: 103,
    email: 'bobby@zulip.com',
});

people.add({
    full_name: 'Mark Twin',
    user_id: 104,
    email: 'twin1@zulip.com',
});

people.add({
    full_name: 'Mark Twin',
    user_id: 105,
    email: 'twin2@zulip.com',
});

people.add({
    full_name: 'Brother of Bobby|123',
    user_id: 106,
    email: 'bobby2@zulip.com',
});

people.initialize_current_user(cordelia.user_id);

var hamletcharacters = {
    name: "hamletcharacters",
    id: 1,
    description: "Characters of Hamlet",
    members: [cordelia.user_id],
};

var backend = {
    name: "Backend",
    id: 2,
    description: "Backend team",
    members: [],
};

var edgecase_group = {
    name: "Bobby <h1>Tables</h1>",
    id: 3,
    description: "HTML Syntax to check for Markdown edge cases.",
    members: [],
};

global.user_groups.add(hamletcharacters);
global.user_groups.add(backend);
global.user_groups.add(edgecase_group);

var stream_data = global.stream_data;
var denmark = {
    subscribed: false,
    color: 'blue',
    name: 'Denmark',
    stream_id: 1,
    in_home_view: false,
};
var social = {
    subscribed: true,
    color: 'red',
    name: 'social',
    stream_id: 2,
    in_home_view: true,
    invite_only: true,
};
var edgecase_stream = {
    subscribed: true,
    color: 'green',
    name: 'Bobby <h1>Tables</h1>',
    stream_id: 3,
    in_home_view: true,
};
stream_data.add_sub('Denmark', denmark);
stream_data.add_sub('social', social);
stream_data.add_sub('Bobby <h1>Tables</h1>', edgecase_stream);

// Check the default behavior of fenced code blocks
// works properly before markdown is initialized.
run_test('fenced_block_defaults', () => {
    var input = '\n```\nfenced code\n```\n\nand then after\n';
    var expected = '\n\n<div class="codehilite"><pre><span></span>fenced code\n</pre></div>\n\n\n\nand then after\n\n';
    var output = fenced_code.process_fenced_code(input);
    assert.equal(output, expected);
});

markdown.initialize();

var bugdown_data = global.read_fixture_data('markdown_test_cases.json');

run_test('bugdown_detection', () => {
    var no_markup = [
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
        "We like to code\n~~~\ndef code():\n    we = \"like to do\"\n~~~",
        "This is a\nmultiline :emoji: here\n message",
        "This is an :emoji: message",
        "User Mention @**leo**",
        "User Mention @**leo f**",
        "User Mention @**leo with some name**",
        "Group Mention @*hamletcharacters*",
        "Stream #**Verona**",
        "This contains !gravatar(leo@zulip.com)",
        "And an avatar !avatar(leo@zulip.com) is here",
    ];

    var markup = [
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

    no_markup.forEach(function (content) {
        assert.equal(markdown.contains_backend_only_syntax(content), false);
    });

    markup.forEach(function (content) {
        assert.equal(markdown.contains_backend_only_syntax(content), true);
    });
});

run_test('marked_shared', () => {
    var tests = bugdown_data.regular_tests;

    tests.forEach(function (test) {

        // Ignore tests if specified
        if (test.ignore === true) {
            return;
        }

        var message = {raw_content: test.input};
        page_params.translate_emoticons = test.translate_emoticons || false;
        markdown.apply_markdown(message);
        var output = message.content;
        var error_message = `Failure in test: ${test.name}`;
        if (test.marked_expected_output) {
            global.bugdown_assert.notEqual(test.expected_output, output, error_message);
            global.bugdown_assert.equal(test.marked_expected_output, output, error_message);
        } else if (test.backend_only_rendering) {
            assert.equal(markdown.contains_backend_only_syntax(test.input), true);
        } else {
            global.bugdown_assert.equal(test.expected_output, output, error_message);
        }
    });
});

run_test('message_flags', () => {
    var message = {raw_content: '@**Leo**'};
    markdown.apply_markdown(message);
    assert(!message.mentioned);
    assert(!message.mentioned_me_directly);

    message = {raw_content: '@**Cordelia Lear**'};
    markdown.apply_markdown(message);
    assert(message.mentioned);
    assert(message.mentioned_me_directly);

    message = {raw_content: '@**all**'};
    markdown.apply_markdown(message);
    assert(message.mentioned);
    assert(!message.mentioned_me_directly);
});

run_test('marked', () => {
    var test_cases = [
        {input: 'hello', expected: '<p>hello</p>'},
        {input: 'hello there', expected: '<p>hello there</p>'},
        {input: 'hello **bold** for you', expected: '<p>hello <strong>bold</strong> for you</p>'},
        {input: 'hello ***foo*** for you', expected: '<p>hello <strong><em>foo</em></strong> for you</p>'},
        {input: '__hello__', expected: '<p>__hello__</p>'},
        {input: '\n```\nfenced code\n```\n\nand then after\n',
         expected: '<div class="codehilite"><pre><span></span>fenced code\n</pre></div>\n\n\n<p>and then after</p>'},
        {input: '\n```\n    fenced code trailing whitespace            \n```\n\nand then after\n',
         expected: '<div class="codehilite"><pre><span></span>    fenced code trailing whitespace\n</pre></div>\n\n\n<p>and then after</p>'},
        {input: '* a\n* list \n* here',
         expected: '<ul>\n<li>a</li>\n<li>list </li>\n<li>here</li>\n</ul>'},
        {input: '\n```c#\nfenced code special\n```\n\nand then after\n',
         expected: '<div class="codehilite"><pre><span></span>fenced code special\n</pre></div>\n\n\n<p>and then after</p>'},
        {input: '\n```vb.net\nfenced code dot\n```\n\nand then after\n',
         expected: '<div class="codehilite"><pre><span></span>fenced code dot\n</pre></div>\n\n\n<p>and then after</p>'},
        {input: 'Some text first\n* a\n* list \n* here\n\nand then after',
         expected: '<p>Some text first</p>\n<ul>\n<li>a</li>\n<li>list </li>\n<li>here</li>\n</ul>\n<p>and then after</p>'},
        {input: '1. an\n2. ordered \n3. list',
         expected: '<p>1. an<br>\n2. ordered<br>\n3. list</p>'},
        {input: '\n~~~quote\nquote this for me\n~~~\nthanks\n',
         expected: '<blockquote>\n<p>quote this for me</p>\n</blockquote>\n<p>thanks</p>'},
        {input: 'This is a @**Cordelia Lear** mention',
         expected: '<p>This is a <span class="user-mention" data-user-id="101">@Cordelia Lear</span> mention</p>'},
        {input: 'These @ @**** are not mentions',
         expected: '<p>These @ @<em>**</em> are not mentions</p>'},
        {input: 'These # #**** are not mentions',
         expected: '<p>These # #<em>**</em> are not mentions</p>'},
        {input: 'These @* are not mentions',
         expected: '<p>These @* are not mentions</p>'},
        {input: 'These #* #*** are also not mentions',
         expected: '<p>These #* #*** are also not mentions</p>'},
        {input: 'This is a #**Denmark** stream link',
         expected: '<p>This is a <a class="stream" data-stream-id="1" href="http://zulip.zulipdev.com/#narrow/stream/1-Denmark">#Denmark</a> stream link</p>'},
        {input: 'This is #**Denmark** and #**social** stream links',
         expected: '<p>This is <a class="stream" data-stream-id="1" href="http://zulip.zulipdev.com/#narrow/stream/1-Denmark">#Denmark</a> and <a class="stream" data-stream-id="2" href="http://zulip.zulipdev.com/#narrow/stream/2-social">#social</a> stream links</p>'},
        {input: 'And this is a #**wrong** stream link',
         expected: '<p>And this is a #**wrong** stream link</p>'},
        {input: 'mmm...:burrito:s',
         expected: '<p>mmm...<img alt=":burrito:" class="emoji" src="/static/generated/emoji/images/emoji/burrito.png" title="burrito">s</p>'},
        {input: 'This is an :poop: message',
         expected: '<p>This is an <span aria-label="poop" class="emoji emoji-1f4a9" role="img" title="poop">:poop:</span> message</p>'},
        {input: "\ud83d\udca9",
         expected: '<p><span aria-label="poop" class="emoji emoji-1f4a9" role="img" title="poop">:poop:</span></p>'},
        {input: '\u{1f6b2}',
         expected: '<p>\u{1f6b2}</p>' },
        {input: 'Silent mention: @_**Cordelia Lear**',
         expected: '<p>Silent mention: <span class="user-mention silent" data-user-id="101">Cordelia Lear</span></p>'},
        {input: '> Mention in quote: @**Cordelia Lear**\n\nMention outside quote: @**Cordelia Lear**',
         expected: '<blockquote>\n<p>Mention in quote: <span class="user-mention silent" data-user-id="101">Cordelia Lear</span></p>\n</blockquote>\n<p>Mention outside quote: <span class="user-mention" data-user-id="101">@Cordelia Lear</span></p>'},
        // Test only those realm filters which don't return True for
        // `contains_backend_only_syntax()`. Those which return True
        // are tested separately.
        {input: 'This is a realm filter #1234 with text after it',
         expected: '<p>This is a realm filter <a href="https://trac.zulip.net/ticket/1234" target="_blank" title="https://trac.zulip.net/ticket/1234">#1234</a> with text after it</p>'},
        {input: '#1234is not a realm filter.',
         expected: '<p>#1234is not a realm filter.</p>'},
        {input: 'A pattern written as #1234is not a realm filter.',
         expected: '<p>A pattern written as #1234is not a realm filter.</p>'},
        {input: 'This is a realm filter with ZGROUP_123:45 groups',
         expected: '<p>This is a realm filter with <a href="https://zone_45.zulip.net/ticket/123" target="_blank" title="https://zone_45.zulip.net/ticket/123">ZGROUP_123:45</a> groups</p>'},
        {input: 'This is an !avatar(cordelia@zulip.com) of Cordelia Lear',
         expected: '<p>This is an <img alt="cordelia@zulip.com" class="message_body_gravatar" src="/avatar/cordelia@zulip.com?s=30" title="cordelia@zulip.com"> of Cordelia Lear</p>'},
        {input: 'This is a !gravatar(cordelia@zulip.com) of Cordelia Lear',
         expected: '<p>This is a <img alt="cordelia@zulip.com" class="message_body_gravatar" src="/avatar/cordelia@zulip.com?s=30" title="cordelia@zulip.com"> of Cordelia Lear</p>'},
        {input: 'Test *italic*',
         expected: '<p>Test <em>italic</em></p>'},
        {input: 'T\n#**Denmark**',
         expected: '<p>T<br>\n<a class="stream" data-stream-id="1" href="http://zulip.zulipdev.com/#narrow/stream/1-Denmark">#Denmark</a></p>'},
        {input: 'T\n@**Cordelia Lear**',
         expected: '<p>T<br>\n<span class="user-mention" data-user-id="101">@Cordelia Lear</span></p>'},
        {input: '@**Mark Twin|104** and @**Mark Twin|105** are out to confuse you.',
         expected: '<p><span class="user-mention" data-user-id="104">@Mark Twin</span> and <span class="user-mention" data-user-id="105">@Mark Twin</span> are out to confuse you.</p>'},
        {input: '@**Invalid User|1234**',
         expected: '<p>@**Invalid User|1234**</p>'},
        {input: '@**Cordelia Lear|103** has a wrong user_id.',
         expected: '<p>@**Cordelia Lear|103** has a wrong user_id.</p>'},
        {input: '@**Brother of Bobby|123** is really the full name.',
         expected: '<p><span class="user-mention" data-user-id="106">@Brother of Bobby|123</span> is really the full name.</p>'},
        {input: '@**Brother of Bobby|123|106**',
         expected: '<p><span class="user-mention" data-user-id="106">@Brother of Bobby|123</span></p>'},
        {input: 'T\n@hamletcharacters',
         expected: '<p>T<br>\n@hamletcharacters</p>'},
        {input: 'T\n@*hamletcharacters*',
         expected: '<p>T<br>\n<span class="user-group-mention" data-user-group-id="1">@hamletcharacters</span></p>'},
        {input: 'T\n@*notagroup*',
         expected: '<p>T<br>\n@*notagroup*</p>'},
        {input: 'T\n@*backend*',
         expected: '<p>T<br>\n<span class="user-group-mention" data-user-group-id="2">@Backend</span></p>'},
        {input: '@*notagroup*',
         expected: '<p>@*notagroup*</p>'},
        {input: 'This is a realm filter `hello` with text after it',
         expected: '<p>This is a realm filter <code>hello</code> with text after it</p>'},
        // Test the emoticon conversion
        {input: ':)',
         expected: '<p>:)</p>'},
        {input: ':)',
         expected: '<p><span aria-label="slight smile" class="emoji emoji-1f642" role="img" title="slight smile">:slight_smile:</span></p>',
         translate_emoticons: true},
        // Test HTML Escape in Custom Zulip Rules
        {input: '@**<h1>The Rogue One</h1>**',
         expected: '<p>@**&lt;h1&gt;The Rogue One&lt;/h1&gt;**</p>'},
        {input: '#**<h1>The Rogue One</h1>**',
         expected: '<p>#**&lt;h1&gt;The Rogue One&lt;/h1&gt;**</p>'},
        {input: '!avatar(<h1>The Rogue One</h1>)',
         expected: '<p><img alt="&lt;h1&gt;The Rogue One&lt;/h1&gt;" class="message_body_gravatar" src="/avatar/&lt;h1&gt;The Rogue One&lt;/h1&gt;?s=30" title="&lt;h1&gt;The Rogue One&lt;/h1&gt;"></p>'},
        {input: ':<h1>The Rogue One</h1>:',
         expected: '<p>:&lt;h1&gt;The Rogue One&lt;/h1&gt;:</p>'},
        {input: '@**O\'Connell**',
         expected: '<p>@**O&#39;Connell**</p>'},
        {input: '@*Bobby <h1>Tables</h1>*',
         expected: '<p><span class="user-group-mention" data-user-group-id="3">@Bobby &lt;h1&gt;Tables&lt;/h1&gt;</span></p>'},
        {input: '@**Bobby <h1>Tables</h1>**',
         expected: '<p><span class="user-mention" data-user-id="103">@Bobby &lt;h1&gt;Tables&lt;/h1&gt;</span></p>'},
        {input: '#**Bobby <h1>Tables</h1>**',
         expected: '<p><a class="stream" data-stream-id="3" href="http://zulip.zulipdev.com/#narrow/stream/3-Bobby-.3Ch1.3ETables.3C.2Fh1.3E">#Bobby &lt;h1&gt;Tables&lt;/h1&gt;</a></p>'},
    ];

    // We remove one of the unicode emoji we put as input in one of the test
    // cases (U+1F6B2), to verify that we display the emoji as it was input if it
    // isn't present in emoji_codes.codepoint_to_name.
    delete emoji_codes.codepoint_to_name['1f6b2'];

    test_cases.forEach(function (test_case) {
        // Disable emoji conversion by default.
        page_params.translate_emoticons = test_case.translate_emoticons || false;

        var input = test_case.input;
        var expected = test_case.expected;

        var message = {raw_content: input};
        markdown.apply_markdown(message);
        var output = message.content;
        assert.equal(expected, output);
    });
});

run_test('topic_links', () => {
    var message = {type: 'stream', topic: "No links here"};
    markdown.add_topic_links(message);
    assert.equal(util.get_topic_links(message).length, []);

    message = {type: 'stream', topic: "One #123 link here"};
    markdown.add_topic_links(message);
    assert.equal(util.get_topic_links(message).length, 1);
    assert.equal(util.get_topic_links(message)[0], "https://trac.zulip.net/ticket/123");

    message = {type: 'stream', topic: "Two #123 #456 link here"};
    markdown.add_topic_links(message);
    assert.equal(util.get_topic_links(message).length, 2);
    assert.equal(util.get_topic_links(message)[0], "https://trac.zulip.net/ticket/123");
    assert.equal(util.get_topic_links(message)[1], "https://trac.zulip.net/ticket/456");

    message = {type: 'stream', topic: "New ZBUG_123 link here"};
    markdown.add_topic_links(message);
    assert.equal(util.get_topic_links(message).length, 1);
    assert.equal(util.get_topic_links(message)[0], "https://trac2.zulip.net/ticket/123");

    message = {type: 'stream', topic: "New ZBUG_123 with #456 link here"};
    markdown.add_topic_links(message);
    assert.equal(util.get_topic_links(message).length, 2);
    assert(util.get_topic_links(message).indexOf("https://trac2.zulip.net/ticket/123") !== -1);
    assert(util.get_topic_links(message).indexOf("https://trac.zulip.net/ticket/456") !== -1);

    message = {type: 'stream', topic: "One ZGROUP_123:45 link here"};
    markdown.add_topic_links(message);
    assert.equal(util.get_topic_links(message).length, 1);
    assert.equal(util.get_topic_links(message)[0], "https://zone_45.zulip.net/ticket/123");

    message = {type: "not-stream"};
    markdown.add_topic_links(message);
    assert.equal(util.get_topic_links(message).length, 0);
});

run_test('message_flags', () => {
    var input = "/me is testing this";
    var message = {topic: "No links here", raw_content: input};
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

run_test('backend_only_realm_filters', () => {
    var backend_only_realm_filters = [
        'Here is the PR-#123.',
        'Function abc() was introduced in (PR)#123.',
    ];
    backend_only_realm_filters.forEach(function (content) {
        assert.equal(markdown.contains_backend_only_syntax(content), true);
    });
});

run_test('python_to_js_filter', () => {
    // The only way to reach python_to_js_filter is indirectly, hence the call
    // to set_realm_filters.
    markdown.set_realm_filters([['/a(?im)a/g'], ['/a(?L)a/g']]);
    var actual_value = marked.InlineLexer.rules.zulip.realm_filters;
    var expected_value = [/\/aa\/g(?![\w])/gim, /\/aa\/g(?![\w])/g];
    assert.deepEqual(actual_value, expected_value);
    // Test case with multiple replacements.
    markdown.set_realm_filters([['#cf(?P<contest>[0-9]+)(?P<problem>[A-Z][0-9A-Z]*)', 'http://google.com']]);
    actual_value = marked.InlineLexer.rules.zulip.realm_filters;
    expected_value = [/#cf([0-9]+)([A-Z][0-9A-Z]*)(?![\w])/g];
    assert.deepEqual(actual_value, expected_value);
    // Test incorrect syntax.
    blueslip.set_test_data('error', 'python_to_js_filter: Invalid regular expression: /!@#@(!#&((!&(@#((?![\\w])/: Unterminated group');
    markdown.set_realm_filters([['!@#@(!#&((!&(@#(', 'http://google.com']]);
    actual_value = marked.InlineLexer.rules.zulip.realm_filters;
    expected_value = [];
    assert.deepEqual(actual_value, expected_value);
    assert.equal(blueslip.get_test_logs('error').length, 1);
    blueslip.clear_test_data();
});

run_test('katex_throws_unexpected_exceptions', () => {
    katex.renderToString = function () { throw new Error('some-exception'); };
    blueslip.set_test_data('error', 'Error: some-exception');
    var message = { raw_content: '$$a$$' };
    markdown.apply_markdown(message);
    assert.equal(blueslip.get_test_logs('error').length, 1);
    blueslip.clear_test_data();
});

run_test('misc_helpers', () => {
    const elem = $('.user-mention');
    markdown.set_name_in_mention_element(elem, 'Aaron');
    assert.equal(elem.text(), '@Aaron');
    elem.addClass('silent');
    markdown.set_name_in_mention_element(elem, 'Aaron, but silent');
    assert.equal(elem.text(), 'Aaron, but silent');
});
