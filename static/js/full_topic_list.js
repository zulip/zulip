var full_topic_list = (function () {

var exports = {};

exports.widget = function (stream_name) {
    var self = {};

    self.topic_items = new Dict({fold_case: true});

    self.build = function () {
        console.info('here');
        var heading = $('<h3 class="topics-for-heading">');
        heading.text('Topics for ' + stream_name);

        $('#topic-history').html(heading);
        $('#topic-history').append(self.make_list());
    };

    self.make_list = function () {
        var topics = stream_data.get_recent_topics(stream_name) || [];

        var ul = $('<ul class="full-topic-list">');
        ul.attr('data-stream', stream);

        _.each(topics, function (subject_obj, idx) {
            var topic_name = subject_obj.subject;
            var num_unread = unread.num_unread_for_subject(stream_name, subject_obj.canon_subject);

            var topic_info = {
                topic_name: topic_name,
                unread: num_unread,
                is_zero: num_unread === 0,
                is_muted: muting.is_topic_muted(stream_name, topic_name),
                url: narrow.by_stream_subject_uri(stream_name, topic_name)
            };
            var li = $(templates.render('full_topic_list_item', topic_info));
            self.topic_items.set(topic_name, li);
            ul.append(li);
        });

        return ul;
    };

    return self;
};
        
exports.build = function (stream_name) {
    var widget = exports.widget(stream_name);
    widget.build();
};

return exports;
}());
if (typeof module !== 'undefined') {
    module.exports = topic_list;
}
