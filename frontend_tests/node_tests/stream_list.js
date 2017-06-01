set_global('$', global.make_zjquery());

set_global('templates', {});

add_dependencies({
    colorspace: 'js/colorspace',
    hash_util: 'js/hash_util',
    narrow: 'js/narrow',
    stream_color: 'js/stream_color',
    stream_data: 'js/stream_data',
    stream_sort: 'js/stream_sort',
    unread: 'js/unread',
    util: 'js/util',
});

var stream_list = require('js/stream_list.js');

(function test_create_sidebar_row() {
    // Make a couple calls to create_sidebar_row() and make sure they
    // generate the right markup as well as play nice with get_stream_li().

    var devel = {
        name: 'devel',
        stream_id: 100,
        color: 'blue',
        subscribed: true,
        id: 5,
    };
    global.stream_data.add_sub('devel', devel);

    var social = {
        name: 'social',
        stream_id: 200,
        color: 'green',
        subscribed: true,
        id: 6,
    };
    global.stream_data.add_sub('social', social);

    global.unread.num_unread_for_stream = function () {
        return 42;
    };

    (function create_devel_sidebar_row() {
        var devel_value = $('devel-value');
        var devel_count = $('devel-count');
        $('devel-stub-html').add_child('.count', devel_count);
        $('devel-count').add_child('.value', devel_value);

        global.templates.render = function (template_name, data) {
            assert.equal(template_name, 'stream_sidebar_row');
            assert.equal(data.uri, '#narrow/stream/devel');
            return 'devel-stub-html';
        };

        stream_list.create_sidebar_row(devel);
        assert.equal(devel_value.text(), '42');
    }());

    (function create_social_sidebar_row() {
        var social_value = $('social-value');
        var social_count = $('social-count');
        $('social-stub-html').add_child('.count', social_count);
        $('social-count').add_child('.value', social_value);

        global.templates.render = function (template_name, data) {
            assert.equal(template_name, 'stream_sidebar_row');
            assert.equal(data.uri, '#narrow/stream/social');
            return 'social-stub-html';
        };

        stream_list.create_sidebar_row(social);
        assert.equal(social_value.text(), '42');
    }());

    function set_getter(elem, stub_value) {
        elem.get = function (idx) {
            assert.equal(idx, 0);
            return stub_value;
        };
    }

    set_getter($('<hr class="stream-split">'), 'split');
    set_getter($('devel-stub-html'), 'devel-sidebar');
    set_getter($('social-stub-html'), 'social-sidebar');

    var appended_elems;
    $('#stream_filters').append = function (elems) {
        appended_elems = elems;
    };

    stream_list.build_stream_list();

    var expected_elems = [
        'split',
        'devel-sidebar',
        'social-sidebar',
    ];

    assert.deepEqual(appended_elems, expected_elems);

}());


(function test_sort_streams() {
    stream_data.clear_subscriptions();

    function add_row(sub) {
        global.stream_data.add_sub(sub.name, sub);
        var row = {
            update_whether_active: function () {},
            get_li: function () {
                return {
                    get: function () {
                        return 'stub-' + sub.name;
                    },
                };
            },
        };
        stream_list.stream_sidebar.set_row(sub.stream_id, row);
    }

    // pinned streams
    var develSub = {
        name: 'devel',
        stream_id: 1000,
        color: 'blue',
        id: 5,
        pin_to_top: true,
        subscribed: true,
    };
    add_row(develSub);

    var RomeSub = {
        name: 'Rome',
        stream_id: 2000,
        color: 'blue',
        id: 6,
        pin_to_top: true,
        subscribed: true,
    };
    add_row(RomeSub);

    var testSub = {
        name: 'test',
        stream_id: 3000,
        color: 'blue',
        id: 7,
        pin_to_top: true,
        subscribed: true,
    };
    add_row(testSub);

    // unpinned streams
    var announceSub = {
        name: 'announce',
        stream_id: 4000,
        color: 'green',
        id: 8,
        pin_to_top: false,
        subscribed: true,
    };
    add_row(announceSub);

    var DenmarkSub = {
        name: 'Denmark',
        stream_id: 5000,
        color: 'green',
        id: 9,
        pin_to_top: false,
        subscribed: true,
    };
    add_row(DenmarkSub);

    var carSub = {
        name: 'cars',
        stream_id: 6000,
        color: 'green',
        id: 10,
        pin_to_top: false,
        subscribed: true,
    };
    add_row(carSub);


    global.stream_data.is_active = function (sub) {
        return sub.name !== 'cars';
    };


    var appended_elems;
    $('#stream_filters').append = function (elems) {
        appended_elems = elems;
    };

    stream_list.build_stream_list();

    var expected_elems = [
        'stub-devel',
        'stub-Rome',
        'stub-test',
        'split',
        'stub-announce',
        'stub-Denmark',
        'split',
        'stub-cars',
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

}());
