set_global('page_params', {
    search_pills_enabled: false,
});
zrequire('search');
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
set_global('Filter', {});

global.patch_builtin('setTimeout', func => func());

run_test('update_button_visibility', () => {
    const search_query = $('#search_query');
    const search_button = $('.search_button');

    search_query.is = return_false;
    search_query.val('');
    narrow_state.active = return_false;
    search_button.prop('disabled', false);

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

run_test('initialize', () => {
    const search_query_box = $('#search_query');
    const searchbox_form = $('#searchbox_form');
    const search_button = $('.search_button');

    searchbox_form.on = (event, func) => {
        assert.equal(event, 'compositionend');
        search.is_using_input_method = false;
        func();
        assert(search.is_using_input_method);
    };

    search_suggestion.max_num_of_search_results = 999;
    search_query_box.typeahead = (opts) => {
        assert.equal(opts.fixed, true);
        assert.equal(opts.items, 999);
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
            search_suggestion.get_suggestions_legacy = () => search_suggestions;
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
            search_query_box.blur = () => {
                is_blurred = true;
            };
            /* Test updater */
            const _setup = (search_box_val) => {
                is_blurred = false;
                search_query_box.val(search_box_val);
                Filter.parse = (search_string) => {
                    assert.equal(search_string, search_box_val);
                    return operators;
                };
                narrow.activate = (raw_operators, options) => {
                    assert.deepEqual(raw_operators, operators);
                    assert.deepEqual(options, {trigger: 'search'});
                };
            };

            operators = [{
                negated: false,
                operator: 'search',
                operand: 'ver',
            }];
            _setup('ver');
            assert.equal(opts.updater('ver'), 'ver');
            assert(is_blurred);

            operators = [{
                negated: false,
                operator: 'stream',
                operand: 'Verona',
            }];
            _setup('stream:Verona');
            assert.equal(opts.updater('stream:Verona'), 'stream:Verona');
            assert(is_blurred);

            search.is_using_input_method = true;
            _setup('stream:Verona');
            assert.equal(opts.updater('stream:Verona'), 'stream:Verona');
            assert(!is_blurred);
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
            Filter.parse = (search_string) => {
                assert.equal(search_string, search_box_val);
                return operators;
            };
            narrow.activate = (raw_operators, options) => {
                assert.deepEqual(raw_operators, operators);
                assert.deepEqual(options, {trigger: 'search'});
            };
        };

        operators = [{
            negated: false,
            operator: 'search',
            operand: '',
        }];
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

    search.initialize();
});

run_test('initiate_search', () => {
    let is_searchbox_selected = false;
    $('#search_query').select = () => {
        is_searchbox_selected = true;
    };
    search.initiate_search();
    assert(is_searchbox_selected);
});
