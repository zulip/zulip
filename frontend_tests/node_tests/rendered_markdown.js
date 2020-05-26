const rm = zrequire('rendered_markdown');
set_global('moment', zrequire('moment', 'moment-timezone'));
zrequire('people');
zrequire('user_groups');
zrequire('stream_data');
zrequire('timerender');
set_global('$', global.make_zjquery());

set_global('rtl', {
    get_direction: () => 'ltr',
});

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
people.add_active_user(iago);
people.add_active_user(cordelia);
people.initialize_current_user(iago.user_id);

const group_me = {
    name: 'my user group',
    id: 1,
    members: [iago.user_id, cordelia.user_id],
};
const group_other = {
    name: 'other user group',
    id: 2,
    members: [cordelia.user_id],
};
user_groups.initialize({
    realm_user_groups: [group_me, group_other],
});

const stream = {
    subscribed: true,
    color: 'yellow',
    name: 'test',
    stream_id: 3,
    is_muted: true,
    invite_only: false,
};
stream_data.add_sub(stream);

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
    $content.set_find_results('span.timestamp', $array([]));
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


run_test('user-group-mention', () => {
    // Setup
    const $content = get_content_element();
    const $group_me = $.create('.user-group-mention(me)');
    $group_me.set_find_results('.highlight', false);
    $group_me.attr('data-user-group-id', group_me.id);
    const $group_other = $.create('.user-group-mention(other)');
    $group_other.set_find_results('.highlight', false);
    $group_other.attr('data-user-group-id', group_other.id);
    $content.set_find_results('.user-group-mention', $array([$group_me, $group_other]));

    // Initial asserts
    assert(!$group_me.hasClass('user-mention-me'));
    assert.equal($group_me.text(), 'never-been-set');
    assert.equal($group_other.text(), 'never-been-set');

    rm.update_elements($content);

    // Final asserts
    assert($group_me.hasClass('user-mention-me'));
    assert.equal($group_me.text(), `@${group_me.name}`);
    assert.equal($group_other.text(), `@${group_other.name}`);
});

run_test('stream-links', () => {
    // Setup
    const $content = get_content_element();
    const $stream = $.create('a.stream');
    $stream.set_find_results('.highlight', false);
    $stream.attr('data-stream-id', stream.stream_id);
    const $stream_topic = $.create('a.stream-topic');
    $stream_topic.set_find_results('.highlight', false);
    $stream_topic.attr('data-stream-id', stream.stream_id);
    $stream_topic.text('#random>topic name');
    $content.set_find_results('a.stream', $array([$stream]));
    $content.set_find_results('a.stream-topic', $array([$stream_topic]));

    // Initial asserts
    assert.equal($stream.text(), 'never-been-set');
    assert.equal($stream_topic.text(), '#random>topic name');

    rm.update_elements($content);

    // Final asserts
    assert.equal($stream.text(), `#${stream.name}`);
    assert.equal($stream_topic.text(), `#${stream.name} > topic name`);
});

run_test('timestamp', () => {
    // Setup
    const $content = get_content_element();
    const $timestamp = $.create('timestamp(valid)');
    $timestamp.attr('data-timestamp', 1);
    const $timestamp_invalid = $.create('timestamp(invalid)');
    $timestamp.addClass('timestamp');
    $timestamp_invalid.addClass('timestamp');
    $content.set_find_results('span.timestamp', $array([$timestamp, $timestamp_invalid]));

    // Initial asserts
    assert.equal($timestamp.text(), 'never-been-set');
    assert.equal($timestamp_invalid.text(), 'never-been-set');

    rm.update_elements($content);

    // Final asserts
    assert($timestamp.hasClass('timestamp'));
    assert(!$timestamp_invalid.hasClass('timestamp'));
    assert.equal($timestamp.text(), 'Thu, Jan 1 1970, 12:00 AM');
    assert.equal($timestamp.attr('title'), "This time is in your timezone. Original text was 'never-been-set'.");
    assert.equal($timestamp_invalid.text(), 'never-been-set');
    assert.equal($timestamp_invalid.attr('title'), 'Could not parse timestamp.');
});

run_test('emoji', () => {
    // Setup
    const $content = get_content_element();
    const $emoji = $.create('.emoji');
    $emoji.attr('title', 'tada');
    let called = false;
    $emoji.replaceWith = (f) => {
        const text = f.call($emoji);
        assert.equal(':tada:', text);
        called = true;
    };
    $content.set_find_results('.emoji', $emoji);
    page_params.emojiset = 'text';

    rm.update_elements($content);

    assert(called);
});
