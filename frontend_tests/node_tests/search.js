set_global('page_params', {
    search_pills_enabled: true,
});
zrequire('search');
zrequire('search_pill');
zrequire('Filter', 'js/filter');
zrequire('search_pill_widget');
zrequire('tab_bar');

const noop = () => {};
const return_true = () => true;
const return_false = () => false;

set_global('$', global.make_zjquery());
set_global('narrow_state', {});
set_global('search_suggestion', {});
set_global('ui_util', {
    change_tab_to: noop,
});
set_global('narrow', {});

search_pill.append_search_string = noop;

global.patch_builtin('setTimeout', func => func());

run_test('clear_search_form', () => {
    $('#search_query').val('noise');
    $('#search_query').focus();
    $('.search_button').prop('disabled', false);

    search.clear_search_form();

    assert.equal($('#search_query').is_focused(), false);
    assert.equal($('#search_query').val(), '');
    assert.equal($('.search_button').prop('disabled'), true);
});

run_test('update_button_visibility', () => {
    const search_query = $('#search_query');
    const search_button = $('.search_button');

    search_query.is = return_true;
    search_query.val('');
    narrow_state.active = return_false;
    search_button.prop('disabled', true);
    search.update_button_visibility();
    assert(!search_button.prop('disabled'));

    search_query.is = return_false;
    search_query.val('Test search term');
    narrow_state.active = return_false;
    search_button.prop('disabled', true);
    search.update_button_visibility();
    assert(!search_button.prop('disabled'));

    search_query.is = return_false;
    search_query.val('');
    narrow_state.active = return_true;
    search_button.prop('disabled', true);
    search.update_button_visibility();
    assert(!search_button.prop('disabled'));
});

run_test('initizalize', () => {
    const search_query_box = $('#search_query');
    const searchbox_form = $('#searchbox_form');
    const search_button = $('.search_button');
    const searchbox = $('#searchbox');

    searchbox_form.on = (event, func) => {
        assert.equal(event, 'compositionend');
        search.is_using_input_method = false;
        func();
        assert(search.is_using_input_method);
    };

    search_pill.get_search_string_for_current_filter = function () {
        return 'is:starred';
    };

    search_suggestion.max_num_of_search_results = 99;
    search_query_box.typeahead = (opts) => {

        assert.equal(opts.fixed, true);
        assert.equal(opts.items, 99);
        assert.equal(opts.naturalSearch, true);
        assert.equal(opts.helpOnEmptyStrings, true);
        assert.equal(opts.matcher(), true);

        {
            const search_suggestions = {
                lookup_table: new Map([
                    ['stream:Verona', {
                        description: 'Stream <strong>Ver</strong>ona',
                        search_string: 'stream:Verona',
                    }],
                    ['ver', {
                        description: 'Search for ver',
                        search_string: 'ver',
                    }],
                ]),
                strings: ['ver', 'stream:Verona'],
            };

            /* Test source */
            search_suggestion.get_suggestions = () => search_suggestions;
            const expected_source_value = search_suggestions.strings;
            const source = opts.source('ver');
            assert.equal(source, expected_source_value);

            /* Test highlighter */
            let expected_value = 'Search for ver';
            assert.equal(opts.highlighter(source[0]), expected_value);

            expected_value = 'Stream <strong>Ver</strong>ona';
            assert.equal(opts.highlighter(source[1]), expected_value);

            /* Test sorter */
            assert.equal(opts.sorter(search_suggestions.strings), search_suggestions.strings);
        }

        {
            let operators;
            let is_blurred;
            let is_append_search_string_called;
            search_query_box.blur = () => {
                is_blurred = true;
            };
            search_pill.append_search_string = () => {
                is_append_search_string_called = true;
            };
            /* Test updater */
            const _setup = (search_box_val) => {
                is_blurred = false;
                is_append_search_string_called = false;
                search_query_box.val(search_box_val);
                narrow.activate = (raw_operators, options) => {
                    assert.deepEqual(raw_operators, operators);
                    assert.deepEqual(options, {trigger: 'search'});
                };
                search_pill.get_search_string_for_current_filter = () => {
                    return '';
                };
            };

            operators = [{
                negated: false,
                operator: 'search',
                operand: 'ver',
            }];
            _setup('ver');
            opts.updater('ver');
            assert(is_blurred);
            assert(is_append_search_string_called);

            operators = [{
                negated: false,
                operator: 'stream',
                operand: 'Verona',
            }];
            _setup('stream:Verona');
            opts.updater('stream:Verona');
            assert(is_blurred);
            assert(is_append_search_string_called);

            search.is_using_input_method = true;
            _setup('stream:Verona');
            opts.updater('stream:Verona');
            assert(!is_blurred);
            assert(is_append_search_string_called);
        }
    };

    searchbox_form.keydown = (func) => {
        const ev = {
            which: 15,
        };
        search_query_box.is = return_false;
        assert.equal(func(ev), undefined);

        ev.which = 13;
        assert.equal(func(ev), undefined);

        ev.which = 13;
        search_query_box.is = return_true;
        assert.equal(func(ev), false);

        return search_query_box;
    };

    search_query_box.keyup = (func) => {
        const ev = {};
        let operators;
        let is_blurred;
        narrow_state.active = return_false;
        search_query_box.blur = () => {
            is_blurred = true;
        };

        const _setup = (search_box_val) => {
            is_blurred = false;
            search_button.prop('disabled', false);
            search_query_box.val(search_box_val);
            narrow.activate = (raw_operators, options) => {
                assert.deepEqual(raw_operators, operators);
                assert.deepEqual(options, {trigger: 'search'});
            };
            search_pill.get_search_string_for_current_filter = () => {
                return '';
            };
        };

        operators = [];
        _setup('');

        ev.which = 15;
        search_query_box.is = return_false;
        func(ev);

        assert(!is_blurred);
        assert(!search_button.prop('disabled'));

        ev.which = 13;
        search_query_box.is = return_false;
        func(ev);

        assert(!is_blurred);
        assert(!search_button.prop('disabled'));

        ev.which = 13;
        search_query_box.is = return_true;
        func(ev);
        assert(is_blurred);

        operators = [{
            negated: false,
            operator: 'search',
            operand: 'ver',
        }];
        _setup('ver');
        search.is_using_input_method = true;
        func(ev);
        // No change on enter keyup event when using input tool
        assert(!is_blurred);
        assert(!search_button.prop('disabled'));

        _setup('ver');
        ev.which = 13;
        search_query_box.is = return_true;
        func(ev);
        assert(is_blurred);
        assert(!search_button.prop('disabled'));
    };

    search_query_box.on = (event, callback) => {
        if (event === 'focus') {
            search_button.prop('disabled', true);
            callback();
            assert(!search_button.prop('disabled'));
        } else if (event === 'blur') {
            search_query_box.val("test string");
            narrow_state.search_string = () => 'ver';
            callback();
            assert.equal(search_query_box.val(), 'test string');
        }
    };

    searchbox.on = (event, callback) => {
        if (event === 'focusin') {
            searchbox.css({"box-shadow": "unset"});
            callback();
            assert.deepEqual(searchbox.css(), {"box-shadow": "inset 0px 0px 0px 2px hsl(204, 20%, 74%)"});
        } else if (event === 'focusout') {
            searchbox.css({"box-shadow": "inset 0px 0px 0px 2px hsl(204, 20%, 74%)"});
            callback();
            assert.deepEqual(searchbox.css(), {"box-shadow": "unset"});
        }
    };

    search.initialize();
});

run_test('initiate_search', () => {
    let is_searchbox_focused = false;
    $('#search_query').focus = () => {
        is_searchbox_focused = true;
    };
    search.initiate_search();
    assert(is_searchbox_focused);
});
