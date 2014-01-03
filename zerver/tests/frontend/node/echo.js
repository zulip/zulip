var assert = require('assert');
add_dependencies({
    _: 'third/underscore/underscore.js',
    marked: 'third/marked/lib/marked.js'
});

set_global('$', function (obj) {
  if (typeof obj === 'function') {
    // Run on-load setup
    obj();
  } else if (typeof obj === 'string') {
    // Selector usage
    return {on: function () {}};
  }
});

set_global('emoji', {
  emojis_by_name: {emoji: 'some/url/here/emoji.png'}
});

var echo = require('js/echo.js');

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
                     "This is an :emoji: message"
                    ];

    var markup = [
                   "Contains a https://zulip.com/image.png file",
                   "Contains a https://zulip.com/image.jpg file",
                   "https://zulip.com/image.jpg",
                   "also https://zulip.com/image.jpg",
                   "https://zulip.com/image.jpg too",
                   "Contains a zulip.com/foo.jpeg file",
                   "Contains a https://zulip.com/image.png file",
                   "User Mention @**leo**",
                   "User Mention @**leo f**",
                   "User Mention @**leo with some name**",
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

(function test_marked() {
  var test_cases = [
    {input: 'hello', expected: '<p>hello</p>'},
    {input: 'hello there', expected: '<p>hello there</p>'},
    {input: 'hello **bold** for you', expected: '<p>hello <strong>bold</strong> for you</p>'},
    {input: '__hello__', expected: '<p>__hello__</p>'},
    {input: '\n```\nfenced code\n```\n\nand then after\n', expected: '<div class="codehilite"><pre>fenced code\n</pre></div><p>and then after</p>'},
    {input: '* a\n* list \n* here',
     expected: '<ul>\n<li>a</li>\n<li>list </li>\n<li>here</li>\n</ul>'},
    {input: 'Some text first\n* a\n* list \n* here\n\nand then after',
     expected: '<p>Some text first</p>\n<ul>\n<li>a</li>\n<li>list </li>\n<li>here</li>\n</ul>\n<p>and then after</p>'},
    {input: '1. an\n2. ordered \n3. list',
     expected: '<p>1. an</p>\n<p>2. ordered </p>\n<p>3. list</p>'},
    {input: '\n~~~quote\nquote this for me\n~~~\nthanks\n',
     expected: '<blockquote><p>quote this for me</p></blockquote><p>thanks</p>'},
     {input: 'This is an :emoji: message',
      expected: '<p>This is an <img alt=":emoji:" class="emoji" src="some/url/here/emoji.png" title=":emoji:"> message</p>'}
  ];

  test_cases.forEach(function (test_case) {
    var input = test_case.input;
    var expected = test_case.expected;

    var output = echo.apply_markdown(input);

    assert.equal(expected, output);
  });
}());
