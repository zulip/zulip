global.patch_builtin('window', {
    location: {
        protocol: 'http:',
        host: 'example.com',
    },
});
zrequire('people');
zrequire('hash_util');
zrequire('hashchange');
zrequire('stream_data');

set_global('document', 'document-stub');
set_global('history', {});

set_global('admin', {});
set_global('drafts', {});
set_global('favicon', {});
set_global('floating_recipient_bar', {});
set_global('info_overlay', {});
set_global('message_viewport', {});
set_global('narrow', {});
set_global('overlays', {});
set_global('settings', {});
set_global('subs', {});
set_global('ui_util', {});
set_global('blueslip', global.make_zblueslip());

run_test('operators_round_trip', () => {
    var operators;
    var hash;
    var narrow;

    operators = [
        {operator: 'stream', operand: 'devel'},
        {operator: 'topic', operand: 'algol'},
    ];
    hash = hash_util.operators_to_hash(operators);
    assert.equal(hash, '#narrow/stream/devel/topic/algol');

    narrow = hash_util.parse_narrow(hash.split('/'));
    assert.deepEqual(narrow, [
        {operator: 'stream', operand: 'devel', negated: false},
        {operator: 'topic', operand: 'algol', negated: false},
    ]);

    operators = [
        {operator: 'stream', operand: 'devel'},
        {operator: 'topic', operand: 'visual c++', negated: true},
    ];
    hash = hash_util.operators_to_hash(operators);
    assert.equal(hash, '#narrow/stream/devel/-topic/visual.20c.2B.2B');

    narrow = hash_util.parse_narrow(hash.split('/'));
    assert.deepEqual(narrow, [
        {operator: 'stream', operand: 'devel', negated: false},
        {operator: 'topic', operand: 'visual c++', negated: true},
    ]);

    // test new encodings, where we have a stream id
    var florida_stream = {
        name: 'Florida, USA',
        stream_id: 987,
    };
    stream_data.add_sub(florida_stream.name, florida_stream);
    operators = [
        {operator: 'stream', operand: 'Florida, USA'},
    ];
    hash = hash_util.operators_to_hash(operators);
    assert.equal(hash, '#narrow/stream/987-Florida.2C-USA');
    narrow = hash_util.parse_narrow(hash.split('/'));
    assert.deepEqual(narrow, [
        {operator: 'stream', operand: 'Florida, USA', negated: false},
    ]);
});

run_test('operators_trailing_slash', () => {
    var hash;
    var narrow;

    hash = '#narrow/stream/devel/topic/algol/';
    narrow = hash_util.parse_narrow(hash.split('/'));
    assert.deepEqual(narrow, [
        {operator: 'stream', operand: 'devel', negated: false},
        {operator: 'topic', operand: 'algol', negated: false},
    ]);
});

run_test('people_slugs', () => {
    var operators;
    var hash;
    var narrow;

    var alice = {
        email: 'alice@example.com',
        user_id: 42,
        full_name: 'Alice Smith',
    };

    people.add(alice);
    operators = [
        {operator: 'sender', operand: 'alice@example.com'},
    ];
    hash = hash_util.operators_to_hash(operators);
    assert.equal(hash, '#narrow/sender/42-alice');
    narrow = hash_util.parse_narrow(hash.split('/'));
    assert.deepEqual(narrow, [
        {operator: 'sender', operand: 'alice@example.com', negated: false},
    ]);

    operators = [
        {operator: 'pm-with', operand: 'alice@example.com'},
    ];
    hash = hash_util.operators_to_hash(operators);
    assert.equal(hash, '#narrow/pm-with/42-alice');
});

function test_helper() {
    var events = [];
    var narrow_terms;

    function stub(module_name, func_name) {
        global[module_name][func_name] = () => {
            events.push(module_name + '.' + func_name);
        };
    }

    stub('admin', 'launch');
    stub('drafts', 'launch');
    stub('favicon', 'reset');
    stub('floating_recipient_bar', 'update');
    stub('message_viewport', 'stop_auto_scrolling');
    stub('narrow', 'deactivate');
    stub('overlays', 'close_for_hash_change');
    stub('settings', 'launch');
    stub('subs', 'launch');
    stub('ui_util', 'blur_active_element');

    ui_util.change_tab_to = (hash) => {
        events.push('change_tab_to ' + hash);
    };

    narrow.activate = (terms) => {
        narrow_terms = terms;
        events.push('narrow.activate');
    };

    info_overlay.show = (name) => {
        events.push('info: ' + name);
    };

    return {
        clear_events: () => {
            events = [];
        },
        assert_events: (expected_events) => {
            assert.deepEqual(expected_events, events);
        },
        get_narrow_terms: () => {
            return narrow_terms;
        },
    };
}

run_test('hash_interactions', () => {
    var helper = test_helper();

    window.location.hash = '#';

    helper.clear_events();
    hashchange.initialize();
    helper.assert_events([
        'overlays.close_for_hash_change',
        'message_viewport.stop_auto_scrolling',
        'change_tab_to #home',
        'narrow.deactivate',
        'floating_recipient_bar.update',
    ]);

    helper.clear_events();
    window.onhashchange();
    helper.assert_events([
        'overlays.close_for_hash_change',
        'message_viewport.stop_auto_scrolling',
        'change_tab_to #home',
        'narrow.deactivate',
        'floating_recipient_bar.update',
    ]);

    window.location.hash = '#narrow/stream/Denmark';

    helper.clear_events();
    window.onhashchange();
    helper.assert_events([
        'overlays.close_for_hash_change',
        'message_viewport.stop_auto_scrolling',
        'change_tab_to #home',
        'narrow.activate',
        'floating_recipient_bar.update',
    ]);
    var terms = helper.get_narrow_terms();
    assert.equal(terms[0].operand, 'Denmark');

    window.location.hash = '#narrow';

    helper.clear_events();
    window.onhashchange();
    helper.assert_events([
        'overlays.close_for_hash_change',
        'message_viewport.stop_auto_scrolling',
        'change_tab_to #home',
        'narrow.activate',
        'floating_recipient_bar.update',
    ]);
    terms = helper.get_narrow_terms();
    assert.equal(terms.length, 0);

    window.location.hash = '#streams/whatever';

    helper.clear_events();
    window.onhashchange();
    helper.assert_events([
        'overlays.close_for_hash_change',
        'subs.launch',
    ]);

    window.location.hash = '#keyboard-shortcuts/whatever';

    helper.clear_events();
    window.onhashchange();
    helper.assert_events([
        'overlays.close_for_hash_change',
        'message_viewport.stop_auto_scrolling',
        'info: keyboard-shortcuts',
    ]);

    window.location.hash = '#message-formatting/whatever';

    helper.clear_events();
    window.onhashchange();
    helper.assert_events([
        'overlays.close_for_hash_change',
        'message_viewport.stop_auto_scrolling',
        'info: message-formatting',
    ]);

    window.location.hash = '#search-operators/whatever';

    helper.clear_events();
    window.onhashchange();
    helper.assert_events([
        'overlays.close_for_hash_change',
        'message_viewport.stop_auto_scrolling',
        'info: search-operators',
    ]);

    window.location.hash = '#drafts';

    helper.clear_events();
    window.onhashchange();
    helper.assert_events([
        'overlays.close_for_hash_change',
        'drafts.launch',
    ]);

    window.location.hash = '#settings/alert-words';

    helper.clear_events();
    window.onhashchange();
    helper.assert_events([
        'overlays.close_for_hash_change',
        'settings.launch',
    ]);

    window.location.hash = '#organization/user-list-admin';

    helper.clear_events();
    window.onhashchange();
    helper.assert_events([
        'overlays.close_for_hash_change',
        'admin.launch',
    ]);

    var called_back;

    helper.clear_events();
    hashchange.exit_overlay(() => {
        called_back = true;
    });

    helper.assert_events([
        'ui_util.blur_active_element',
    ]);
    assert(called_back);

});

run_test('save_narrow', () => {
    var helper = test_helper();

    var operators = [
        {operator: 'is', operand: 'private'},
    ];

    blueslip.set_test_data('warn', 'browser does not support pushState');
    hashchange.save_narrow(operators);
    blueslip.clear_test_data();

    helper.assert_events([
        'message_viewport.stop_auto_scrolling',
        'favicon.reset',
    ]);
    assert.equal(window.location.hash, '#narrow/is/private');

    var url_pushed;
    global.history.pushState = (state, title, url) => {
        url_pushed = url;
    };

    operators = [
        {operator: 'is', operand: 'starred'},
    ];

    helper.clear_events();
    hashchange.save_narrow(operators);
    helper.assert_events([
        'message_viewport.stop_auto_scrolling',
        'favicon.reset',
    ]);
    assert.equal(url_pushed, 'http://example.com/#narrow/is/starred');
});
