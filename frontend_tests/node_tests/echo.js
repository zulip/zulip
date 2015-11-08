/*global Dict */
var path = require('path');
var fs = require('fs');

set_global('page_params', {realm_emoji: {
  burrito: 'static/third/gemoji/images/emoji/burrito.png'
}});

add_dependencies({
    marked: 'third/marked/lib/marked.js',
    emoji: 'js/emoji.js',
    people: 'js/people.js',
    fenced_code: 'js/fenced_code.js'
});

var doc = "";
set_global('document', doc);

set_global('$', function (obj) {
  if (typeof obj === 'function') {
    // Run on-load setup
    obj();
  } else if (typeof obj === 'string') {
    // $(document).on usage
    // Selector usage
    return {on: function () {}};
  }
});

set_global('page_params', {
  realm_filters: [["#(?P<id>[0-9]{2,8})", "https://trac.zulip.net/ticket/%(id)s"],
                  ["ZBUG_(?P<id>[0-9]{2,8})", "https://trac2.zulip.net/ticket/%(id)s"],
                  ["ZGROUP_(?P<id>[0-9]{2,8}):(?P<zone>[0-9]{1,8})", "https://zone_%(zone)s.zulip.net/ticket/%(id)s"]]
});

set_global('feature_flags', {local_echo: true});

var people = require("js/people.js");
people.test_set_people_name_dict({'Cordelia Lear': {full_name: 'Cordelia Lear', email: 'cordelia@zulip.com'}});

var echo = require('js/echo.js');

var bugdown_data = JSON.parse(fs.readFileSync(path.join(__dirname, '../../zerver/fixtures/bugdown-data.json'), 'utf8', 'r'));

(function test_bugdown_detection() {

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
                     "We like to code\n~~~\ndef code():\n    we = \"like to do\"\n~~~",
                     "This is a\nmultiline :emoji: here\n message",
                     "This is an :emoji: message",
                     "User Mention @**leo**",
                     "User Mention @**leo f**",
                     "User Mention @**leo with some name**"
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
                   "This contains !gravatar(leo@zulip.com)",
                   "And an avatar !avatar(leo@zulip.com) is here"
                 ];

    no_markup.forEach(function (content) {
        assert.equal(echo.contains_bugdown(content), false);
    });

    markup.forEach(function (content) {
        assert.equal(echo.contains_bugdown(content), true);
    });
}());

(function test_marked_shared() {
  var tests = bugdown_data.regular_tests;
  tests.forEach(function (test) {
    var output = echo.apply_markdown(test.input);

    if (test.bugdown_matches_marked) {
      assert.equal(test.expected_output, output);
    } else {
      assert.notEqual(test.expected_output, output);
    }
  });
}());

(function test_marked() {
  var test_cases = [
    {input: 'hello', expected: '<p>hello</p>'},
    {input: 'hello there', expected: '<p>hello there</p>'},
    {input: 'hello **bold** for you', expected: '<p>hello <strong>bold</strong> for you</p>'},
    {input: '__hello__', expected: '<p>__hello__</p>'},
    {input: '\n```\nfenced code\n```\n\nand then after\n', expected: '<div class="codehilite"><pre>fenced code\n</pre></div>\n\n\n<p>and then after</p>'},
    {input: '* a\n* list \n* here',
     expected: '<ul>\n<li>a</li>\n<li>list </li>\n<li>here</li>\n</ul>'},
    {input: 'Some text first\n* a\n* list \n* here\n\nand then after',
     expected: '<p>Some text first</p>\n<ul>\n<li>a</li>\n<li>list </li>\n<li>here</li>\n</ul>\n<p>and then after</p>'},
    {input: '1. an\n2. ordered \n3. list',
     expected: '<p>1. an</p>\n<p>2. ordered </p>\n<p>3. list</p>'},
    {input: '\n~~~quote\nquote this for me\n~~~\nthanks\n',
     expected: '<blockquote>\n<p>quote this for me</p>\n</blockquote>\n<p>thanks</p>'},
    {input: 'This is a @**Cordelia Lear** mention',
     expected: '<p>This is a <span class="user-mention" data-user-email="cordelia@zulip.com">@Cordelia Lear</span> mention</p>'},
    {input: 'mmm...:burrito:s',
     expected: '<p>mmm...<img alt=\":burrito:\" class=\"emoji\" src=\"static/third/gemoji/images/emoji/burrito.png\" title=\":burrito:\">s</p>'},
    {input: 'This is an :poop: message',
     expected: '<p>This is an <img alt=":poop:" class="emoji" src="static/third/gemoji/images/emoji/poop.png" title=":poop:"> message</p>'},
    {input: 'This is a realm filter #1234 with text after it',
     expected: '<p>This is a realm filter <a href="https://trac.zulip.net/ticket/1234" target="_blank" title="https://trac.zulip.net/ticket/1234">#1234</a> with text after it</p>'},
    {input: 'This is a realm filter with ZGROUP_123:45 groups',
     expected: '<p>This is a realm filter with <a href="https://zone_45.zulip.net/ticket/123" target="_blank" title="https://zone_45.zulip.net/ticket/123">ZGROUP_123:45</a> groups</p>'}
  ];

  test_cases.forEach(function (test_case) {
    var input = test_case.input;
    var expected = test_case.expected;

    var output = echo.apply_markdown(input);

    assert.equal(expected, output);
  });

}());

(function test_subject_links() {
  var message = {subject: "No links here"};
  echo._add_subject_links(message);
  assert.equal(message.subject_links.length, []);

  message = {subject: "One #123 link here"};
  echo._add_subject_links(message);
  assert.equal(message.subject_links.length, 1);
  assert.equal(message.subject_links[0], "https://trac.zulip.net/ticket/123");

  message = {subject: "Two #123 #456 link here"};
  echo._add_subject_links(message);
  assert.equal(message.subject_links.length, 2);
  assert.equal(message.subject_links[0], "https://trac.zulip.net/ticket/123");
  assert.equal(message.subject_links[1], "https://trac.zulip.net/ticket/456");

  message = {subject: "New ZBUG_123 link here"};
  echo._add_subject_links(message);
  assert.equal(message.subject_links.length, 1);
  assert.equal(message.subject_links[0], "https://trac2.zulip.net/ticket/123");


  message = {subject: "New ZBUG_123 with #456 link here"};
  echo._add_subject_links(message);
  assert.equal(message.subject_links.length, 2);
  assert(message.subject_links.indexOf("https://trac2.zulip.net/ticket/123") !== -1);
  assert(message.subject_links.indexOf("https://trac.zulip.net/ticket/456") !== -1);

  message = {subject: "One ZGROUP_123:45 link here"};
  echo._add_subject_links(message);
  assert.equal(message.subject_links.length, 1);
  assert.equal(message.subject_links[0], "https://zone_45.zulip.net/ticket/123");
}());

(function test_message_flags() {
  var input = "/me is testing this";
  var message = {subject: "No links here", content: echo.apply_markdown(input), raw_content: input};
  echo._add_message_flags(message);

  assert.equal(message.flags.length, 2);
  assert(message.flags.indexOf('read') !== -1);
  assert(message.flags.indexOf('is_me_message') !== -1);

  input = "testing this @**all**";
  message = {subject: "No links here", content: echo.apply_markdown(input), raw_content: input};
  echo._add_message_flags(message);

  assert.equal(message.flags.length, 2);
  assert(message.flags.indexOf('read') !== -1);
  assert(message.flags.indexOf('mentioned') !== -1);
}());
