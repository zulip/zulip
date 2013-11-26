var assert = require('assert');

add_dependencies({
    _: 'third/underscore/underscore',
    Dict: 'js/dict',
    Handlebars: 'handlebars',
    templates: 'js/templates',
    muting: 'js/muting',
    narrow: 'js/narrow',
    hashchange: 'js/hashchange'
});

set_global('recent_subjects', new global.Dict());
set_global('unread', {});
set_global('$', function () {});

var stream_list = require('js/stream_list.js');

global.use_template('sidebar_subject_list');

(function test_build_subject_list() {
    var stream = "devel";
    var active_topic = "testing";
    var max_topics = 5;

    var topics = [
        {subject: "coding"}
    ];
    global.recent_subjects.set("devel", topics);
    global.unread.num_unread_for_subject = function () {
        return 1;
    };

    var topic_html = stream_list._build_subject_list(stream, active_topic, max_topics);

}());
