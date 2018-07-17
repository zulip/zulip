set_global('$', global.make_zjquery());

set_global('templates', {});
set_global('alert_words', {
    words: ['foo', 'bar'],
});

zrequire('alert_words_ui');

run_test('render_alert_words_ui', () => {
    var word_list = $('#alert_words_list');
    var appended = [];
    word_list.append = (rendered) => {
        appended.push(rendered);
    };

    var alert_word_items = $.create('alert_word_items');
    word_list.set_find_results('.alert-word-item', alert_word_items);

    templates.render =  (name, args) => {
        assert.equal(name, 'alert_word_settings_item');
        return 'stub-' + args.word;
    };

    var new_alert_word = $('#create_alert_word_name');
    assert(!new_alert_word.is_focused());

    alert_words_ui.render_alert_words_ui();

    assert.deepEqual(appended, [
        'stub-foo',
        'stub-bar',
        'stub-',
    ]);
    assert(new_alert_word.is_focused());
});

