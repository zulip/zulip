add_dependencies({
    emoji_codes: 'generated/emoji/emoji_codes.js',
    emoji: 'js/emoji.js',
});

var emoji_picker = require('js/emoji_picker.js');

(function test_initialize() {
    emoji.update_emojis({});
    emoji_picker.initialize();

    var complete_emoji_catalog = _.sortBy(emoji_picker.complete_emoji_catalog, 'name');
    assert.equal(complete_emoji_catalog.length, 9);
    assert.equal(_.keys(emoji_picker.emoji_collection).length, 977);

    function assert_emoji_category(ele, icon, num) {
        assert.equal(ele.icon, icon);
        assert.equal(ele.emojis.length, num);
        function check_emojis(val) {
            _.each(ele.emojis, function (emoji) {
                assert.equal(emoji.is_realm_emoji, val);
            });
        }
        if (ele.name === 'Custom') {
            check_emojis(true);
        } else {
            check_emojis(false);
        }
    }
    assert_emoji_category(complete_emoji_catalog.pop(), 'fa-hashtag', 243);
    assert_emoji_category(complete_emoji_catalog.pop(), 'fa-thumbs-o-up', 6);
    assert_emoji_category(complete_emoji_catalog.pop(), 'fa-car', 115);
    assert_emoji_category(complete_emoji_catalog.pop(), 'fa-smile-o', 185);
    assert_emoji_category(complete_emoji_catalog.pop(), 'fa-lightbulb-o', 165);
    assert_emoji_category(complete_emoji_catalog.pop(), 'fa-leaf', 131);
    assert_emoji_category(complete_emoji_catalog.pop(), 'fa-cutlery', 68);
    assert_emoji_category(complete_emoji_catalog.pop(), 'fa-cog', 1);
    assert_emoji_category(complete_emoji_catalog.pop(), 'fa-soccer-ball-o', 54);
}());
