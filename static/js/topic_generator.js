var topic_generator = (function () {

var exports = {};

exports.sub_list_generator = function (lst, lower, upper) {
    // lower/upper has Python range semantics so if you pass
    // in lower=5 and upper=8, you get elements 5/6/7
    var i = lower;

    return {
        next: function () {
            if (i >= upper) {
                return;
            }
            var res = lst[i];
            i += 1;
            return res;
        },
    };
};

exports.list_generator = function (lst) {
    return exports.sub_list_generator(lst, 0, lst.length);
};

exports.fchain = function (outer_gen, get_inner_gen) {
    var outer_val = outer_gen.next();
    var inner_gen;

    return {
        next: function () {
            while (outer_val !== undefined) {
                if (inner_gen === undefined) {
                    inner_gen = get_inner_gen(outer_val);
                    if (!inner_gen || !inner_gen.next) {
                        blueslip.error('Invalid generator returned.');
                        return;
                    }
                }
                var inner = inner_gen.next();
                if (inner !== undefined) {
                    return inner;
                }
                outer_val = outer_gen.next();
                inner_gen = undefined;
            }
        },
    };
};

exports.chain = function (gen_lst) {
    function get(which) {
        return which;
    }

    var outer_gen = exports.list_generator(gen_lst);

    return exports.fchain(outer_gen, get);
};

exports.wrap = function (lst, val) {
    if (val === undefined) {
        return exports.list_generator(lst);
    }

    var i = _.indexOf(lst, val);
    if (i < 0) {
        return exports.list_generator(lst);
    }

    var inners = [
         exports.sub_list_generator(lst, i, lst.length),
         exports.sub_list_generator(lst, 0, i),
    ];

    return exports.chain(inners);
};

exports.wrap_exclude = function (lst, val) {
    if (val === undefined) {
        return exports.list_generator(lst);
    }

    var i = _.indexOf(lst, val);
    if (i < 0) {
        return exports.list_generator(lst);
    }

    var inners = [
         exports.sub_list_generator(lst, i+1, lst.length),
         exports.sub_list_generator(lst, 0, i),
    ];

    return exports.chain(inners);
};

exports.filter = function (gen, filter_func) {
    return {
        next: function () {
            while (true) {
                var val = gen.next();
                if (val === undefined) {
                    return;
                }
                if (filter_func(val)) {
                    return val;
                }
            }
        },
    };
};

exports.map = function (gen, map_func) {
    return {
        next: function () {
            var val = gen.next();
            if (val === undefined) {
                return;
            }
            return map_func(val);
        },
    };
};

exports.next_topic = function (streams, get_topics, has_unread_messages, curr_stream, curr_topic) {
    var stream_gen = exports.wrap(streams, curr_stream);

    function get_topic_gen(which_stream) {
        var gen;

        if (which_stream === curr_stream) {
            gen = exports.wrap_exclude(get_topics(which_stream), curr_topic);
        } else {
            gen = exports.list_generator(get_topics(which_stream));
        }

        function has_unread(topic) {
            return has_unread_messages(which_stream, topic);
        }

        function make_object(topic) {
            return {
                stream: which_stream,
                topic: topic,
            };
        }

        gen = exports.filter(gen, has_unread);
        gen = exports.map(gen, make_object);

        return gen;
    }

    var outer_gen = exports.fchain(stream_gen, get_topic_gen);
    return outer_gen.next();
};

exports.get_next_topic = function (curr_stream, curr_topic) {
    var my_streams = stream_sort.get_streams();

    my_streams = _.filter(my_streams, function (stream_name) {
        return stream_data.name_in_home_view(stream_name);
    });

    function get_unmuted_topics(stream_name) {
        var topic_objs = stream_data.get_recent_topics(stream_name) || [];
        var topics = _.map(topic_objs, function (obj) { return obj.subject; });
        topics = _.reject(topics, function (topic) {
            return muting.is_topic_muted(stream_name, topic);
        });
        return topics;
    }

    function has_unread_messages(stream_name, topic) {
        var stream_id = stream_data.get_stream_id(stream_name);
        return unread.topic_has_any_unread(stream_id, topic);
    }

    return exports.next_topic(
        my_streams,
        get_unmuted_topics,
        has_unread_messages,
        curr_stream,
        curr_topic
    );
};

return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = topic_generator;
}
