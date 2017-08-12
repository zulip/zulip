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
zrequire('narrow');
zrequire('unread');
zrequire('stream_data');
zrequire('stream_list');

var noop = function () {};
var return_false = function () { return false; };
var return_true = function () { return true; };

set_global('topic_list', {});

(function test_create_sidebar_row() {
    // Make a couple calls to create_sidebar_row() and make sure they
    // generate the right markup as well as play nice with get_stream_li().

    var devel = {
        name: 'devel',
        stream_id: 100,
        color: 'blue',
        subscribed: true,
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
            assert.equal(data.uri, '#narrow/stream/devel');
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
            assert.equal(data.uri, '#narrow/stream/social');
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
        split,
        devel_sidebar,
        social_sidebar,
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
}());

function initialize_stream_data() {
    stream_data.clear_subscriptions();

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

(function test_narrowing() {
    initialize_stream_data();

    var document = 'document-stub';

    set_global('document', document);
    set_global('narrow_state', {
        stream: function () { return 'devel'; },
        topic: noop,
    });

    topic_list.set_click_handlers = noop;
    topic_list.close = noop;
    topic_list.remove_expanded_topics = noop;
    topic_list.rebuild = noop;
    topic_list.active_stream_id = noop;
    stream_list.show_all_streams = noop;
    stream_list.scroll_element_into_container = noop;

    var scrollbar_updated = false;
    $.stub_selector("#stream-filters-container", {
        perfectScrollbar: function () { scrollbar_updated = true; },
    });

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
}());

(function test_sort_streams() {
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
}());

(function test_update_count_in_dom() {
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
}());

(function test_create_initial_sidebar_rows() {
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
}());

(function test_scroll_delta() {
    // If we are entirely on-screen, don't scroll
    assert.equal(0, stream_list.scroll_delta({
        elem_top: 1,
        elem_bottom: 9,
        container_height: 10,
    }));

    assert.equal(0, stream_list.scroll_delta({
        elem_top: -5,
        elem_bottom: 15,
        container_height: 10,
    }));

    // The top is offscreen.
    assert.equal(-3, stream_list.scroll_delta({
        elem_top: -3,
        elem_bottom: 5,
        container_height: 10,
    }));

    assert.equal(-3, stream_list.scroll_delta({
        elem_top: -3,
        elem_bottom: -1,
        container_height: 10,
    }));

    assert.equal(-11, stream_list.scroll_delta({
        elem_top: -150,
        elem_bottom: -1,
        container_height: 10,
    }));

    // The bottom is offscreen.
    assert.equal(3, stream_list.scroll_delta({
        elem_top: 7,
        elem_bottom: 13,
        container_height: 10,
    }));

    assert.equal(3, stream_list.scroll_delta({
        elem_top: 11,
        elem_bottom: 13,
        container_height: 10,
    }));

    assert.equal(11, stream_list.scroll_delta({
        elem_top: 11,
        elem_bottom: 99,
        container_height: 10,
    }));

}());
