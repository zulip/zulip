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

(function test_basic_chars() {
    function process(s) {
        // Simulating keyboard events is a huge pain.
        var shifted_keys = '~!@#$%^*()_+{}:"<>?';
        var e = {
            which: s.charCodeAt(0),
            shiftKey: (shifted_keys.indexOf(s) >= 0),
        };
        return hotkey.process_hotkey(e);
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
