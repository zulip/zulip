"use strict";

const pm_conversations = require("./pm_conversations");

exports.sub_list_generator = function (lst, lower, upper) {
    // lower/upper has Python range semantics so if you pass
    // in lower=5 and upper=8, you get elements 5/6/7
    let i = lower;

    return {
        next() {
            if (i >= upper) {
                return;
            }
            const res = lst[i];
            i += 1;
            return res;
        },
    };
};

exports.reverse_sub_list_generator = function (lst, lower, upper) {
    // lower/upper has Python range semantics so if you pass
    // in lower=5 and upper=8, you get elements 7/6/5
    let i = upper - 1;

    return {
        next() {
            if (i < lower) {
                return;
            }
            const res = lst[i];
            i -= 1;
            return res;
        },
    };
};

exports.list_generator = function (lst) {
    return exports.sub_list_generator(lst, 0, lst.length);
};

exports.reverse_list_generator = function (lst) {
    return exports.reverse_sub_list_generator(lst, 0, lst.length);
};

exports.fchain = function (outer_gen, get_inner_gen) {
    let outer_val = outer_gen.next();
    let inner_gen;

    return {
        next() {
            while (outer_val !== undefined) {
                if (inner_gen === undefined) {
                    inner_gen = get_inner_gen(outer_val);
                    if (!inner_gen || !inner_gen.next) {
                        blueslip.error("Invalid generator returned.");
                        return;
                    }
                }
                const inner = inner_gen.next();
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

    const outer_gen = exports.list_generator(gen_lst);

    return exports.fchain(outer_gen, get);
};

exports.wrap = function (lst, val) {
    if (val === undefined) {
        return exports.list_generator(lst);
    }

    const i = lst.indexOf(val);
    if (i < 0) {
        return exports.list_generator(lst);
    }

    const inners = [
        exports.sub_list_generator(lst, i, lst.length),
        exports.sub_list_generator(lst, 0, i),
    ];

    return exports.chain(inners);
};

exports.wrap_exclude = function (lst, val) {
    if (val === undefined) {
        return exports.list_generator(lst);
    }

    const i = lst.indexOf(val);
    if (i < 0) {
        return exports.list_generator(lst);
    }

    const inners = [
        exports.sub_list_generator(lst, i + 1, lst.length),
        exports.sub_list_generator(lst, 0, i),
    ];

    return exports.chain(inners);
};

exports.reverse_wrap_exclude = function (lst, val) {
    if (val === undefined) {
        return exports.reverse_list_generator(lst);
    }

    const i = lst.indexOf(val);
    if (i < 0) {
        return exports.reverse_list_generator(lst);
    }

    const inners = [
        exports.reverse_sub_list_generator(lst, 0, i),
        exports.reverse_sub_list_generator(lst, i + 1, lst.length),
    ];

    return exports.chain(inners);
};

exports.filter = function (gen, filter_func) {
    return {
        next() {
            while (true) {
                const val = gen.next();
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
        next() {
            const val = gen.next();
            if (val === undefined) {
                return;
            }
            return map_func(val);
        },
    };
};

exports.next_topic = function (streams, get_topics, has_unread_messages, curr_stream, curr_topic) {
    const stream_gen = exports.wrap(streams, curr_stream);

    function get_topic_gen(which_stream) {
        let gen;

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
                topic,
            };
        }

        gen = exports.filter(gen, has_unread);
        gen = exports.map(gen, make_object);

        return gen;
    }

    const outer_gen = exports.fchain(stream_gen, get_topic_gen);
    return outer_gen.next();
};

exports.get_next_topic = function (curr_stream, curr_topic) {
    let my_streams = stream_sort.get_streams();

    my_streams = my_streams.filter((stream_name) => {
        if (!stream_data.is_stream_muted_by_name(stream_name)) {
            return true;
        }
        if (stream_name === curr_stream) {
            // We can use n within a muted stream if we are
            // currently narrowed to it.
            return true;
        }
        return false;
    });

    function get_unmuted_topics(stream_name) {
        const stream_id = stream_data.get_stream_id(stream_name);
        let topics = stream_topic_history.get_recent_topic_names(stream_id);
        topics = topics.filter((topic) => !muting.is_topic_muted(stream_id, topic));
        return topics;
    }

    function has_unread_messages(stream_name, topic) {
        const stream_id = stream_data.get_stream_id(stream_name);
        return unread.topic_has_any_unread(stream_id, topic);
    }

    return exports.next_topic(
        my_streams,
        get_unmuted_topics,
        has_unread_messages,
        curr_stream,
        curr_topic,
    );
};

exports._get_pm_gen = function (curr_pm) {
    const my_pm_strings = pm_conversations.recent.get_strings();
    const gen = exports.wrap_exclude(my_pm_strings, curr_pm);
    return gen;
};

exports._get_unread_pm_gen = function (curr_pm) {
    const pm_gen = exports._get_pm_gen(curr_pm);

    function has_unread(user_ids_string) {
        const num_unread = unread.num_unread_for_person(user_ids_string);
        return num_unread > 0;
    }

    const gen = exports.filter(pm_gen, has_unread);
    return gen;
};

exports.get_next_unread_pm_string = function (curr_pm) {
    const gen = exports._get_unread_pm_gen(curr_pm);
    return gen.next();
};

exports.get_next_stream = function (curr_stream) {
    const my_streams = stream_sort.get_streams();
    const stream_gen = exports.wrap_exclude(my_streams, curr_stream);
    return stream_gen.next();
};

exports.get_prev_stream = function (curr_stream) {
    const my_streams = stream_sort.get_streams();
    const stream_gen = exports.reverse_wrap_exclude(my_streams, curr_stream);
    return stream_gen.next();
};

window.topic_generator = exports;
