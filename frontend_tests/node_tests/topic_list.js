add_dependencies({
    Handlebars: 'handlebars',
    hash_util: 'js/hash_util',
    hashchange: 'js/hashchange',
    muting: 'js/muting',
    narrow: 'js/narrow',
    stream_data: 'js/stream_data',
    templates: 'js/templates',
});

set_global('unread', {});

var jsdom = require("jsdom");
var window = jsdom.jsdom().defaultView;
global.$ = require('jquery')(window);

var topic_list = require('js/topic_list.js');

global.compile_template('topic_list_item');

(function test_topic_list_build_widget() {
    var stream = "devel";
    var active_topic = "testing";
    var max_topics = 5;

    var topics = [
        {subject: "coding"},
    ];
    global.stream_data.populate_stream_topics_for_tests({devel: topics});
    global.unread.num_unread_for_subject = function () {
        return 1;
    };

    var parent_elem = $('<div>');
    var widget = topic_list.build_widget(parent_elem, stream, active_topic, max_topics);
    var topic_html = widget.get_dom();

    assert.equal(widget.get_parent(), parent_elem);
    assert.equal(widget.get_stream_name(), 'devel');

    var topic = $(topic_html).find('a').text().trim();
    assert.equal(topic, 'coding');

    global.write_test_output("test_topic_list_build_widget", parent_elem.html());
}());
