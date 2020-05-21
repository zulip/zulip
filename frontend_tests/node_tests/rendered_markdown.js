const rm = zrequire('rendered_markdown');
zrequire('people');
zrequire('markdown');
set_global('$', global.make_zjquery());

set_global('rtl', {
    get_direction: () => 'ltr',
});

const $array = (array) => {
    const each = (func) => {
        array.forEach(e => {
            func.call(e);
        });
    };
    return {each};
};

set_global('page_params', { emojiset: 'apple' });

const get_content_element = () => {
    $.clear_all_elements();
    const $content = $.create('.rendered_markdown');
    $content.set_find_results('.user-mention', $array([]));
    $content.set_find_results('.user-group-mention', $array([]));
    $content.set_find_results('a.stream', $array([]));
    $content.set_find_results('a.stream-topic', $array([]));
    $content.set_find_results('.emoji', $array([]));
    return $content;
};

run_test('misc_helpers', () => {
    const elem = $.create('.user-mention');
    rm.set_name_in_mention_element(elem, 'Aaron');
    assert.equal(elem.text(), '@Aaron');
    elem.addClass('silent');
    rm.set_name_in_mention_element(elem, 'Aaron, but silent');
    assert.equal(elem.text(), 'Aaron, but silent');
});

run_test('user-mention', () => {
    // Setup
    const iago = {
        email: 'iago@zulip.com',
        user_id: 30,
        full_name: 'Iago',
    };

    const cordelia = {
        email: 'cordelia@zulup.com',
        user_id: 31,
        full_name: 'Cordelia',
    };
    people.init();
    people.add(iago);
    people.add(cordelia);
    people.initialize_current_user(iago.user_id);
    const $content = get_content_element();
    const $iago = $.create('.user-mention(iago)');
    $iago.set_find_results('.highlight', false);
    $iago.attr('data-user-id', iago.user_id);
    const $cordelia = $.create('.user-mention(cordelia)');
    $cordelia.set_find_results('.highlight', false);
    $cordelia.attr('data-user-id', cordelia.user_id);
    $content.set_find_results('.user-mention', $array([$iago, $cordelia]));

    // Initial asserts
    assert(!$iago.hasClass('user-mention-me'));
    assert.equal($iago.text(), 'never-been-set');
    assert.equal($cordelia.text(), 'never-been-set');

    rm.update_elements($content);

    // Final asserts
    assert($iago.hasClass('user-mention-me'));
    assert.equal($iago.text(), `@${iago.full_name}`);
    assert.equal($cordelia.text(), `@${cordelia.full_name}`);
});
