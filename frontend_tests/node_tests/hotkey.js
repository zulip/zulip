// Important note on these tests:
//
// The way the Zulip hotkey tests work is as follows.  First, we set
// up various contexts by monkey-patching the various hotkeys exports
// functions (like overlays.settings_open).  Within that context, to
// test whether a given key (e.g. `x`) results in a specific function
// (e.g. `ui.foo()`), we fail to import any modules other than
// hotkey.js so that accessing them will result in a ReferenceError.
//
// Then we create a stub `ui.foo`, and call the hotkey function.  If
// it calls any external module other than `ui.foo`, it'll crash.
// Future work includes making sure it actually does call `ui.foo()`.

set_global('activity', {
});

set_global('drafts', {
});

set_global('page_params', {
});

set_global('overlays', {
});

set_global('$', function () {
    return {
        // Hack: Used for reactions hotkeys; may want to restructure.
        find: function () {return ['target'];},
        keydown: function () {},
        keypress: function () {},
    };
});

set_global('document', {
});

var hotkey = require('js/hotkey.js');

set_global('list_util', {
});

set_global('current_msg_list', {
    selected_id: function () {
        return 42;
    },
    selected_message: function () {
        return {
            sent_by_me: true,
            flags: ["read", "starred"],
        };
    },
    selected_row: function () {},
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

    function map_down(which, shiftKey, ctrlKey) {
        return hotkey.get_keydown_hotkey({
            which: which,
            shiftKey: shiftKey,
            ctrlKey: ctrlKey,
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

    assert.equal(map_down(219, false, true).name, 'escape');

    // More negative tests.
    assert.equal(map_down(47), undefined);
    assert.equal(map_press(27), undefined);
    assert.equal(map_down(27, true), undefined);
    assert.equal(map_down(67, false, true), undefined); // ctrl + c
    assert.equal(map_down(86, false, true), undefined); // ctrl + v
    assert.equal(map_down(90, false, true), undefined); // ctrl + z
    assert.equal(map_down(84, false, true), undefined); // ctrl + t
    assert.equal(map_down(82, false, true), undefined); // ctrl + r
    assert.equal(map_down(79, false, true), undefined); // ctrl + o
    assert.equal(map_down(80, false, true), undefined); // ctrl + p
    assert.equal(map_down(65, false, true), undefined); // ctrl + a
    assert.equal(map_down(83, false, true), undefined); // ctrl + s
    assert.equal(map_down(70, false, true), undefined); // ctrl + f
    assert.equal(map_down(72, false, true), undefined); // ctrl + h
    assert.equal(map_down(88, false, true), undefined); // ctrl + x
    assert.equal(map_down(78, false, true), undefined); // ctrl + n
    assert.equal(map_down(77, false, true), undefined); // ctrl + m
}());

(function test_basic_chars() {
    function process(s) {
        var e = {
            which: s.charCodeAt(0),
        };
        try {
            return hotkey.process_keypress(e);
        } catch (err) {
            // An exception will be thrown here if a different
            // function is called than the one declared.  Try to
            // provide a useful error message.
            // add a newline to seperate from other console output.
            console.log('\nERROR: Mapping for character "' + e.which + '" does not match tests.');
        }
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
    assert_unmapped('abefhlmoptxyz');
    assert_unmapped('BEFHILNOQTUWXYZ');

    // We have to skip some checks due to the way the code is
    // currently organized for mapped keys.
    hotkey.is_editing_stream_name = return_false;
    overlays.settings_open = return_false;

    set_global('popovers', {
        actions_popped: return_false,
    });
    set_global('emoji_picker', {
        reactions_popped: return_false,
    });
    set_global('hotspots', {
        is_open: return_false,
    });

    // All letters should return false if we are composing text.
    hotkey.processing_text = return_true;

    function test_normal_typing() {
        assert_unmapped('abcdefghijklmnopqrstuvwxyz');
        assert_unmapped(' ');
        assert_unmapped('[]\\.,;');
        assert_unmapped('ABCDEFGHIJKLMNOPQRSTUVWXYZ');
        assert_unmapped('~!@#$%^*()_+{}:"<>');
    }

    _.each([return_true, return_false], function (settings_open) {
        _.each([return_true, return_false], function (is_active) {
            _.each([return_true, return_false], function (info_overlay_open) {
                set_global('overlays', {
                    is_active: is_active,
                    settings_open: settings_open,
                    info_overlay_open: info_overlay_open});

                test_normal_typing();
            });
        });
    });

    // Ok, now test keys that work when we're viewing messages.
    hotkey.processing_text = return_false;
    overlays.settings_open = return_false;

    page_params.can_create_streams = true;
    overlays.streams_open = return_true;
    overlays.is_active = return_true;
    assert_mapping('S', 'subs.keyboard_sub');
    assert_mapping('V', 'subs.view_stream');
    assert_mapping('n', 'subs.new_stream_clicked');
    page_params.can_create_streams = false;
    assert_unmapped('n');
    overlays.is_active = return_false;
    overlays.streams_open = return_false;

    assert_mapping('?', 'ui.maybe_show_keyboard_shortcuts');
    assert_mapping('/', 'search.initiate_search');
    assert_mapping('w', 'activity.initiate_search');
    assert_mapping('q', 'stream_list.initiate_search');

    assert_mapping('A', 'narrow.stream_cycle_backward');
    assert_mapping('D', 'narrow.stream_cycle_forward');

    assert_mapping('c', 'compose_actions.start');
    assert_mapping('C', 'compose_actions.start');
    assert_mapping('P', 'narrow.by');
    assert_mapping('g', 'gear_menu.open');
    assert_mapping('d', 'drafts.toggle');

    // Next, test keys that only work on a selected message.
    var message_view_only_keys = '@*+RjJkKsSuvi:GM';

    // Check that they do nothing without a selected message
    global.current_msg_list.empty = return_true;
    assert_unmapped(message_view_only_keys);

    global.current_msg_list.empty = return_false;

    // Check that they do nothing while in the settings overlay
    overlays.settings_open = return_true;
    assert_unmapped('@*+-rRjJkKsSuvi:GM');
    overlays.settings_open = return_false;

    // TODO: Similar check for being in the subs page

    assert_mapping('@', 'compose_actions.reply_with_mention');
    assert_mapping('*', 'message_flags.toggle_starred');
    assert_mapping('+', 'reactions.toggle_emoji_reaction');
    assert_mapping('-', 'condense.toggle_collapse');
    assert_mapping('r', 'compose_actions.respond_to_message');
    assert_mapping('R', 'compose_actions.respond_to_message', true);
    assert_mapping('j', 'navigate.down');
    assert_mapping('J', 'navigate.page_down');
    assert_mapping('k', 'navigate.up');
    assert_mapping('K', 'navigate.page_up');
    assert_mapping('s', 'narrow.by_recipient');
    assert_mapping('S', 'narrow.by_subject');
    assert_mapping('u', 'popovers.show_sender_info');
    assert_mapping('v', 'lightbox.show_from_selected_message');
    assert_mapping('i', 'popovers.open_message_menu');
    assert_mapping(':', 'reactions.open_reactions_popover', true);
    assert_mapping('G', 'navigate.to_end');
    assert_mapping('M', 'muting_ui.toggle_mute');

    // Test keys that work when a message is selected and
    // also when the message list is empty.
    assert_mapping('n', 'narrow.narrow_to_next_topic');

    global.current_msg_list.empty = return_true;
    assert_mapping('n', 'narrow.narrow_to_next_topic');

    global.current_msg_list.empty = return_false;

}());

(function test_motion_keys() {
    var codes = {
        down_arrow: 40,
        end: 35,
        home: 36,
        left_arrow: 37,
        right_arrow: 39,
        page_up: 33,
        page_down: 34,
        spacebar: 32,
        up_arrow: 38,
        '+': 187,
    };

    function process(name, shiftKey, ctrlKey) {
        var e = {
            which: codes[name],
            shiftKey: shiftKey,
            ctrlKey: ctrlKey,
        };

        try {
            return hotkey.process_keydown(e);
        } catch (err) {
            // An exception will be thrown here if a different
            // function is called than the one declared.  Try to
            // provide a useful error message.
            // add a newline to seperate from other console output.
            console.log('\nERROR: Mapping for character "' + e.which + '" does not match tests.');
        }
    }

    function assert_unmapped(name) {
        assert.equal(process(name), false);
    }

    function assert_mapping(key_name, func_name, shiftKey, ctrlKey) {
        stubbing(func_name, function () {
            assert(process(key_name, shiftKey, ctrlKey));
        });
    }

    list_util.inside_list = return_false;
    global.current_msg_list.empty = return_true;
    global.drafts.drafts_overlay_open = return_false;
    overlays.settings_open = return_false;
    overlays.streams_open = return_false;
    overlays.lightbox_open = return_false;

    assert_unmapped('down_arrow');
    assert_unmapped('end');
    assert_unmapped('home');
    assert_unmapped('page_up');
    assert_unmapped('page_down');
    assert_unmapped('spacebar');
    assert_unmapped('up_arrow');

    global.list_util.inside_list = return_true;
    assert_mapping('up_arrow', 'list_util.go_up');
    assert_mapping('down_arrow', 'list_util.go_down');
    list_util.inside_list = return_false;

    global.current_msg_list.empty = return_false;
    assert_mapping('down_arrow', 'navigate.down');
    assert_mapping('end', 'navigate.to_end');
    assert_mapping('home', 'navigate.to_home');
    assert_mapping('left_arrow', 'message_edit.edit_last_sent_message');
    assert_mapping('page_up', 'navigate.page_up');
    assert_mapping('page_down', 'navigate.page_down');
    assert_mapping('spacebar', 'navigate.page_down');
    assert_mapping('up_arrow', 'navigate.up');

    overlays.info_overlay_open = return_true;
    assert_unmapped('down_arrow');
    assert_unmapped('up_arrow');
    overlays.info_overlay_open = return_false;

    overlays.streams_open = return_true;
    assert_mapping('up_arrow', 'subs.switch_rows');
    assert_mapping('down_arrow', 'subs.switch_rows');
    overlays.streams_open = return_false;

    overlays.lightbox_open = return_true;
    assert_mapping('left_arrow', 'lightbox.prev');
    assert_mapping('right_arrow', 'lightbox.next');
    overlays.lightbox_open = return_false;

    hotkey.is_editing_stream_name = return_true;
    assert_unmapped('down_arrow');
    assert_unmapped('up_arrow');
    hotkey.is_editing_stream_name = return_false;

    overlays.settings_open = return_true;
    assert_unmapped('end');
    assert_unmapped('home');
    assert_unmapped('left_arrow');
    assert_unmapped('page_up');
    assert_unmapped('page_down');
    assert_unmapped('spacebar');

    assert_mapping('up_arrow', 'settings.handle_up_arrow');
    assert_mapping('down_arrow', 'settings.handle_down_arrow');
    overlays.settings_open = return_false;

    global.drafts.drafts_overlay_open = return_true;
    assert_mapping('up_arrow', 'drafts.drafts_handle_events');
    assert_mapping('down_arrow', 'drafts.drafts_handle_events');
    global.drafts.drafts_overlay_open = return_false;
}());
