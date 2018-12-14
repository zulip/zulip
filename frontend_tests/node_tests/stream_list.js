set_global('document', 'document-stub');
set_global('$', global.make_zjquery());

set_global('templates', {});

zrequire('unread_ui');
zrequire('Filter', 'js/filter');
zrequire('util');
zrequire('topic_data');
zrequire('stream_sort');
zrequire('colorspace');
zrequire('stream_color');
zrequire('hash_util');
zrequire('unread');
zrequire('stream_data');
zrequire('scroll_util');
zrequire('list_cursor');
zrequire('stream_list');
zrequire('topic_zoom');

stream_color.initialize();

var noop = function () {};
var return_false = function () { return false; };
var return_true = function () { return true; };

set_global('topic_list', {});
set_global('overlays', {});
set_global('popovers', {});

set_global('keydown_util', {
    handle: noop,
});

run_test('create_sidebar_row', () => {
    // Make a couple calls to create_sidebar_row() and make sure they
    // generate the right markup as well as play nice with get_stream_li().

    var devel = {
        name: 'devel',
        stream_id: 100,
        color: 'blue',
        subscribed: true,
        pin_to_top: true,
    };
    global.stream_data.add_sub('devel', devel);

    var social = {
        name: 'social',
        stream_id: 200,
        color: 'green',
        subscribed: true,
    };
    global.stream_data.add_sub('social', social);

    global.unread.num_unread_for_stream = function () {
        return 42;
    };

    (function create_devel_sidebar_row() {
        var devel_value = $.create('devel-value');
        var devel_count = $.create('devel-count');

        var sidebar_row = $('<devel sidebar row>');

        sidebar_row.set_find_results('.count', devel_count);
        devel_count.set_find_results('.value', devel_value);
        devel_count.set_parent(sidebar_row);

        global.templates.render = function (template_name, data) {
            assert.equal(template_name, 'stream_sidebar_row');
            assert.equal(data.uri, '#narrow/stream/100-devel');
            return '<devel sidebar row>';
        };

        stream_list.create_sidebar_row(devel);
        assert.equal(devel_value.text(), '42');
    }());

    (function create_social_sidebar_row() {
        var social_value = $.create('social-value');
        var social_count = $.create('social-count');
        var sidebar_row = $('<social sidebar row>');

        sidebar_row.set_find_results('.count', social_count);
        social_count.set_find_results('.value', social_value);
        social_count.set_parent(sidebar_row);

        global.templates.render = function (template_name, data) {
            assert.equal(template_name, 'stream_sidebar_row');
            assert.equal(data.uri, '#narrow/stream/200-social');
            return '<social sidebar row>';
        };

        stream_list.create_sidebar_row(social);
        assert.equal(social_value.text(), '42');
    }());

    var split = '<hr class="stream-split">';
    var devel_sidebar = $('<devel sidebar row>');
    var social_sidebar = $('<social sidebar row>');

    var appended_elems;
    $('#stream_filters').append = function (elems) {
        appended_elems = elems;
    };

    stream_list.build_stream_list();

    var expected_elems = [
        devel_sidebar,          //pinned
        split,                  //separator
        social_sidebar,         //not pinned
    ];

    assert.deepEqual(appended_elems, expected_elems);

    var social_li = $('<social sidebar row>');
    var stream_id = social.stream_id;

    var privacy_elem = $.create('privacy-stub');
    social_li.set_find_results('.stream-privacy', privacy_elem);

    social.invite_only = true;
    social.color = '#222222';
    global.templates.render = function (template_name, data) {
        assert.equal(template_name, 'stream_privacy');
        assert.equal(data.invite_only, true);
        assert.equal(data.dark_background, 'dark_background');
        return '<div>privacy-html';
    };
    stream_list.redraw_stream_privacy(social);
    assert.equal(privacy_elem.html(), '<div>privacy-html');

    stream_list.set_in_home_view(stream_id, false);
    assert(social_li.hasClass('out_of_home_view'));

    stream_list.set_in_home_view(stream_id, true);
    assert(!social_li.hasClass('out_of_home_view'));

    var row = stream_list.stream_sidebar.get_row(stream_id);
    stream_data.is_active = return_true;
    row.update_whether_active();
    assert(!social_li.hasClass('inactive_stream'));

    stream_data.is_active = return_false;
    row.update_whether_active();
    assert(social_li.hasClass('inactive_stream'));

    var removed;
    social_li.remove = function () {
        removed = true;
    };

    row.remove();
    assert(removed);
});

set_global('$', global.make_zjquery());

function add_row(sub) {
    global.stream_data.add_sub(sub.name, sub);
    var row = {
        update_whether_active: function () {},
        get_li: function () {
            var html = '<' + sub.name + ' sidebar row html>';
            var obj = $(html);

            obj.length = 1;  // bypass blueslip error

            return obj;
        },
    };
    stream_list.stream_sidebar.set_row(sub.stream_id, row);
}

function initialize_stream_data() {
    stream_data.clear_subscriptions();

    // pinned streams
    var develSub = {
        name: 'devel',
        stream_id: 1000,
        color: 'blue',
        pin_to_top: true,
        subscribed: true,
    };
    add_row(develSub);

    var RomeSub = {
        name: 'Rome',
        stream_id: 2000,
        color: 'blue',
        pin_to_top: true,
        subscribed: true,
    };
    add_row(RomeSub);

    var testSub = {
        name: 'test',
        stream_id: 3000,
        color: 'blue',
        pin_to_top: true,
        subscribed: true,
    };
    add_row(testSub);

    // unpinned streams
    var announceSub = {
        name: 'announce',
        stream_id: 4000,
        color: 'green',
        pin_to_top: false,
        subscribed: true,
    };
    add_row(announceSub);

    var DenmarkSub = {
        name: 'Denmark',
        stream_id: 5000,
        color: 'green',
        pin_to_top: false,
        subscribed: true,
    };
    add_row(DenmarkSub);

    var carSub = {
        name: 'cars',
        stream_id: 6000,
        color: 'green',
        pin_to_top: false,
        subscribed: true,
    };
    add_row(carSub);
}

function elem($obj) {
    return {to_$: () => $obj};
}

run_test('zoom_in_and_zoom_out', () => {
    var label1 = $.create('label1 stub');
    var label2 = $.create('label2 stub');

    label1.show();
    label2.show();

    assert(label1.visible());
    assert(label2.visible());

    $('.stream-filters-label').each = (f) => {
        f.call(elem(label1));
        f.call(elem(label2));
    };

    const splitter = $.create('hr stub');

    splitter.show();
    assert(splitter.visible());

    $('.stream-split').each = (f) => {
        f.call(elem(splitter));
    };

    const stream_li1 = $.create('stream1 stub');
    const stream_li2 = $.create('stream2 stub');

    function make_attr(arg) {
        return (sel) => {
            assert.equal(sel, 'data-stream-id');
            return arg;
        };
    }

    stream_li1.attr = make_attr('42');
    stream_li1.hide();
    stream_li2.attr = make_attr('99');

    $('#stream_filters li.narrow-filter').each = (f) => {
        f.call(elem(stream_li1));
        f.call(elem(stream_li2));
    };
    stream_list.initialize();

    stream_list.zoom_in_topics({stream_id: 42});

    assert(!label1.visible());
    assert(!label2.visible());
    assert(!splitter.visible());
    assert(stream_li1.visible());
    assert(!stream_li2.visible());
    assert($('#streams_list').hasClass('zoom-in'));

    $('#stream_filters li.narrow-filter').show = () => {
        stream_li1.show();
        stream_li2.show();
    };

    stream_li1.length = 1;
    stream_list.zoom_out_topics({stream_li: stream_li1});

    assert(label1.visible());
    assert(label2.visible());
    assert(splitter.visible());
    assert(stream_li1.visible());
    assert(stream_li2.visible());
    assert($('#streams_list').hasClass('zoom-out'));
});

set_global('$', global.make_zjquery());

run_test('narrowing', () => {
    initialize_stream_data();

    set_global('narrow_state', {
        stream: function () { return 'devel'; },
        topic: noop,
    });

    topic_list.set_click_handlers = noop;
    topic_list.close = noop;
    topic_list.remove_expanded_topics = noop;
    topic_list.rebuild = noop;
    topic_list.active_stream_id = noop;
    topic_list.get_stream_li = noop;
    stream_list.zoom_out_topics = noop;
    scroll_util.scroll_element_into_container = noop;

    var scrollbar_updated = false;

    set_global('ui', {
        update_scrollbar: function () {scrollbar_updated = true;},
    });
    ui.update_scrollbar(
        $.stub_selector("#stream-filters-container")
    );

    assert(!$('<devel sidebar row html>').hasClass('active-filter'));

    stream_list.initialize();

    var filter;

    filter = new Filter([
        {operator: 'stream', operand: 'devel'},
    ]);
    stream_list.handle_narrow_activated(filter);
    assert($('<devel sidebar row html>').hasClass('active-filter'));
    assert(scrollbar_updated);  // Make sure we are updating perfectScrollbar.

    scrollbar_updated = false;
    filter = new Filter([
        {operator: 'stream', operand: 'cars'},
        {operator: 'topic', operand: 'sedans'},
    ]);
    stream_list.handle_narrow_activated(filter);
    assert(!$("ul.filters li").hasClass('active-filter'));
    assert(!$('<cars sidebar row html>').hasClass('active-filter')); // false because of topic
    assert(scrollbar_updated);  // Make sure we are updating perfectScrollbar.

    filter = new Filter([
        {operator: 'stream', operand: 'cars'},
    ]);
    stream_list.handle_narrow_activated(filter);
    assert(!$("ul.filters li").hasClass('active-filter'));
    assert($('<cars sidebar row html>').hasClass('active-filter'));

    var removed_classes;
    $("ul#stream_filters li").removeClass = (classes) => {
        removed_classes = classes;
    };

    var topics_closed;
    topic_list.close = () => {
        topics_closed = true;
    };

    stream_list.handle_narrow_deactivated();
    assert.equal(removed_classes, 'active-filter active-sub-filter');
    assert(topics_closed);
});

run_test('focusout_user_filter', () => {
    var e = { };
    var click_handler = $('.stream-list-filter').get_on_handler('focusout');
    click_handler(e);
});

run_test('focus_user_filter', () => {
    var e = {
        stopPropagation: function () {},
    };
    var click_handler = $('.stream-list-filter').get_on_handler('click');
    click_handler(e);
});

run_test('sort_streams', () => {
    stream_data.clear_subscriptions();

    // Get coverage on early-exit.
    stream_list.build_stream_list();

    initialize_stream_data();

    global.stream_data.is_active = function (sub) {
        return sub.name !== 'cars';
    };


    var appended_elems;
    $('#stream_filters').append = function (elems) {
        appended_elems = elems;
    };

    stream_list.build_stream_list();

    var split = '<hr class="stream-split">';
    var expected_elems = [
        $('<devel sidebar row html>'),
        $('<Rome sidebar row html>'),
        $('<test sidebar row html>'),
        split,
        $('<announce sidebar row html>'),
        $('<Denmark sidebar row html>'),
        split,
        $('<cars sidebar row html>'),
    ];

    assert.deepEqual(appended_elems, expected_elems);

    var streams = global.stream_sort.get_streams();

    assert.deepEqual(streams, [
        // three groups: pinned, normal, dormant
        'devel',
        'Rome',
        'test',
        //
        'announce',
        'Denmark',
        //
        'cars',
    ]);

    var denmark_sub = stream_data.get_sub('Denmark');
    var stream_id = denmark_sub.stream_id;
    assert(stream_list.stream_sidebar.has_row_for(stream_id));
    stream_list.remove_sidebar_row(stream_id);
    assert(!stream_list.stream_sidebar.has_row_for(stream_id));
});

run_test('separators_only_pinned_and_dormant', () => {

    // Test only pinned and dormant streams

    stream_data.clear_subscriptions();

    // Get coverage on early-exit.
    stream_list.build_stream_list();

    // pinned streams
    var develSub = {
        name: 'devel',
        stream_id: 1000,
        color: 'blue',
        pin_to_top: true,
        subscribed: true,
    };
    add_row(develSub);

    var RomeSub = {
        name: 'Rome',
        stream_id: 2000,
        color: 'blue',
        pin_to_top: true,
        subscribed: true,
    };
    add_row(RomeSub);
    // dorment stream
    var DenmarkSub = {
        name: 'Denmark',
        stream_id: 3000,
        color: 'blue',
        pin_to_top: false,
        subscribed: true,
    };
    add_row(DenmarkSub);

    global.stream_data.is_active = function (sub) {
        return sub.name !== 'Denmark';
    };

    var appended_elems;
    $('#stream_filters').append = function (elems) {
        appended_elems = elems;
    };

    stream_list.build_stream_list();

    var split = '<hr class="stream-split">';
    var expected_elems = [
        // pinned
        $('<devel sidebar row html>'),
        $('<Rome sidebar row html>'),
        split,
        // dormant
        $('<Denmark sidebar row html>'),
    ];

    assert.deepEqual(appended_elems, expected_elems);

});

run_test('separators_only_pinned', () => {

    // Test only pinned streams

    stream_data.clear_subscriptions();

    // Get coverage on early-exit.
    stream_list.build_stream_list();

    // pinned streams
    var develSub = {
        name: 'devel',
        stream_id: 1000,
        color: 'blue',
        pin_to_top: true,
        subscribed: true,
    };
    add_row(develSub);

    var RomeSub = {
        name: 'Rome',
        stream_id: 2000,
        color: 'blue',
        pin_to_top: true,
        subscribed: true,
    };
    add_row(RomeSub);


    var appended_elems;
    $('#stream_filters').append = function (elems) {
        appended_elems = elems;
    };

    stream_list.build_stream_list();

    var expected_elems = [
        // pinned
        $('<devel sidebar row html>'),
        $('<Rome sidebar row html>'),
        // no separator at the end as no stream follows
    ];

    assert.deepEqual(appended_elems, expected_elems);

});
run_test('update_count_in_dom', () => {
    function make_elem(elem, count_selector, value_selector) {
        var count = $(count_selector);
        var value = $(value_selector);
        elem.set_find_results('.count', count);
        count.set_find_results('.value', value);
        count.set_parent(elem);

        return elem;
    }

    var stream_li = make_elem(
        $('<stream li>'),
        '<stream-count>',
        '<stream-value>'
    );

    stream_li.addClass('subscription_block');
    stream_li.addClass('stream-with-count');
    assert(stream_li.hasClass('stream-with-count'));

    var stream_count = new Dict();
    var stream_id = 11;

    var stream_row = {
        get_li: function () { return stream_li; },
    };

    stream_list.stream_sidebar.set_row(stream_id, stream_row);

    stream_count.set(stream_id, 0);
    var counts = {
        stream_count: stream_count,
        topic_count: new Dict(),
    };

    stream_list.update_dom_with_unread_counts(counts);
    assert.equal($('<stream li>').text(), 'never-been-set');
    assert(!stream_li.hasClass('stream-with-count'));

    stream_count.set(stream_id, 99);

    stream_list.update_dom_with_unread_counts(counts);
    assert.equal($('<stream-value>').text(), '99');
    assert(stream_li.hasClass('stream-with-count'));

    var topic_results;

    topic_list.set_count = function (stream_id, topic, count) {
        topic_results = {
            stream_id: stream_id,
            topic: topic,
            count: count,
        };
    };

    var topic_count = new Dict({fold_case: true});
    topic_count.set('lunch', '555');
    counts.topic_count.set(stream_id, topic_count);

    stream_list.update_dom_with_unread_counts(counts);

    assert.deepEqual(topic_results, {
        stream_id: stream_id,
        topic: 'lunch',
        count: 555,
    });
});

narrow_state.active = () => false;

run_test('rename_stream', () => {
    const sub = stream_data.get_sub_by_name('devel');
    const new_name = 'Development';

    stream_data.rename_sub(sub, new_name);

    const li_stub = $.create('li stub');
    templates.render = (name, payload) => {
        assert.equal(name, 'stream_sidebar_row');
        assert.deepEqual(payload, {
            name: 'Development',
            id: 1000,
            uri: '#narrow/stream/1000-Development',
            not_in_home_view: false,
            invite_only: undefined,
            color: payload.color,
            pin_to_top: true,
            dark_background: payload.dark_background,
        });
        return {to_$: () => li_stub};
    };

    var count_updated;
    stream_list.update_count_in_dom = (li) => {
        assert.equal(li, li_stub);
        count_updated = true;
    };

    stream_list.rename_stream(sub);
    assert(count_updated);
});

set_global('$', global.make_zjquery());

run_test('refresh_pin', () => {
    initialize_stream_data();

    const sub = {
        name: 'maybe_pin',
        stream_id: 100,
        color: 'blue',
        pin_to_top: false,
    };

    stream_data.add_sub(sub.name, sub);

    const pinned_sub = _.extend(sub, {
        pin_to_top: true,
    });

    const li_stub = $.create('li stub');
    templates.render = () => {
        return {to_$: () => li_stub};
    };

    stream_list.update_count_in_dom = noop;
    $('#stream_filters').append = noop;

    var scrolled;
    stream_list.scroll_stream_into_view = (li) => {
        assert.equal(li, li_stub);
        scrolled = true;
    };

    stream_list.refresh_pinned_or_unpinned_stream(pinned_sub);
    assert(scrolled);
});

run_test('create_initial_sidebar_rows', () => {
    initialize_stream_data();

    var html_dict = new Dict();

    stream_list.stream_sidebar = {
        has_row_for: return_false,
        set_row: function (stream_id, widget) {
            html_dict.set(stream_id, widget.get_li().html());
        },
    };

    stream_list.update_count_in_dom = noop;

    global.templates.render = function (template_name, data) {
        assert.equal(template_name, 'stream_sidebar_row');
        return '<div>stub-html-' + data.name;
    };

    // Test this code with stubs above...
    stream_list.create_initial_sidebar_rows();

    assert.equal(html_dict.get(1000), '<div>stub-html-devel');
    assert.equal(html_dict.get(5000), '<div>stub-html-Denmark');
});
