set_global('$', global.make_zjquery());
set_global('templates', {});
set_global('reactions', {});
set_global('current_msg_list', (function () {
    var id;
    return {
        select_id: function (new_id) { id = new_id; },
        selected_id: function () { return id; },
    };
}()));

add_dependencies({
    emoji_codes: 'generated/emoji/emoji_codes.js',
    emoji: 'js/emoji.js',
});

var emoji_picker = require('js/emoji_picker.js');

set_global('popovers', {
    hide_all: function () {
        emoji_picker.hide_emoji_popover();
    },
});

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

(function test_render_emoji_popover() {
    var element = $.create('fake-add-emoji');
    popovers.compute_placement = function () { return 'fake-placement'; };
    templates.render = function (temp_file, args) {
        assert.equal(typeof args, 'object');
        if (temp_file === 'emoji_popover') {
            assert.equal(args.class, 'emoji-info-popover');
            assert.equal(args.categories.length, 9);
        } else {
            assert.equal(temp_file, 'emoji_popover_content');
            assert.equal(args.message_id, 131);
            assert.equal(args.emoji_categories.length, 9);
        }
        return 'fake-' + temp_file;
    };
    var get_used_emojis_called = false;
    reactions.get_emojis_used_by_user_for_message_id = function (id) {
        assert.equal(id, 131);
        get_used_emojis_called = true;
        return [];
    };
    var popover_created = false;
    var popover_displayed = false;
    element.popover = function (param) {
        if (typeof param === 'object') {
            assert.equal(param.placement, 'fake-placement');
            assert.equal(param.template, 'fake-emoji_popover');
            assert.equal(param.content, 'fake-emoji_popover_content');
            var popover = $.create('fake-popover');
            element.data = function (data) {
                assert.equal(data, 'popover');
                return { $tip: popover };
            };
            popover.set_find_results('.emoji-popover-subheading', $('.emoji-popover-subheading'));
            popover.set_find_results('.emoji-popover-emoji-map', $('.emoji-popover-emoji-map'));
            popover_created = true;
        } else {
            assert.equal(param, 'show');
            popover_displayed = true;
        }
    };
    var scroll_settings = {
        suppressScrollX: true,
        useKeyboard: false,
        wheelSpeed: 0.68,
    };
    var emoji_map_addscroll = false;
    var emoji_search_addscroll = false;
    $(".emoji-popover-emoji-map").perfectScrollbar = function (param) {
        assert.deepEqual(param, scroll_settings);
        emoji_map_addscroll = true;
    };
    $(".emoji-search-results-container").perfectScrollbar = function (param) {
        assert.deepEqual(param, scroll_settings);
        emoji_search_addscroll = true;
    };
    $('.emoji-popover-subheading').each = function (func) {
        func.bind($('.emoji-popover-subheading'))();
    };
    $('.emoji-popover-subheading').attr('data-section', 'Custom');
    $('.emoji-popover-subheading').position = function () {
        return { top: 121 };
    };

    emoji_picker.render_emoji_popover(element, 131);

    assert(popover_created);
    assert(get_used_emojis_called);
    assert(popover_displayed);
    assert.equal(element.prop('title'), 'Add reaction...');
    assert($('.emoji-popover-filter').is_focused());
    assert(emoji_map_addscroll);
    assert(emoji_search_addscroll);
    assert($(".emoji-popover-emoji-map").visible());
    assert($(".emoji-popover-category-tabs").visible());
    assert(!$(".emoji-search-results-container").visible());
}());

(function test_toggle_emoji_popover() {
    var element = $('fake-add-emoji');
    var emoji_map_destroyed = false;
    var emoji_search_destroyed = false;
    var popover_destroyed = false;
    var closest_called = false;
    var popover_rendered = false;

    function setup() {
        $('.has_popover').addClass('has_popover has_emoji_popover');
        $(".emoji-popover-emoji-map").perfectScrollbar = function (param) {
            assert.equal(param, 'destroy');
            emoji_map_destroyed = true;
        };
        $(".emoji-search-results-container").perfectScrollbar = function (param) {
            assert.equal(param, 'destroy');
            emoji_search_destroyed = true;
        };
        element.popover = function (param) {
            assert.equal(param, 'destroy');
            popover_destroyed = true;
        };
        element.get = function () { return [element]; };
        element.closest = function (sel) {
            assert.equal(sel, '.message_row');
            closest_called = true;
            return this;
        };
        element.data = function (param) {
            assert.equal(param, 'popover');
        };
        emoji_picker.render_emoji_popover = function (elt) {
            assert.equal(elt, element);
            popover_rendered = true;
        };
    }

    setup();
    emoji_picker.toggle_emoji_popover(element);
    assert(!$('.has_popover').hasClass('has_popover has_emoji_popover'));
    assert(emoji_map_destroyed);
    assert(emoji_search_destroyed);
    assert(popover_destroyed);
    assert(!closest_called);
    assert.equal(current_msg_list.selected_id(), undefined);
    assert(!popover_rendered);

    setup();
    emoji_picker.toggle_emoji_popover(element, 131);
    assert(!$('.has_popover').hasClass('has_popover has_emoji_popover'));
    assert(emoji_map_destroyed);
    assert(emoji_search_destroyed);
    assert(popover_destroyed);
    assert(closest_called);
    assert.equal(current_msg_list.selected_id(), 131);
    assert(popover_rendered);
}());
