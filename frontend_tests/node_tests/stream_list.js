set_global('$', function () {});

add_dependencies({
    Handlebars: 'handlebars',
    templates: 'js/templates',
    muting: 'js/muting',
    narrow: 'js/narrow',
    stream_color: 'js/stream_color',
    stream_data: 'js/stream_data',
    subs: 'js/subs',
    hashchange: 'js/hashchange'
});

global.recent_subjects = new global.Dict();

set_global('unread', {});
set_global('message_store', {
    recent_private_messages: new global.Array()
});

var stream_list = require('js/stream_list.js');

global.$ = require('jQuery');
$.fn.expectOne = function () {
    assert(this.length === 1);
    return this;
};

global.use_template('sidebar_subject_list');
global.use_template('sidebar_private_message_list');
global.use_template('stream_sidebar_row');
global.use_template('stream_privacy');

(function test_build_subject_list() {
    var stream = "devel";
    var active_topic = "testing";
    var max_topics = 5;

    var topics = [
        {subject: "coding"}
    ];
    global.stream_data.recent_subjects.set("devel", topics);
    global.unread.num_unread_for_subject = function () {
        return 1;
    };

    var topic_html = stream_list._build_subject_list(stream, active_topic, max_topics);
    global.write_test_output("test_build_subject_list", topic_html);

    var topic = $(topic_html).find('a').text().trim();
    assert.equal(topic, 'coding');
}());

(function test_build_private_messages_list() {
    var reply_tos = "alice@zulip.com,bob@zulip.com";
    var active_conversation = "Alice, Bob";
    var max_conversations = 5;


    var conversations = {reply_to: reply_tos,
                      display_reply_to: active_conversation,
                      timestamp: 0 };
    global.message_store.recent_private_messages.push(conversations);

    global.unread.num_unread_for_person = function () {
        return 1;
    };

    var convos_html = stream_list._build_private_messages_list(active_conversation, max_conversations);
    global.write_test_output("test_build_private_messages_list", convos_html);

    var conversation = $(convos_html).find('a').text().trim();
    assert.equal(conversation, active_conversation);
}());


(function test_add_stream_to_sidebar() {
    // Make a couple calls to add_stream_to_sidebar() and make sure they
    // generate the right markup as well as play nice with get_stream_li().

    var stream_filters = $('<ul id="stream_filters">');
    $("body").append(stream_filters);

    var stream = "devel";

    var sub = {
        name: 'devel',
        stream_id: 1000,
        color: 'blue',
        id: 5
    };
    global.stream_data.add_sub('devel', sub);

    sub = {
        name: 'social',
        stream_id: 2000,
        color: 'green',
        id: 6
    };
    global.stream_data.add_sub('social', sub);

    stream_list.add_stream_to_sidebar('devel');
    stream_list.add_stream_to_sidebar('social');

    var html = $("body").html();
    global.write_test_output("test_add_stream_to_sidebar", html);

    var li = stream_list.get_stream_li('social');
    assert.equal(li.attr('data-name'), 'social');
    assert.equal(li.find('.streamlist_swatch').css('background-color'), 'green');
    assert.equal(li.find('a.subscription_name').text().trim(), 'social');
    assert(li.find('.arrow').find("i").hasClass("icon-vector-chevron-down"));

    global.append_test_output("Then make 'social' private.");
    global.stream_data.get_sub('social').invite_only = true;
    stream_list.redraw_stream_privacy('social');

    html = $("body").html();
    global.append_test_output(html);

    assert(li.find('.stream-privacy').find("i").hasClass("icon-vector-lock"));
}());


(function test_sort_pin_to_top_streams() {

    var stream_search_box = $('<input class="stream-list-filter" type="text" placeholder="Search streams">');
    var stream_filters = $('<ul id="stream_filters">');
    $("body").empty();
    $("body").append(stream_search_box);
    $("body").append(stream_filters);

    var develSub = {
        name: 'devel',
        stream_id: 1000,
        color: 'blue',
        id: 5,
        pin_to_top: false,
        subscribed: true,
        sidebar_li: stream_list.add_stream_to_sidebar('devel')
    };
    global.stream_data.add_sub('devel', develSub);

    var socialSub = {
        name: 'social',
        stream_id: 2000,
        color: 'green',
        id: 6,
        pin_to_top: true,
        subscribed: true,
        sidebar_li: stream_list.add_stream_to_sidebar('social')
    };
    global.stream_data.add_sub('social', socialSub);
    stream_list.build_stream_list();
    assert.equal(socialSub.sidebar_li.nextAll().find('[ data-name="devel"]').length, 1);
}());
