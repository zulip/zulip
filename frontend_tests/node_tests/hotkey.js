set_global('activity', {
});

set_global('$', function () {
    return {
        keydown: function () {},
        keypress: function () {},
    };
});

set_global('document', {
});

var hotkey = require('js/hotkey.js');

set_global('current_msg_list', {
    selected_id: function () { return 42; },
});

function return_true() { return true; }
function return_false() { return false; }

function stubbing(func_name_to_stub, test_function) {
    global.with_overrides(function (override) {
        global.with_stub(function (stub) {
            override(func_name_to_stub, stub.f);
            test_function(stub);
        });
    });
}

(function test_mappings() {
    function map_press(which, shiftKey) {
        return hotkey.get_keypress_hotkey({
            which: which,
            shiftKey: shiftKey,
        });
    }

    function map_down(which, shiftKey) {
        return hotkey.get_keydown_hotkey({
            which: which,
            shiftKey: shiftKey,
        });
    }

    // The next assertion protects against an iOS bug where we
    // treat "!" as a hotkey, because iOS sends the wrong code.
    assert.equal(map_press(33), undefined);

    // Test page-up does work.
    assert.equal(map_down(33).name, 'page_up');

    // Test other mappings.
    assert.equal(map_down(9).name, 'tab');
    assert.equal(map_down(9, true).name, 'shift_tab');
    assert.equal(map_down(27).name, 'escape');
    assert.equal(map_down(37).name, 'left_arrow');
    assert.equal(map_down(13).name, 'enter');
    assert.equal(map_down(13, true).name, 'enter');

    assert.equal(map_press(47).name, 'search'); // slash
    assert.equal(map_press(106).name, 'vim_down'); // j

    // More negative tests.
    assert.equal(map_down(47), undefined);
    assert.equal(map_press(27), undefined);
    assert.equal(map_down(27, true), undefined);
}());

(function test_basic_chars() {
    function process(s) {
        var e = {
            which: s.charCodeAt(0),
        };
        return hotkey.process_keypress(e);
    }

    function assert_mapping(c, func_name, shiftKey) {
        stubbing(func_name, function () {
            assert(process(c, shiftKey));
        });
    }

    function assert_unmapped(s) {
        _.each(s, function (c) {
            assert.equal(process(c), false);
        });
    }

    // Unmapped keys should immediately return false, without
    // calling any functions outside of hotkey.js.
    assert_unmapped('abdefghlmnoptuxyz');
    assert_unmapped('BEFGHILMNOPQTUVWXYZ');

    // We have to skip some checks due to the way the code is
    // currently organized for mapped keys.
    hotkey.is_editing_stream_name = return_false;
    hotkey.is_settings_page = return_false;

    set_global('popovers', {
        actions_popped: return_false,
    });

    // All letters should return false if we are composing text.
    hotkey.processing_text = return_true;

    function test_normal_typing() {
        assert_unmapped('abcdefghijklmnopqrstuvwxyz');
        assert_unmapped(' ');
        assert_unmapped('[]\\.,;');
        assert_unmapped('ABCDEFGHIJKLMNOPQRSTUVWXYZ');
        assert_unmapped('~!@#$%^*()_+{}:"<>?');
    }

    _.each([return_true, return_false], function (is_settings_page) {
        _.each([return_true, return_false], function (home_tab_obscured) {
            hotkey.is_settings_page = is_settings_page;
            set_global('ui', {home_tab_obscured: home_tab_obscured});

            test_normal_typing();
        });
    });

    // Ok, now test keys that work when we're viewing messages.
    hotkey.processing_text = return_false;
    hotkey.is_settings_page = return_false;

    assert_mapping('?', 'ui.show_info_overlay');
    assert_mapping('/', 'search.initiate_search');
    assert_mapping('q', 'activity.initiate_search');
    assert_mapping('w', 'stream_list.initiate_search');

    assert_mapping('A', 'navigate.cycle_stream');
    assert_mapping('D', 'navigate.cycle_stream');

    assert_mapping('c', 'compose.start');
    assert_mapping('C', 'compose.start');
    assert_mapping('v', 'narrow.by');

    // Next, test keys that only work on a selected message.
    global.current_msg_list.empty = return_true;
    assert_unmapped('@rRjJkKsSi');

    global.current_msg_list.empty = return_false;

    assert_mapping('@', 'compose.reply_with_mention');
    assert_mapping('r', 'compose.respond_to_message');
    assert_mapping('R', 'compose.respond_to_message', true);
    assert_mapping('j', 'navigate.down');
    assert_mapping('J', 'navigate.page_down');
    assert_mapping('k', 'navigate.up');
    assert_mapping('K', 'navigate.page_up');
    assert_mapping('s', 'narrow.by_recipient');
    assert_mapping('S', 'narrow.by_subject');
    assert_mapping('i', 'popovers.open_message_menu');
}());

(function test_motion_keys() {
    var codes = {
        down_arrow: 40,
        end: 35,
        home: 36,
        left_arrow: 37,
        page_up: 33,
        page_down: 34,
        spacebar: 32,
        up_arrow: 38,
    };

    function process(name) {
        var e = {
            which: codes[name],
        };
        return hotkey.process_keydown(e);
    }

    function assert_unmapped(name) {
        assert.equal(process(name), false);
    }

    function assert_mapping(key_name, func_name) {
        stubbing(func_name, function () {
            assert(process(key_name));
        });
    }

    hotkey.tab_up_down = function () { return {flag: false}; };
    global.current_msg_list.empty = return_true;
    hotkey.is_settings_page = return_false;

    assert_unmapped('down_arrow');
    assert_unmapped('end');
    assert_unmapped('home');
    assert_unmapped('page_up');
    assert_unmapped('page_down');
    assert_unmapped('spacebar');
    assert_unmapped('up_arrow');

    global.current_msg_list.empty = return_false;
    assert_mapping('down_arrow', 'navigate.down');
    assert_mapping('end', 'navigate.to_end');
    assert_mapping('home', 'navigate.to_home');
    assert_mapping('left_arrow', 'message_edit.edit_last_sent_message');
    assert_mapping('page_up', 'navigate.page_up');
    assert_mapping('page_down', 'navigate.page_down');
    assert_mapping('spacebar', 'navigate.page_down');
    assert_mapping('up_arrow', 'navigate.up');

    hotkey.is_settings_page = return_true;
    assert_unmapped('end');
    assert_unmapped('home');
    assert_unmapped('left_arrow');
    assert_unmapped('page_up');
    assert_unmapped('page_down');
    assert_unmapped('spacebar');

    hotkey.is_editing_stream_name = return_true;
    assert_unmapped('down_arrow');
    assert_unmapped('up_arrow');
}());
