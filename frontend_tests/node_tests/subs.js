global.stub_out_jquery();

set_global('ui', {
    update_scrollbar: function () {},
});

set_global('i18n', global.stub_i18n);
set_global('channel', {});

zrequire('stream_data');
zrequire('Handlebars', 'handlebars');
zrequire('templates');
zrequire('subs');

var jsdom = require("jsdom");
var window = jsdom.jsdom().defaultView;
global.$ = require('jquery')(window);
set_global('window', window);
zrequire('bootstrap', 'third/bootstrap/js/bootstrap');

subs.stream_name_match_stream_ids = [];
subs.stream_description_match_stream_ids = [];

(function test_filter_table() {
    var denmark = {
        subscribed: false,
        name: 'Denmark',
        stream_id: 1,
        description: 'Copenhagen',
    };
    var poland = {
        subscribed: true,
        name: 'Poland',
        stream_id: 2,
        description: 'monday',
    };
    var pomona = {
        subscribed: true,
        name: 'Pomona',
        stream_id: 3,
        description: 'college',
    };
    var cpp = {
        subscribed: true,
        name: 'C++',
        stream_id: 4,
    };

    var elem_1 = $(global.render_template("subscription", denmark));
    var elem_2 = $(global.render_template("subscription", poland));
    var elem_3 = $(global.render_template("subscription", pomona));
    var elem_4 = $(global.render_template("subscription", cpp));

    $("body").empty();
    $("body").append('<div id="subscriptions_table"></div>');
    var streams_list = $('<div class="streams-list"></div>');
    $("#subscriptions_table").append(streams_list);

    stream_data.add_sub("Denmark", denmark);
    stream_data.add_sub("Poland", poland);
    stream_data.add_sub("Pomona", pomona);
    stream_data.add_sub("C++", cpp);

    streams_list.append(elem_1);
    streams_list.append(elem_2);
    streams_list.append(elem_3);

    // Search with single keyword
    subs.filter_table({input: "Po", subscribed_only: false});
    assert(elem_1.hasClass("notdisplayed"));
    assert(!elem_2.hasClass("notdisplayed"));
    assert(!elem_3.hasClass("notdisplayed"));

    // Search with multiple keywords
    subs.filter_table({input: "Denmark, Pol", subscribed_only: false});
    assert(!elem_1.hasClass("notdisplayed"));
    assert(!elem_2.hasClass("notdisplayed"));
    assert(elem_3.hasClass("notdisplayed"));

    subs.filter_table({input: "Den, Pol", subscribed_only: false});
    assert(!elem_1.hasClass("notdisplayed"));
    assert(!elem_2.hasClass("notdisplayed"));
    assert(elem_3.hasClass("notdisplayed"));

    // Search is case-insensitive
    subs.filter_table({input: "po", subscribed_only: false});
    assert(elem_1.hasClass("notdisplayed"));
    assert(!elem_2.hasClass("notdisplayed"));
    assert(!elem_3.hasClass("notdisplayed"));

    // Search handles unusual characters like C++
    subs.filter_table({input: "c++", subscribed_only: false});
    assert(elem_1.hasClass("notdisplayed"));
    assert(elem_2.hasClass("notdisplayed"));
    assert(elem_3.hasClass("notdisplayed"));
    assert(!elem_4.hasClass("notdisplayed"));

    // Search subscribed streams only
    subs.filter_table({input: "d", subscribed_only: true});
    assert(elem_1.hasClass("notdisplayed"));
    assert(!elem_2.hasClass("notdisplayed"));
    assert(elem_3.hasClass("notdisplayed"));

    // data-temp-view condition
    elem_1.attr("data-temp-view", "true");

    subs.filter_table({input: "d", subscribed_only: true});
    assert(!elem_1.hasClass("notdisplayed"));
    assert(!elem_2.hasClass("notdisplayed"));
    assert(elem_3.hasClass("notdisplayed"));

    elem_1.attr("data-temp-view", "false");

    subs.filter_table({input: "d", subscribed_only: true});
    assert(elem_1.hasClass("notdisplayed"));
    assert(!elem_2.hasClass("notdisplayed"));
    assert(elem_3.hasClass("notdisplayed"));

    elem_1.removeAttr("data-temp-view");

    // active stream-row is not included in results
    elem_1.addClass("active");
    $("#subscriptions_table").append($('<div class="right"></div>'));
    $(".right").append($('<div class="settings"></div>'));
    $(".right").append($('<div class="nothing-selected"></div>').hide());

    subs.filter_table({input: "d", subscribed_only: true});
    assert(!elem_1.hasClass("active"));
    assert.equal($(".right .settings").css("display"), "none");
    assert.notEqual($(".right .nothing-selected").css("display"), "none");

    // Search terms match stream description
    subs.filter_table({input: "Co", subscribed_only: false});
    assert(!elem_1.hasClass("notdisplayed"));
    assert(elem_2.hasClass("notdisplayed"));
    assert(!elem_3.hasClass("notdisplayed"));

    subs.filter_table({input: "Mon", subscribed_only: false});
    assert(elem_1.hasClass("notdisplayed"));
    assert(!elem_2.hasClass("notdisplayed"));
    assert(!elem_3.hasClass("notdisplayed"));

    subs.filter_table({input: "p", subscribed_only: false});
    assert.equal(subs.stream_name_match_stream_ids.length, 2);
    assert.equal(subs.stream_description_match_stream_ids, 1);
    assert.equal(subs.stream_name_match_stream_ids[0], 2);
    assert.equal(subs.stream_name_match_stream_ids[1], 3);
    assert.equal(subs.stream_description_match_stream_ids[0], 1);

    subs.filter_table({input: "d", subscribed_only: false});
    assert.equal(subs.stream_name_match_stream_ids.length, 2);
    assert.equal(subs.stream_description_match_stream_ids, 0);
    assert.equal(subs.stream_name_match_stream_ids[0], 1);
    assert.equal(subs.stream_name_match_stream_ids[1], 2);
}());

(function test_sub_or_unsub() {
    var denmark = {
        subscribed: false,
        name: 'Denmark',
        stream_id: 1,
        description: 'Copenhagen',
    };
    stream_data.clear_subscriptions();
    stream_data.add_sub("Denmark", denmark);

    var post_params;

    global.channel.post = function (params) {
        post_params = params;
    };

    subs.sub_or_unsub(denmark);
    assert.equal(post_params.url, '/json/users/me/subscriptions');
    assert.deepEqual(post_params.data,
        {subscriptions: '[{"name":"Denmark"}]'});

    global.channel.post = undefined;

    global.channel.del = function (params) {
        post_params = params;
    };

    stream_data.get_sub_by_id(denmark.stream_id).subscribed = true;
    subs.sub_or_unsub(denmark);
    assert.equal(post_params.url, '/json/users/me/subscriptions');
    assert.deepEqual(post_params.data,
        {subscriptions: '["Denmark"]'});

}());

