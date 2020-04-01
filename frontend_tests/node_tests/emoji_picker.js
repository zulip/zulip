zrequire('emoji');
zrequire('emoji_picker');

run_test('initialize', () => {
    emoji.update_emojis({});
    emoji_picker.initialize();

    const complete_emoji_catalog = _.sortBy(emoji_picker.complete_emoji_catalog, 'name');
    assert.equal(complete_emoji_catalog.length, 10);
    assert.equal(emoji.emojis_by_name.size, 1037);

    function assert_emoji_category(ele, icon, num) {
        assert.equal(ele.icon, icon);
        assert.equal(ele.emojis.length, num);
        function check_emojis(val) {
            for (const emoji of ele.emojis) {
                assert.equal(emoji.is_realm_emoji, val);
            }
        }
        if (ele.name === 'Custom') {
            check_emojis(true);
        } else {
            check_emojis(false);
        }
    }
    assert_emoji_category(complete_emoji_catalog.pop(), 'fa-car', 170);
    assert_emoji_category(complete_emoji_catalog.pop(), 'fa-hashtag', 180);
    assert_emoji_category(complete_emoji_catalog.pop(), 'fa-smile-o', 129);
    assert_emoji_category(complete_emoji_catalog.pop(), 'fa-star-o', 6);
    assert_emoji_category(complete_emoji_catalog.pop(), 'fa-thumbs-o-up', 102);
    assert_emoji_category(complete_emoji_catalog.pop(), 'fa-lightbulb-o', 191);
    assert_emoji_category(complete_emoji_catalog.pop(), 'fa-cutlery', 92);
    assert_emoji_category(complete_emoji_catalog.pop(), 'fa-cog', 1);
    assert_emoji_category(complete_emoji_catalog.pop(), 'fa-leaf', 104);
    assert_emoji_category(complete_emoji_catalog.pop(), 'fa-soccer-ball-o', 63);
});
