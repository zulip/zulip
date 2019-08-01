const typeahead = zrequire('typeahead', 'shared/js/typeahead');
zrequire('compose_state');
zrequire('pm_conversations');
zrequire('emoji');
set_global('Handlebars', global.make_handlebars());
zrequire('templates');
zrequire('typeahead_helper');
zrequire('people');
zrequire('user_groups');
zrequire('stream_data');
zrequire('user_pill');
zrequire('compose_pm_pill');
zrequire('composebox_typeahead');
zrequire('recent_senders');
zrequire('settings_org');
const settings_config = zrequire('settings_config');
set_global('md5', function (s) {
    return 'md5-' + s;
});

// To be eliminated in next commit:
stream_data.update_calculated_fields = () => {};
stream_data.set_filter_out_inactives = () => false;

set_global('stream_topic_history', {
});

set_global('message_store', {
    user_ids: () => [],
});

const ct = composebox_typeahead;
const noop = function () {};

// Use a slightly larger value than what's user-facing
// to facilitate testing different combinations of
// broadcast-mentions/persons/groups.
ct.max_num_items = 15;

const mention_all = ct.broadcast_mentions()[0];
assert.equal(mention_all.email, 'all');
assert.equal(mention_all.full_name, 'all');

const emoji_stadium = {
    name: 'stadium',
    aliases: ['stadium'],
    emoji_url: 'TBD',
    emoji_code: '1f3df',
};
const emoji_tada = {
    name: 'tada',
    aliases: ['tada'],
    emoji_url: 'TBD',
    emoji_code: '1f389',
};
const emoji_moneybag = {
    name: 'moneybag',
    aliases: ['moneybag'],
    emoji_url: 'TBD',
    emoji_code: '1f4b0',
};
const emoji_japanese_post_office = {
    name: 'japanese_post_office',
    aliases: ['japanese_post_office'],
    emoji_url: 'TBD',
    emoji_code: '1f3e3',
};
const emoji_panda_face = {
    name: 'panda_face',
    aliases: ['panda_face'],
    emoji_url: 'TBD',
    emoji_code: '1f43c',
};
const emoji_see_no_evil = {
    name: 'see_no_evil',
    aliases: ['see_no_evil'],
    emoji_url: 'TBD',
    emoji_code: '1f648',
};
const emoji_thumbs_up = {
    name: 'thumbs_up',
    aliases: ['thumbs_up'],
    emoji_url: 'TBD',
    emoji_code: '1f44d',
};
const emoji_thermometer = {
    name: 'thermometer',
    aliases: ['thermometer'],
    emoji_url: 'TBD',
    emoji_code: '1f321',
};
const emoji_heart = {
    name: 'heart',
    aliases: ['heart'],
    emoji_url: 'TBD',
    emoji_code: '2764',
};
const emoji_headphones = {
    name: 'headphones',
    aliases: ['headphones'],
    emoji_url: 'TBD',
    emoji_code: '1f3a7',
};

const emojis_by_name = new Map(Object.entries({
    tada: emoji_tada,
    moneybag: emoji_moneybag,
    stadium: emoji_stadium,
    japanese_post_office: emoji_japanese_post_office,
    panda_face: emoji_panda_face,
    see_no_evil: emoji_see_no_evil,
    thumbs_up: emoji_thumbs_up,
    thermometer: emoji_thermometer,
    heart: emoji_heart,
    headphones: emoji_headphones,
}));
const emoji_list = Array.from(emojis_by_name.values(), emoji_dict => {
    if (emoji_dict.is_realm_emoji === true) {
        return {
            emoji_name: emoji_dict.name,
            emoji_url: emoji_dict.url,
            is_realm_emoji: true,
        };
    }
    return {
        emoji_name: emoji_dict.name,
        emoji_code: emoji_dict.emoji_code,
    };
});

const me_slash = {
    name: "me",
    text: "translated: /me is excited (Display action text)",
};

const my_slash = {
    name: "my",
    text: "translated: /my (Test)",
};

const sweden_stream = {
    name: 'Sweden',
    description: 'Cold, mountains and home decor.',
    stream_id: 1,
    subscribed: true,
    can_access_subscribers: true,
};
const denmark_stream = {
    name: 'Denmark',
    description: 'Vikings and boats, in a serene and cold weather.',
    stream_id: 2,
    subscribed: true,
};
const netherland_stream = {
    name: 'The Netherlands',
    description: 'The Netherlands, city of dream.',
    stream_id: 3,
    subscribed: false,
};

stream_data.add_sub(sweden_stream);
stream_data.add_sub(denmark_stream);
stream_data.add_sub(netherland_stream);

set_global('$', global.make_zjquery());

set_global('page_params', {});
set_global('channel', {});
set_global('compose', {
    finish: noop,
});

emoji.active_realm_emojis = new Map();
emoji.emojis_by_name = emojis_by_name;
emoji.emojis = emoji_list;

const pygments_data = zrequire("pygments_data", "generated/pygments_data.json");

const alice = {
    email: 'alice@zulip.com',
    user_id: 99,
    full_name: "Alice",
};

const hamlet = {
    email: 'hamlet@zulip.com',
    user_id: 100,
    full_name: "King Hamlet",
};

const othello = {
    email: 'othello@zulip.com',
    user_id: 101,
    full_name: "Othello, the Moor of Venice",
};
const cordelia = {
    email: 'cordelia@zulip.com',
    user_id: 102,
    full_name: "Cordelia Lear",
};
const deactivated_user = {
    email: 'other@zulip.com',
    user_id: 103,
    full_name: "Deactivated User",
};
const lear = {
    email: 'lear@zulip.com',
    user_id: 104,
    full_name: "King Lear",
};

const twin1 = {
    full_name: 'Mark Twin',
    user_id: 105,
    email: 'twin1@zulip.com',
};

const twin2 = {
    full_name: 'Mark Twin',
    user_id: 106,
    email: 'twin2@zulip.com',
};

const gael = {
    full_name: 'Gaël Twin',
    user_id: 107,
    email: 'twin3@zulip.com',
};

const hal = {
    full_name: 'Earl Hal',
    user_id: 108,
    email: 'hal@zulip.com',
};

const harry = {
    full_name: 'Harry',
    user_id: 109,
    email: 'harry@zulip.com',
};

people.add_active_user(alice);
people.add_active_user(hamlet);
people.add_active_user(othello);
people.add_active_user(cordelia);
people.add_active_user(lear);
people.add_active_user(twin1);
people.add_active_user(twin2);
people.add_active_user(gael);
people.add_active_user(hal);
people.add_active_user(harry);
people.add_active_user(deactivated_user);
people.deactivate(deactivated_user);

const hamletcharacters = {
    name: "hamletcharacters",
    id: 1,
    description: "Characters of Hamlet",
    members: [100, 104],
};

const backend = {
    name: "Backend",
    id: 2,
    description: "Backend team",
    members: [],
};

const call_center = {
    name: "Call Center",
    id: 3,
    description: "folks working in support",
    members: [],
};

global.user_groups.add(hamletcharacters);
global.user_groups.add(backend);
global.user_groups.add(call_center);

const make_emoji = function (emoji_dict) {
    return { emoji_name: emoji_dict.name, emoji_code: emoji_dict.emoji_code };
};

run_test('topics_seen_for', () => {
    stream_topic_history.get_recent_topic_names = (stream_id) => {
        assert.equal(stream_id, denmark_stream.stream_id);
        return ['With Twisted Metal', 'acceptance', 'civil fears'];
    };

    assert.deepEqual(
        ct.topics_seen_for('Denmark'),
        ['With Twisted Metal', 'acceptance', 'civil fears']
    );

    // Test when the stream doesn't exist (there are no topics)
    assert.deepEqual(ct.topics_seen_for('non-existing-stream'), []);
});

run_test('content_typeahead_selected', () => {
    const fake_this = {
        query: '',
        $element: {},
    };
    let caret_called1 = false;
    let caret_called2 = false;
    fake_this.$element.caret = function (...args) {
        if (args.length === 0) {  // .caret() used in split_at_cursor
            caret_called1 = true;
            return fake_this.query.length;
        }
        const [arg1, arg2] = args;
        // .caret() used in setTimeout
        assert.equal(arg1, arg2);
        caret_called2 = true;
    };
    let autosize_called = false;
    set_global('compose_ui', {
        autosize_textarea: function () {
            autosize_called = true;
        },
    });
    let set_timeout_called = false;
    global.patch_builtin('setTimeout', function (f, time) {
        f();
        assert.equal(time, 0);
        set_timeout_called = true;
    });
    set_global('document', 'document-stub');

    // emoji
    fake_this.completing = 'emoji';
    fake_this.query = ':octo';
    fake_this.token = 'octo';
    const item = {
        emoji_name: 'octopus',
    };

    let actual_value = ct.content_typeahead_selected.call(fake_this, item);
    let expected_value = ':octopus: ';
    assert.equal(actual_value, expected_value);

    fake_this.query = ' :octo';
    fake_this.token = 'octo';
    actual_value = ct.content_typeahead_selected.call(fake_this, item);
    expected_value = ' :octopus: ';
    assert.equal(actual_value, expected_value);

    fake_this.query = '{:octo';
    fake_this.token = 'octo';
    actual_value = ct.content_typeahead_selected.call(fake_this, item);
    expected_value = '{ :octopus: ';
    assert.equal(actual_value, expected_value);

    // mention
    fake_this.completing = 'mention';

    compose.warn_if_mentioning_unsubscribed_user = () => {};

    fake_this.query = '@**Mark Tw';
    fake_this.token = 'Mark Tw';
    actual_value = ct.content_typeahead_selected.call(fake_this, twin1);
    expected_value = '@**Mark Twin|105** ';
    assert.equal(actual_value, expected_value);

    let warned_for_mention = false;
    compose.warn_if_mentioning_unsubscribed_user = (mentioned) => {
        assert.equal(mentioned, othello);
        warned_for_mention = true;
    };

    fake_this.query = '@oth';
    fake_this.token = 'oth';
    actual_value = ct.content_typeahead_selected.call(fake_this, othello);
    expected_value = '@**Othello, the Moor of Venice** ';
    assert.equal(actual_value, expected_value);
    assert(warned_for_mention);

    fake_this.query = 'Hello @oth';
    fake_this.token = 'oth';
    actual_value = ct.content_typeahead_selected.call(fake_this, othello);
    expected_value = 'Hello @**Othello, the Moor of Venice** ';
    assert.equal(actual_value, expected_value);

    fake_this.query = '@**oth';
    fake_this.token = 'oth';
    actual_value = ct.content_typeahead_selected.call(fake_this, othello);
    expected_value = '@**Othello, the Moor of Venice** ';
    assert.equal(actual_value, expected_value);

    fake_this.query = '@*oth';
    fake_this.token = 'oth';
    actual_value = ct.content_typeahead_selected.call(fake_this, othello);
    expected_value = '@**Othello, the Moor of Venice** ';
    assert.equal(actual_value, expected_value);

    // silent mention
    fake_this.completing = 'silent_mention';
    compose.warn_if_mentioning_unsubscribed_user = () => {
        throw Error('unexpected call for silent mentions');
    };

    fake_this.query = '@_kin';
    fake_this.token = 'kin';
    actual_value = ct.content_typeahead_selected.call(fake_this, hamlet);
    expected_value = '@_**King Hamlet** ';
    assert.equal(actual_value, expected_value);

    fake_this.query = 'Hello @_kin';
    fake_this.token = 'kin';
    actual_value = ct.content_typeahead_selected.call(fake_this, hamlet);
    expected_value = 'Hello @_**King Hamlet** ';
    assert.equal(actual_value, expected_value);

    fake_this.query = '@_*kin';
    fake_this.token = 'kin';
    actual_value = ct.content_typeahead_selected.call(fake_this, hamlet);
    expected_value = '@_**King Hamlet** ';
    assert.equal(actual_value, expected_value);

    fake_this.query =  '@_**kin';
    fake_this.token = 'kin';
    actual_value = ct.content_typeahead_selected.call(fake_this, hamlet);
    expected_value = '@_**King Hamlet** ';
    assert.equal(actual_value, expected_value);

    // user group mention
    compose.warn_if_mentioning_unsubscribed_user = () => {
        throw Error('unexpected call for user groups');
    };

    fake_this.query = '@back';
    fake_this.token = 'back';
    actual_value = ct.content_typeahead_selected.call(fake_this, backend);
    expected_value = '@*Backend* ';
    assert.equal(actual_value, expected_value);

    fake_this.query = '@*back';
    fake_this.token = 'back';
    actual_value = ct.content_typeahead_selected.call(fake_this, backend);
    expected_value = '@*Backend* ';
    assert.equal(actual_value, expected_value);

    fake_this.query = '/m';
    fake_this.completing = 'slash';
    actual_value = ct.content_typeahead_selected.call(fake_this, me_slash);
    expected_value = '/me ';
    assert.equal(actual_value, expected_value);

    // stream
    fake_this.completing = 'stream';
    let warned_for_stream_link = false;
    compose.warn_if_private_stream_is_linked = (linked_stream) => {
        assert.equal(linked_stream, sweden_stream);
        warned_for_stream_link = true;
    };

    fake_this.query = '#swed';
    fake_this.token = 'swed';
    actual_value = ct.content_typeahead_selected.call(fake_this, sweden_stream);
    expected_value = '#**Sweden** ';
    assert.equal(actual_value, expected_value);

    fake_this.query = 'Hello #swed';
    fake_this.token = 'swed';
    actual_value = ct.content_typeahead_selected.call(fake_this, sweden_stream);
    expected_value = 'Hello #**Sweden** ';
    assert.equal(actual_value, expected_value);

    fake_this.query = '#**swed';
    fake_this.token = 'swed';
    actual_value = ct.content_typeahead_selected.call(fake_this, sweden_stream);
    expected_value = '#**Sweden** ';
    assert.equal(actual_value, expected_value);

    // syntax
    fake_this.completing = 'syntax';

    fake_this.query = '~~~p';
    fake_this.token = 'p';
    actual_value = ct.content_typeahead_selected.call(fake_this, 'python');
    expected_value = '~~~python\n\n~~~';
    assert.equal(actual_value, expected_value);

    fake_this.query = 'Hello ~~~p';
    fake_this.token = 'p';
    actual_value = ct.content_typeahead_selected.call(fake_this, 'python');
    expected_value = 'Hello ~~~python\n\n~~~';
    assert.equal(actual_value, expected_value);

    fake_this.query = '```p';
    fake_this.token = 'p';
    actual_value = ct.content_typeahead_selected.call(fake_this, 'python');
    expected_value = '```python\n\n```';
    assert.equal(actual_value, expected_value);

    // Test special case to not close code blocks if there is text afterward
    fake_this.query = '```p\nsome existing code';
    fake_this.token = 'p';
    fake_this.$element.caret = function () {
        return 4; // Put cursor right after ```p
    };
    actual_value = ct.content_typeahead_selected.call(fake_this, 'python');
    expected_value = '```python\nsome existing code';
    assert.equal(actual_value, expected_value);

    fake_this.completing = 'something-else';

    fake_this.query = 'foo';
    actual_value = ct.content_typeahead_selected.call(fake_this, {});
    expected_value = fake_this.query;
    assert.equal(actual_value, expected_value);

    assert(caret_called1);
    assert(caret_called2);
    assert(autosize_called);
    assert(set_timeout_called);
    assert(warned_for_stream_link);
});

function sorted_names_from(subs) {
    return subs.map(sub => sub.name).sort();
}

run_test('initialize', () => {
    let expected_value;

    let stream_typeahead_called = false;
    $('#stream_message_recipient_stream').typeahead = function (options) {
        // options.source()
        //
        let actual_value = options.source();
        assert.deepEqual(actual_value.sort(), ['Denmark', 'Sweden']);

        // options.highlighter()
        options.query = 'De';
        actual_value = options.highlighter('Denmark');
        expected_value = '<strong>Denmark</strong>';
        assert.equal(actual_value, expected_value);

        options.query = 'the n';
        actual_value = options.highlighter('The Netherlands');
        expected_value = '<strong>The Netherlands</strong>';
        assert.equal(actual_value, expected_value);

        // options.matcher()
        options.query = 'de';
        assert.equal(options.matcher('Denmark'), true);
        assert.equal(options.matcher('Sweden'), false);

        options.query = 'De';
        assert.equal(options.matcher('Denmark'), true);
        assert.equal(options.matcher('Sweden'), false);

        options.query = 'the ';
        assert.equal(options.matcher('The Netherlands'), true);
        assert.equal(options.matcher('Sweden'), false);

        stream_typeahead_called = true;
    };

    let subject_typeahead_called = false;
    $('#stream_message_recipient_topic').typeahead = function (options) {
        const topics = ['<&>', 'even more ice', 'furniture', 'ice', 'kronor', 'more ice'];
        stream_topic_history.get_recent_topic_names = (stream_id) => {
            assert.equal(stream_id, sweden_stream.stream_id);
            return topics;
        };

        $('#stream_message_recipient_stream').val('Sweden');
        let actual_value = options.source();
        // Topics should be sorted alphabetically, not by addition order.
        let expected_value = topics;
        assert.deepEqual(actual_value, expected_value);

        // options.highlighter()
        options.query = 'Kro';
        actual_value = options.highlighter('kronor');
        expected_value = '<strong>kronor</strong>';
        assert.equal(actual_value, expected_value);

        // Highlighted content should be escaped.
        options.query = '<';
        actual_value = options.highlighter('<&>');
        expected_value = '<strong>&lt;&amp;&gt;</strong>';
        assert.equal(actual_value, expected_value);

        options.query = 'even m';
        actual_value = options.highlighter('even more ice');
        expected_value = '<strong>even more ice</strong>';
        assert.equal(actual_value, expected_value);

        // options.sorter()
        //
        // Notice that alphabetical sorting isn't managed by this sorter,
        // it is a result of the topics already being sorted after adding
        // them with add_topic().
        options.query = 'furniture';
        actual_value = options.sorter(['furniture']);
        expected_value = ['furniture'];
        assert.deepEqual(actual_value, expected_value);

        // A literal match at the beginning of an element puts it at the top.
        options.query = 'ice';
        actual_value = options.sorter(['even more ice', 'ice', 'more ice']);
        expected_value = ['ice', 'even more ice', 'more ice'];
        assert.deepEqual(actual_value, expected_value);

        // The sorter should return the query as the first element if there
        // isn't a topic with such name.
        // This only happens if typeahead is providing other suggestions.
        options.query = 'e';  // Letter present in "furniture" and "ice"
        actual_value = options.sorter(['furniture', 'ice']);
        expected_value = ['e', 'furniture', 'ice'];
        assert.deepEqual(actual_value, expected_value);

        // Don't make any suggestions if this query doesn't match any
        // existing topic.
        options.query = 'non-existing-topic';
        actual_value = options.sorter([]);
        expected_value = [];
        assert.deepEqual(actual_value, expected_value);

        subject_typeahead_called = true;

        // Unset the stream name.
        $('#stream_message_recipient_stream').val('');
    };

    let pm_recipient_typeahead_called = false;
    $('#private_message_recipient').typeahead = function (options) {
        let inserted_users = [];
        user_pill.get_user_ids = function () {
            return inserted_users;
        };

        // This should match the users added at the beginning of this test file.
        let actual_value = options.source('');
        let expected_value = [alice, cordelia, hal, gael, harry,
                              hamlet, lear, twin1, twin2, othello,
                              hamletcharacters, backend, call_center];
        assert.deepEqual(actual_value, expected_value);

        // Even though the items passed to .highlighter() are the full
        // objects of the users matching the query, it only returns the
        // HTML string with the "User_name <email>" format, with the
        // corresponding parts in bold.
        options.query = 'oth';
        actual_value = options.highlighter(othello);
        expected_value = '        <img class="typeahead-image" src="https://secure.gravatar.com/avatar/md5-othello@zulip.com?d&#x3D;identicon&amp;s&#x3D;50" />\n<strong>Othello, the Moor of Venice</strong>';
        assert.equal(actual_value, expected_value);

        options.query = 'Lear';
        actual_value = options.highlighter(cordelia);
        expected_value = '        <img class="typeahead-image" src="https://secure.gravatar.com/avatar/md5-cordelia@zulip.com?d&#x3D;identicon&amp;s&#x3D;50" />\n<strong>Cordelia Lear</strong>';
        assert.equal(actual_value, expected_value);

        options.query = 'othello@zulip.com, co';
        actual_value = options.highlighter(cordelia);
        expected_value = '        <img class="typeahead-image" src="https://secure.gravatar.com/avatar/md5-cordelia@zulip.com?d&#x3D;identicon&amp;s&#x3D;50" />\n<strong>Cordelia Lear</strong>';
        assert.equal(actual_value, expected_value);

        function matcher(query, person) {
            query = typeahead.clean_query_lowercase(query);
            return ct.query_matches_person(query, person);
        }

        let query;
        query = 'el';  // Matches both "othELlo" and "cordELia"
        assert.equal(matcher(query, othello), true);
        assert.equal(matcher(query, cordelia), true);

        query = 'bender';  // Doesn't exist
        assert.equal(matcher(query, othello), false);
        assert.equal(matcher(query, cordelia), false);

        query = 'gael';
        assert.equal(matcher(query, gael), true);

        query = 'Gaël';
        assert.equal(matcher(query, gael), true);

        query = 'gaël';
        assert.equal(matcher(query, gael), true);

        // Don't make suggestions if the last name only has whitespaces
        // (we're between typing names).
        query = 'othello@zulip.com,     ';
        assert.equal(matcher(query, othello), false);
        assert.equal(matcher(query, cordelia), false);

        // query = 'othello@zulip.com,, , cord';
        query = 'cord';
        assert.equal(matcher(query, othello), false);
        assert.equal(matcher(query, cordelia), true);

        // If the user is already in the list, typeahead doesn't include it
        // again.
        query = 'cordelia@zulip.com, cord';
        assert.equal(matcher(query, othello), false);
        assert.equal(matcher(query, cordelia), false);

        query = 'oth';
        page_params.realm_email_address_visibility =
            settings_config.email_address_visibility_values.admins_only.code;
        page_params.is_admin = false;
        assert.equal(matcher(query, deactivated_user), false);

        page_params.is_admin = true;
        assert.equal(matcher(query, deactivated_user), true);

        function sorter(query, people) {
            return typeahead_helper.sort_recipients(
                people,
                query,
                compose_state.stream_name(),
                compose_state.topic()
            );
        }

        // The sorter's output has the items that match the query from the
        // beginning first, and then the rest of them in REVERSE order of
        // the input.
        query = 'othello';
        actual_value = sorter(query, [othello]);
        expected_value = [othello];
        assert.deepEqual(actual_value, expected_value);

        // A literal match at the beginning of an element puts it at the top.
        query = 'co';  // Matches everything ("x@zulip.COm")
        actual_value = sorter(query, [othello, deactivated_user, cordelia]);
        expected_value = [cordelia, deactivated_user, othello];
        assert.deepEqual(actual_value, expected_value);

        query = 'non-existing-user';
        actual_value = sorter(query, []);
        expected_value = [];
        assert.deepEqual(actual_value, expected_value);

        // Adds a `no break-space` at the end. This should fail
        // if there wasn't any logic replacing `no break-space`
        // with normal space.
        query = 'cordelia' + String.fromCharCode(160);
        assert.equal(matcher(query, cordelia), true);
        assert.equal(matcher(query, othello), false);

        const event = {
            target: '#doesnotmatter',
        };

        let appended_name;
        compose_pm_pill.set_from_typeahead = function (item) {
            appended_name = item.full_name;
        };

        // options.updater()
        options.query = 'othello';
        options.updater(othello, event);
        assert.equal(appended_name, 'Othello, the Moor of Venice');

        options.query = 'othello@zulip.com, cor';
        actual_value = options.updater(cordelia, event);
        assert.equal(appended_name, 'Cordelia Lear');

        const click_event = { type: 'click', target: '#doesnotmatter' };
        options.query = 'othello';
        // Focus lost (caused by the click event in the typeahead list)
        $('#private_message_recipient').blur();
        actual_value = options.updater(othello, click_event);
        assert.equal(appended_name, 'Othello, the Moor of Venice');

        let appended_names = [];
        people.get_by_user_id = function (user_id) {
            const users = {100: hamlet, 104: lear};
            return users[user_id];
        };
        people.my_current_email = function () {
            return 'hamlet@zulip.com';
        };
        compose_pm_pill.set_from_typeahead = function (item) {
            appended_names.push(item.full_name);
        };

        let cleared = false;
        function fake_clear() {
            cleared = true;
        }
        compose_pm_pill.widget = {clear_text: fake_clear};

        options.query = 'hamletchar';
        options.updater(hamletcharacters, event);
        assert.deepEqual(appended_names, ['King Lear']);
        assert(cleared);

        inserted_users = [lear.user_id];
        appended_names = [];
        cleared = false;
        options.updater(hamletcharacters, event);
        assert.deepEqual(appended_names, []);
        assert(cleared);

        pm_recipient_typeahead_called = true;
    };

    let compose_textarea_typeahead_called = false;
    $('#compose-textarea').typeahead = function (options) {
        // options.source()
        //
        // For now we only test that get_sorted_filtered_items has been
        // properly set as the .source(). All its features are tested later on
        // in test_begins_typeahead().
        let fake_this = {
            $element: {},
        };
        let caret_called = false;
        fake_this.$element.caret = function () {
            caret_called = true;
            return 7;
        };
        fake_this.$element.closest = () => [];
        fake_this.options = options;
        let actual_value = options.source.call(fake_this, 'test #s');
        assert.deepEqual(
            sorted_names_from(actual_value),
            ['Denmark', 'Sweden', 'The Netherlands']
        );
        assert(caret_called);

        // options.highlighter()
        //
        // Again, here we only verify that the highlighter has been set to
        // content_highlighter.
        fake_this = { completing: 'mention', token: 'othello' };
        actual_value = options.highlighter.call(fake_this, othello);
        expected_value = '        <img class="typeahead-image" src="https://secure.gravatar.com/avatar/md5-othello@zulip.com?d&#x3D;identicon&amp;s&#x3D;50" />\n<strong>Othello, the Moor of Venice</strong>';
        assert.equal(actual_value, expected_value);

        fake_this = { completing: 'mention', token: 'hamletcharacters' };
        actual_value = options.highlighter.call(fake_this, hamletcharacters);
        expected_value = '        <i class="typeahead-image icon fa fa-group" aria-hidden="true"></i>\n<strong>hamletcharacters</strong>&nbsp;&nbsp;\n<small class="autocomplete_secondary">Characters of Hamlet</small>\n';
        assert.equal(actual_value, expected_value);

        // matching

        function match(fake_this, item) {
            const token = fake_this.token;
            const completing = fake_this.completing;

            return ct.compose_content_matcher(completing, token)(item);
        }

        fake_this = { completing: 'emoji', token: 'ta' };
        assert.equal(match(fake_this, make_emoji(emoji_tada)), true);
        assert.equal(match(fake_this, make_emoji(emoji_moneybag)), false);

        fake_this = { completing: 'stream', token: 'swed' };
        assert.equal(match(fake_this, sweden_stream), true);
        assert.equal(match(fake_this, denmark_stream), false);

        fake_this = { completing: 'syntax', token: 'py' };
        assert.equal(match(fake_this, 'python'), true);
        assert.equal(match(fake_this, 'javascript'), false);

        fake_this = { completing: 'non-existing-completion' };
        assert.equal(match(fake_this), undefined);

        function sort_items(fake_this, item) {
            const token = fake_this.token;
            const completing = fake_this.completing;

            return ct.sort_results(completing, item, token);
        }

        // options.sorter()
        fake_this = { completing: 'emoji', token: 'ta' };
        actual_value = sort_items(fake_this, [make_emoji(emoji_stadium),
                                              make_emoji(emoji_tada)]);
        expected_value = [make_emoji(emoji_tada), make_emoji(emoji_stadium)];
        assert.deepEqual(actual_value, expected_value);

        fake_this = { completing: 'emoji', token: 'th' };
        actual_value = sort_items(fake_this, [make_emoji(emoji_thermometer),
                                              make_emoji(emoji_thumbs_up)]);
        expected_value = [make_emoji(emoji_thumbs_up), make_emoji(emoji_thermometer)];
        assert.deepEqual(actual_value, expected_value);

        fake_this = { completing: 'emoji', token: 'he' };
        actual_value = sort_items(fake_this, [make_emoji(emoji_headphones),
                                              make_emoji(emoji_heart)]);
        expected_value = [make_emoji(emoji_heart), make_emoji(emoji_headphones)];
        assert.deepEqual(actual_value, expected_value);

        fake_this = { completing: 'slash', token: 'm' };
        actual_value = sort_items(fake_this, [my_slash, me_slash]);
        expected_value = [me_slash, my_slash];
        assert.deepEqual(actual_value, expected_value);

        fake_this = { completing: 'stream', token: 'de' };
        actual_value = sort_items(fake_this, [sweden_stream, denmark_stream]);
        expected_value = [denmark_stream, sweden_stream];
        assert.deepEqual(actual_value, expected_value);

        // Matches in the descriptions affect the order as well.
        // Testing "co" for "cold", in both streams' description. It's at the
        // beginning of Sweden's description, so that one should go first.
        fake_this = { completing: 'stream', token: 'co' };
        actual_value = sort_items(fake_this, [denmark_stream, sweden_stream]);
        expected_value = [sweden_stream, denmark_stream];
        assert.deepEqual(actual_value, expected_value);

        fake_this = { completing: 'syntax', token: 'ap' };
        actual_value = sort_items(fake_this, ['abap', 'applescript']);
        expected_value = ['applescript', 'abap'];
        assert.deepEqual(actual_value, expected_value);

        const serbia_stream = {
            name: 'Serbia',
            description: 'Snow and cold',
            stream_id: 3,
            subscribed: false,
        };
        // Subscribed stream is active
        stream_data.is_active = function () {
            return false;
        };
        fake_this = { completing: 'stream', token: 's' };
        actual_value = sort_items(fake_this, [sweden_stream, serbia_stream]);
        expected_value = [sweden_stream, serbia_stream];
        assert.deepEqual(actual_value, expected_value);
        // Subscribed stream is inactive
        stream_data.is_active = function () {
            return true;
        };
        actual_value = sort_items(fake_this, [sweden_stream, serbia_stream]);
        expected_value = [sweden_stream, serbia_stream];
        assert.deepEqual(actual_value, expected_value);

        fake_this = { completing: 'stream', token: 'ser' };
        actual_value = sort_items(fake_this, [denmark_stream, serbia_stream]);
        expected_value = [serbia_stream, denmark_stream];
        assert.deepEqual(actual_value, expected_value);

        fake_this = { completing: 'non-existing-completion' };
        assert.equal(sort_items(fake_this), undefined);

        compose_textarea_typeahead_called = true;
    };

    let pm_recipient_blur_called = false;
    const old_pm_recipient_blur = $('#private_message_recipient').blur;
    $('#private_message_recipient').blur = function (handler) {
        if (handler) {  // The blur handler is being set.
            this.val('othello@zulip.com, ');
            handler.call(this);
            const actual_value = this.val();
            const expected_value = 'othello@zulip.com';
            assert.equal(actual_value, expected_value);
        } else {  // The element is simply losing the focus.
            old_pm_recipient_blur();
        }
        pm_recipient_blur_called = true;
    };

    page_params.enter_sends = false;
    // We manually specify it the first time because the click_func
    // doesn't exist yet.
    $("#stream_message_recipient_stream").select(noop);
    $("#stream_message_recipient_topic").select(noop);
    $("#private_message_recipient").select(noop);

    ct.initialize();

    // handle_keydown()
    let event = {
        keyCode: 13,
        target: {
            id: 'stream_message_recipient_stream',
        },
        preventDefault: noop,
    };

    $('#stream_message_recipient_topic').data = function () {
        return { typeahead: { shown: true }};
    };
    $('form#send_message_form').keydown(event);

    const stub_typeahead_hidden = function () {
        return { typeahead: { shown: false }};
    };
    $('#stream_message_recipient_topic').data = stub_typeahead_hidden;
    $('#stream_message_recipient_stream').data = stub_typeahead_hidden;
    $('#private_message_recipient').data = stub_typeahead_hidden;
    $('#compose-textarea').data = stub_typeahead_hidden;
    $('form#send_message_form').keydown(event);

    event.keyCode = undefined;
    event.which = 9;
    event.shiftKey = false;
    event.target.id = 'subject';
    $('form#send_message_form').keydown(event);
    event.target.id = 'compose-textarea';
    $('form#send_message_form').keydown(event);
    event.target.id = 'some_non_existing_id';
    $('form#send_message_form').keydown(event);

    // Setup jquery functions used in compose_textarea enter
    // handler.
    let range_length = 0;
    $('#compose-textarea').range = function () {
        return {
            length: range_length,
            range: noop,
            start: 0,
            end: 0 + range_length,
        };
    };
    $('#compose-textarea').caret = noop;

    event.keyCode = 13;
    event.target.id = 'stream_message_recipient_topic';
    $('form#send_message_form').keydown(event);
    event.target.id = 'compose-textarea';
    page_params.enter_sends = false;
    event.metaKey = true;
    let compose_finish_called = false;
    compose.finish = function () {
        compose_finish_called = true;
    };

    $('form#send_message_form').keydown(event);
    assert(compose_finish_called);
    event.metaKey = false;
    event.ctrlKey = true;
    $('form#send_message_form').keydown(event);
    page_params.enter_sends = true;
    event.ctrlKey = false;
    event.altKey = true;
    $('form#send_message_form').keydown(event);

    // Cover case where there's a least one character there.
    range_length = 2;
    $('form#send_message_form').keydown(event);

    event.altKey = false;
    event.metaKey = true;
    $('form#send_message_form').keydown(event);
    event.target.id = 'private_message_recipient';
    $('form#send_message_form').keydown(event);

    event.keyCode = 42;
    $('form#send_message_form').keydown(event);

    // handle_keyup()
    event = {
        keyCode: 13,
        target: {
            id: 'stream_message_recipient_stream',
        },
        preventDefault: noop,
    };
    // We execute .keydown() in order to make nextFocus !== false
    $('#stream_message_recipient_topic').data = function () {
        return { typeahead: { shown: true }};
    };
    $('form#send_message_form').keydown(event);
    $('form#send_message_form').keyup(event);
    event.keyCode = undefined;
    event.which = 9;
    event.shiftKey = false;
    $('form#send_message_form').keyup(event);
    event.keyCode = 42;
    $('form#send_message_form').keyup(event);

    // select_on_focus()
    let focus_handler_called = false;
    let stream_one_called = false;
    $('#stream_message_recipient_stream').focus = function (f) {
        // This .one() function emulates the possible infinite recursion that
        // in_handler tries to avoid.
        $('#stream_message_recipient_stream').one = function (event, handler) {
            handler({ preventDefault: noop });
            f();  // This time in_handler will already be true.
            stream_one_called = true;
        };
        f();  // Here in_handler is false.
        focus_handler_called = true;
    };

    $("#compose-send-button").fadeOut = noop;
    $("#compose-send-button").fadeIn = noop;
    let channel_post_called = false;
    global.channel.post = function (params) {
        assert.equal(params.url, '/json/users/me/enter-sends');
        assert.equal(params.idempotent, true);
        assert.deepEqual(params.data, {enter_sends: page_params.enter_sends});

        channel_post_called = true;
    };
    $('#enter_sends').is = function () { return false; };
    $('#enter_sends').click();

    // Now we re-run both .initialize() and the click handler, this time
    // with enter_sends: page_params.enter_sends being true
    $('#enter_sends').is = function () { return true; };
    $('#enter_sends').click();
    ct.initialize();

    // Now let's make sure that all the stub functions have been called
    // during the initialization.
    assert(stream_typeahead_called);
    assert(subject_typeahead_called);
    assert(pm_recipient_typeahead_called);
    assert(pm_recipient_blur_called);
    assert(channel_post_called);
    assert(compose_textarea_typeahead_called);
    assert(focus_handler_called);
    assert(stream_one_called);
});

run_test('begins_typeahead', () => {

    const begin_typehead_this = {options: {completions: {
        emoji: true,
        mention: true,
        silent_mention: true,
        slash: true,
        stream: true,
        syntax: true,
        topic: true,
        timestamp: true,
    }}};

    function get_values(input, rest) {
        // Stub out split_at_cursor that uses $(':focus')
        ct.split_at_cursor = function () {
            return [input, rest];
        };
        const values = ct.get_candidates.call(
            begin_typehead_this, input
        );
        return values;
    }

    function assert_typeahead_equals(input, rest, reference) {
        // Usage:
        // assert_typeahead_equals('#some', reference); => '#some|'
        // assert_typeahead_equals('#some', 'thing', reference) => '#some|thing'
        // In the above examples, '|' serves as the cursor.
        if (reference === undefined) {
            reference = rest;
            rest = '';
        }
        const values = get_values(input, rest);
        assert.deepEqual(values, reference);
    }

    function assert_stream_list(input, rest) {
        if (rest === undefined) {
            rest = '';
        }
        const values = get_values(input, rest);
        assert.deepEqual(
            sorted_names_from(values),
            ['Denmark', 'Sweden', 'The Netherlands']
        );
    }

    const people_only = {is_silent: true};
    const all_mentions = {is_silent: false};
    const lang_list = Object.keys(pygments_data.langs);

    assert_typeahead_equals("test", false);
    assert_typeahead_equals("test one two", false);
    assert_typeahead_equals("*", false);
    assert_typeahead_equals("* ", false);
    assert_typeahead_equals(" *", false);
    assert_typeahead_equals("test *", false);

    // Make sure that the last token is the one we read.
    assert_typeahead_equals("~~~ @zulip", all_mentions);
    assert_typeahead_equals("@zulip :ta", emoji_list);
    assert_stream_list(":tada: #foo");
    assert_typeahead_equals("#foo\n~~~py", lang_list);

    assert_typeahead_equals("@", false);
    assert_typeahead_equals("@_", false);
    assert_typeahead_equals(" @", false);
    assert_typeahead_equals(" @_", false);
    assert_typeahead_equals("test @**o", all_mentions);
    assert_typeahead_equals("test @_**o", people_only);
    assert_typeahead_equals("test @*o", all_mentions);
    assert_typeahead_equals("test @_*k", people_only);
    assert_typeahead_equals("test @*h", all_mentions);
    assert_typeahead_equals("test @_*h", people_only);
    assert_typeahead_equals("test @", false);
    assert_typeahead_equals("test @_", false);
    assert_typeahead_equals("test no@o", false);
    assert_typeahead_equals("test no@_k", false);
    assert_typeahead_equals("@ ", false);
    assert_typeahead_equals("@_ ", false);
    assert_typeahead_equals("@* ", false);
    assert_typeahead_equals("@_* ", false);
    assert_typeahead_equals("@** ", false);
    assert_typeahead_equals("@_** ", false);
    assert_typeahead_equals("test\n@i", all_mentions);
    assert_typeahead_equals("test\n@_i", people_only);
    assert_typeahead_equals("test\n @l", all_mentions);
    assert_typeahead_equals("test\n @_l", people_only);
    assert_typeahead_equals("@zuli", all_mentions);
    assert_typeahead_equals("@_zuli", people_only);
    assert_typeahead_equals("@ zuli", false);
    assert_typeahead_equals("@_ zuli", false);
    assert_typeahead_equals(" @zuli", all_mentions);
    assert_typeahead_equals(" @_zuli", people_only);
    assert_typeahead_equals("test @o", all_mentions);
    assert_typeahead_equals("test @_o", people_only);
    assert_typeahead_equals("test @z", all_mentions);
    assert_typeahead_equals("test @_z", people_only);

    assert_typeahead_equals(":", false);
    assert_typeahead_equals(": ", false);
    assert_typeahead_equals(" :", false);
    assert_typeahead_equals(":)", false);
    assert_typeahead_equals(":4", false);
    assert_typeahead_equals(": la", false);
    assert_typeahead_equals("test :-P", false);
    assert_typeahead_equals("hi emoji :", false);
    assert_typeahead_equals("hi emoj:i", false);
    assert_typeahead_equals("hi emoji :D", false);
    assert_typeahead_equals("hi emoji : t", false);
    assert_typeahead_equals("hi emoji :t", emoji_list);
    assert_typeahead_equals("hi emoji :ta", emoji_list);
    assert_typeahead_equals("hi emoji :da", emoji_list);
    assert_typeahead_equals("hi emoji :da_", emoji_list);
    assert_typeahead_equals("hi emoji :da ", emoji_list);
    assert_typeahead_equals("hi emoji\n:da", emoji_list);
    assert_typeahead_equals("hi emoji\n :ra", emoji_list);
    assert_typeahead_equals(":+", emoji_list);
    assert_typeahead_equals(":la", emoji_list);
    assert_typeahead_equals(" :lee", emoji_list);
    assert_typeahead_equals("hi :see no", emoji_list);
    assert_typeahead_equals("hi :japanese post of", emoji_list);

    assert_typeahead_equals("#", false);
    assert_typeahead_equals("# ", false);
    assert_typeahead_equals(" #", false);
    assert_typeahead_equals("# s", false);
    assert_typeahead_equals("test #", false);
    assert_typeahead_equals("test # a", false);
    assert_typeahead_equals("test no#o", false);
    assert_stream_list("#s");
    assert_stream_list(" #s");
    assert_stream_list("test #D");
    assert_stream_list("test #**v");

    assert_typeahead_equals("/", composebox_typeahead.slash_commands);
    assert_typeahead_equals("/m", composebox_typeahead.slash_commands);
    assert_typeahead_equals(" /m", false);
    assert_typeahead_equals("abc/me", false);
    assert_typeahead_equals("hello /me", false);
    assert_typeahead_equals("\n/m", false);
    assert_typeahead_equals("/poll", composebox_typeahead.slash_commands);
    assert_typeahead_equals(" /pol", false);
    assert_typeahead_equals("abc/po", false);
    assert_typeahead_equals("hello /poll", false);
    assert_typeahead_equals("\n/pol", false);

    assert_typeahead_equals("x/", false);
    assert_typeahead_equals("```", false);
    assert_typeahead_equals("``` ", false);
    assert_typeahead_equals(" ```", false);
    assert_typeahead_equals("test ```", false);
    assert_typeahead_equals("test ``` py", false);
    assert_typeahead_equals("test ```a", false);
    assert_typeahead_equals("test\n```", false);
    assert_typeahead_equals("``c", false);
    assert_typeahead_equals("```b", lang_list);
    assert_typeahead_equals("``` d", lang_list);
    assert_typeahead_equals("test\n``` p", lang_list);
    assert_typeahead_equals("test\n```  p", lang_list);
    assert_typeahead_equals("~~~", false);
    assert_typeahead_equals("~~~ ", false);
    assert_typeahead_equals(" ~~~", false);
    assert_typeahead_equals(" ~~~ g", false);
    assert_typeahead_equals("test ~~~", false);
    assert_typeahead_equals("test ~~~p", false);
    assert_typeahead_equals("test\n~~~", false);
    assert_typeahead_equals("~~~e", lang_list);
    assert_typeahead_equals("~~~ f", lang_list);
    assert_typeahead_equals("test\n~~~ p", lang_list);
    assert_typeahead_equals("test\n~~~  p", lang_list);

    // topic_jump
    assert_typeahead_equals("@**a person**>", false);
    assert_typeahead_equals("@**a person** >", false);
    assert_typeahead_equals("#**stream**>", ['']); // this is deliberately a blank choice.
    assert_typeahead_equals("#**stream** >", ['']);
    assert_typeahead_equals("#**Sweden>some topic** >", false); // Already completed a topic.

    // topic_list
    // includes "more ice"
    const sweden_topics_to_show = stream_topic_history.get_recent_topic_names(1);
    assert_typeahead_equals("#**Sweden>more ice", sweden_topics_to_show);
    sweden_topics_to_show.push('totally new topic');
    assert_typeahead_equals("#**Sweden>totally new topic", sweden_topics_to_show);

    // time_jump
    assert_typeahead_equals("!tim", false);
    assert_typeahead_equals("!timerandom", false);
    assert_typeahead_equals("!time", ['translated: Mention a timezone-aware time']);
    assert_typeahead_equals("!time(", ['translated: Mention a timezone-aware time']);
    assert_typeahead_equals("!time(something", ['translated: Mention a timezone-aware time']);
    assert_typeahead_equals("!time(something", ") ", ['translated: Mention a timezone-aware time']);
    assert_typeahead_equals("!time(something)", false);
    assert_typeahead_equals("!time(something) ", false); // Already completed the mention

    // Following tests place the cursor before the second string
    assert_typeahead_equals("#test", "ing", false);
    assert_typeahead_equals("@test", "ing", false);
    assert_typeahead_equals(":test", "ing", false);
    assert_typeahead_equals("```test", "ing", false);
    assert_typeahead_equals("~~~test", "ing", false);
    const terminal_symbols = ',.;?!()[] "\'\n\t';
    terminal_symbols.split().forEach(symbol => {
        assert_stream_list("#test", symbol);
        assert_typeahead_equals("@test", symbol, all_mentions);
        assert_typeahead_equals(":test", symbol, emoji_list);
        assert_typeahead_equals("```test", symbol, lang_list);
        assert_typeahead_equals("~~~test", symbol, lang_list);
    });
});

run_test('tokenizing', () => {
    assert.equal(ct.tokenize_compose_str("/m"), "/m");
    assert.equal(ct.tokenize_compose_str("1/3"), "");
    assert.equal(ct.tokenize_compose_str("foo bar"), "");
    assert.equal(ct.tokenize_compose_str("foo#@:bar"), "");
    assert.equal(ct.tokenize_compose_str("foo bar [#alic"), "#alic");
    assert.equal(ct.tokenize_compose_str("#foo @bar [#alic"), "#alic");
    assert.equal(ct.tokenize_compose_str("foo bar #alic"), "#alic");
    assert.equal(ct.tokenize_compose_str("foo bar @alic"), "@alic");
    assert.equal(ct.tokenize_compose_str("foo bar :smil"), ":smil");
    assert.equal(ct.tokenize_compose_str(":smil"), ":smil");
    assert.equal(ct.tokenize_compose_str("foo @alice sm"), "@alice sm");
    assert.equal(ct.tokenize_compose_str("foo ```p"), "");
    assert.equal(ct.tokenize_compose_str("``` py"), "``` py");
    assert.equal(ct.tokenize_compose_str("foo``bar ~~~ py"), "");
    assert.equal(ct.tokenize_compose_str("foo ~~~why = why_not\n~~~"), "~~~");

    // The following cases are kinda judgment calls...
    assert.equal(ct.tokenize_compose_str(
        "foo @toomanycharactersisridiculoustocomplete"), "");
    assert.equal(ct.tokenize_compose_str("foo #streams@foo"), "#streams@foo");
});

run_test('content_highlighter', () => {
    let fake_this = { completing: 'emoji' };
    const emoji = { emoji_name: 'person shrugging', emoji_url: '¯\_(ツ)_/¯' };
    let th_render_typeahead_item_called = false;
    typeahead_helper.render_emoji = function (item) {
        assert.deepEqual(item, emoji);
        th_render_typeahead_item_called = true;
    };
    ct.content_highlighter.call(fake_this, emoji);

    fake_this = { completing: 'mention' };
    let th_render_person_called = false;
    typeahead_helper.render_person = function (person) {
        assert.deepEqual(person, othello);
        th_render_person_called = true;
    };
    ct.content_highlighter.call(fake_this, othello);

    let th_render_user_group_called = false;
    typeahead_helper.render_user_group = function (user_group) {
        assert.deepEqual(user_group, backend);
        th_render_user_group_called = true;
    };
    ct.content_highlighter.call(fake_this, backend);

    // We don't have any fancy rendering for slash commands yet.
    fake_this = { completing: 'slash' };
    let th_render_slash_command_called = false;
    const me_slash = {
        text: "/me is excited (Display action text)",
    };
    typeahead_helper.render_typeahead_item = function (item) {
        assert.deepEqual(item, {
            primary: "/me is excited (Display action text)",
        });
        th_render_slash_command_called = true;
    };
    ct.content_highlighter.call(fake_this, me_slash);

    fake_this = { completing: 'stream' };
    let th_render_stream_called = false;
    typeahead_helper.render_stream = function (stream) {
        assert.deepEqual(stream, denmark_stream);
        th_render_stream_called = true;
    };
    ct.content_highlighter.call(fake_this, denmark_stream);

    fake_this = { completing: 'syntax' };
    th_render_typeahead_item_called = false;
    typeahead_helper.render_typeahead_item = function (item) {
        assert.deepEqual(item, { primary: 'py' });
        th_render_typeahead_item_called = true;
    };
    ct.content_highlighter.call(fake_this, 'py');

    fake_this = { completing: 'something-else' };
    assert(!ct.content_highlighter.call(fake_this));

    // Verify that all stub functions have been called.
    assert(th_render_typeahead_item_called);
    assert(th_render_person_called);
    assert(th_render_user_group_called);
    assert(th_render_stream_called);
    assert(th_render_typeahead_item_called);
    assert(th_render_slash_command_called);
});

run_test('filter_and_sort_mentions (normal)', () => {
    const is_silent = false;

    const suggestions = ct.filter_and_sort_mentions(
        is_silent, 'al');

    assert.deepEqual(suggestions, [
        mention_all,
        alice,
        hal,
        call_center,
    ]);
});

run_test('filter_and_sort_mentions (silent)', () => {
    const is_silent = true;

    const suggestions = ct.filter_and_sort_mentions(
        is_silent, 'al');

    assert.deepEqual(suggestions, [alice, hal]);
});

run_test('typeahead_results', () => {
    const stream_list = [denmark_stream, sweden_stream, netherland_stream];

    function compose_typeahead_results(completing, items, token) {
        return ct.filter_and_sort_candidates(completing, items, token);
    }

    function assert_emoji_matches(input, expected) {
        const returned = compose_typeahead_results('emoji', emoji_list, input);
        assert.deepEqual(returned, expected);
    }
    function assert_mentions_matches(input, expected) {
        const is_silent = false;
        const returned = ct.filter_and_sort_mentions(is_silent, input);
        assert.deepEqual(returned, expected);
    }
    function assert_stream_matches(input, expected) {
        const returned = compose_typeahead_results('stream', stream_list, input);
        assert.deepEqual(returned, expected);
    }

    function assert_slash_matches(input, expected) {
        const returned = compose_typeahead_results('slash', composebox_typeahead.slash_commands, input);
        assert.deepEqual(returned, expected);
    }
    assert_emoji_matches('da', [{emoji_name: "tada", emoji_code: "1f389"},
                                {emoji_name: "panda_face", emoji_code: "1f43c"}]);
    assert_emoji_matches('da_', []);
    assert_emoji_matches('da ', []);
    assert_emoji_matches('panda ', [{emoji_name: "panda_face", emoji_code: "1f43c"}]);
    assert_emoji_matches('panda_', [{emoji_name: "panda_face", emoji_code: "1f43c"}]);
    assert_emoji_matches('japanese_post_', [{emoji_name: "japanese_post_office", emoji_code: "1f3e3"}]);
    assert_emoji_matches('japanese post ', [{emoji_name: "japanese_post_office", emoji_code: "1f3e3"}]);
    assert_emoji_matches('notaemoji', []);
    // Autocomplete user mentions by user name.
    assert_mentions_matches('cordelia', [cordelia]);
    assert_mentions_matches('cordelia le', [cordelia]);
    assert_mentions_matches('cordelia le ', []);
    assert_mentions_matches('King ', [hamlet, lear]);
    assert_mentions_matches('King H', [hamlet]);
    assert_mentions_matches('King L', [lear]);
    assert_mentions_matches('delia lear', []);
    assert_mentions_matches('Mark Tw', [twin1, twin2]);
    // Autocomplete user group mentions by group name.
    assert_mentions_matches('hamletchar', [hamletcharacters]);
    // Autocomplete user group mentions by group descriptions.
    assert_mentions_matches('characters ', [hamletcharacters]);
    assert_mentions_matches('characters of ', [hamletcharacters]);
    assert_mentions_matches('characters o ', []);
    assert_mentions_matches('haracters of hamlet', []);
    assert_mentions_matches('of hamlet', []);

    // Autocomplete by slash commands.
    assert_slash_matches('me', [me_slash]);

    // Autocomplete stream by stream name or stream description.
    assert_stream_matches('den', [denmark_stream, sweden_stream]);
    assert_stream_matches('denmark', [denmark_stream]);
    assert_stream_matches('denmark ', []);
    assert_stream_matches('den ', []);
    assert_stream_matches('cold', [sweden_stream, denmark_stream]);
    assert_stream_matches('the ', [netherland_stream]);
    assert_stream_matches('city', [netherland_stream]);
});

run_test('message people', () => {
    let results;

    compose_state.stream_name = () => undefined;
    ct.max_num_items = 2;

    /*
        We will simulate that we talk to Hal and Harry,
        while we don't talk to King Hamlet.  This will
        knock King Hamlet out of consideration in the
        filtering pass.  Then Hal will be truncated in
        the sorting step.
    */

    message_store.user_ids = () => [hal.user_id, harry.user_id];

    const opts = {
        want_broadcast: false,
        want_groups: true,
        filter_pills: false,
    };

    results = ct.get_person_suggestions('Ha', opts);
    assert.deepEqual(results, [harry, hamletcharacters]);

    // Now let's exclude Hal.
    message_store.user_ids = () => [hamlet.user_id, harry.user_id];

    results = ct.get_person_suggestions('Ha', opts);
    assert.deepEqual(results, [harry, hamletcharacters]);

    message_store.user_ids = () => [hamlet.user_id, harry.user_id, hal.user_id];

    results = ct.get_person_suggestions('Ha', opts);
    assert.deepEqual(results, [harry, hamletcharacters]);

    people.deactivate(harry);
    results = ct.get_person_suggestions('Ha', opts);
    // harry is excluded since it has been deactivated.
    assert.deepEqual(results, [hamletcharacters, hal]);
});
