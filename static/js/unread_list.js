var unread_list = (function () {

var exports = {};

exports.list_widget = function (conf) {
    var self = {};

    self.rebuild = function () {
        var data = conf.get_bulk_data();
        var list_ul = $('<ul>');

        _.each(data, function (item) {
            var html = conf.build_html(item);
            var li = $('<li>');
            li.html(html);
            list_ul.append(li);
        });

        var container = conf.get_container();
        container.html(list_ul);

        conf.update_messaging(data);
    };

    return self;
};

exports.build_html = function (item) {
    return templates.render('unread_list_item', item);
};

function get_text_class(color) {
    return stream_color.get_color_class(color) || 'light_background';
}

exports.get_pm_data = function (opts) {
    var user_ids_string = opts.user_ids_string;
    var reply_to = people.user_ids_string_to_emails_string(user_ids_string);
    var recipients_string = people.get_recipients(user_ids_string);
    var uri = hash_util.pm_with_uri(reply_to);
    var is_group_pm = user_ids_string.indexOf(',') >= 1;
    var is_single_pm = !is_group_pm;
    var small_avatar_url;
    var count = opts.count || '';
    var current = opts.current;

    if (is_single_pm) {
        var person = people.get_person_from_user_id(user_ids_string);
        small_avatar_url = people.small_avatar_url_for_person(person);
    }

    return {
        is_pm: true,
        is_single_pm: is_single_pm,
        is_group_pm: is_group_pm,
        uri: uri,
        name: recipients_string,
        count: count,
        small_avatar_url: small_avatar_url,
        current: current,
    };
};

exports.get_stream_data = function (opts) {
    var sub = opts.sub;
    var stream_id = sub.stream_id;
    var count = opts.count || '';
    var uri = hash_util.by_stream_uri(stream_id);
    var muted = opts.muted;
    var current = opts.current;
    var color = sub.color;
    var text_class = get_text_class(color);
    var show_pin = sub.pin_to_top;

    return {
        is_stream: true,
        stream_id: stream_id,
        name: sub.name,
        count: count,
        invite_only: sub.invite_only,
        color: color,
        text_class: text_class,
        uri: uri,
        muted: muted,
        current: current,
        show_pin: show_pin,
    };
};

exports.get_topic_data = function (opts) {
    var stream_id = opts.stream_id;
    var sub = stream_data.get_sub_by_id(stream_id);
    var topic = opts.topic;
    var count = opts.count || '';
    var uri = hash_util.by_stream_topic_uri(stream_id, topic);
    var color = sub.color;
    var text_class = get_text_class(color);
    var current = opts.current;
    var muted = opts.muted;

    return {
        is_topic: true,
        stream_id: stream_id,
        topic: topic,
        count: count,
        uri: uri,
        color: color,
        text_class: text_class,
        muted: muted,
        current: current,
    };
};

function compare_bool(a, b) {
    // True values should sort to the "top".
    if (a && !b) {
        return -1;
    }

    if (!a && b) {
        return 1;
    }

    return 0;
}

exports.compare_stream = function (stream_id_a, stream_id_b) {
    var sub_a = stream_data.get_sub_by_id(stream_id_a);
    var sub_b = stream_data.get_sub_by_id(stream_id_b);

    var diff = compare_bool(
        sub_a.pin_to_top,
        sub_b.pin_to_top
    );

    if (diff !== 0) {
        return diff;
    }

    return util.strcmp(sub_a.name, sub_b.name);
};

exports.compare_function = function (item_a, item_b) {
    var diff;

    diff = compare_bool(
        item_a.is_single_pm,
        item_b.is_single_pm
    );
    if (diff !== 0) {
        return diff;
    }

    diff = compare_bool(
        item_a.is_pm,
        item_b.is_pm
    );
    if (diff !== 0) {
        return diff;
    }

    if (item_a.is_private) {
        return util.strcmp(
            item_a.name,
            item_b.name
        );
    }

    if (item_a.stream_id !== item_b.stream_id) {
        return exports.compare_stream(
            item_a.stream_id,
            item_b.stream_id
        );
    }

    diff = compare_bool(
        item_a.is_stream,
        item_b.is_stream
    );
    if (diff !== 0) {
        return diff;
    }

    return util.strcmp(
        item_a.topic,
        item_b.topic
    );
};


exports.get_bulk_data = function () {
    var data = unread.get_counts();

    var dct = new Dict();
    var curr_stream_id = narrow_state.stream_id();
    var curr_topic;

    if (curr_stream_id) {
        curr_topic = narrow_state.topic();
    }

    var curr_pm = narrow_state.pm_string();

    var curr_key;

    if (curr_topic) {
        curr_key = 'topic:' + curr_stream_id + ':' + curr_topic;
    } else if (curr_stream_id) {
        curr_key = 'stream:' + curr_stream_id;
    } else if (curr_pm) {
        curr_key = 'pm:' + curr_pm;
    }

    _.each(data.pm_count.keys(), function (user_ids_string) {
        var count = data.pm_count.get(user_ids_string);

        if (count === 0) {
            return;
        }

        var key = 'pm:' + user_ids_string;
        var pm_item = exports.get_pm_data({
            user_ids_string: user_ids_string,
            count: count,
        });

        dct.set(key, pm_item);
    });

    var stream_ids = data.stream_count.keys();

    _.each(stream_ids, function (stream_id) {
        var sub = stream_data.get_sub_by_id(stream_id);
        var count = data.stream_count.get(stream_id);
        var muted = !stream_data.in_home_view(stream_id);

        if (count === 0) {
            return;
        }

        if (muted) {
            return;
        }

        var key = 'stream:' + stream_id;
        var current = key === curr_key;
        var stream_item = exports.get_stream_data({
            sub: sub,
            count: count,
            muted: muted,
            current: current,
        });
        dct.set(key, stream_item);

        var topic_dct = data.topic_count.get(stream_id);
        _.each(topic_dct.keys(), function (topic) {
            var count = topic_dct.get(topic);

            if (count === 0) {
                return;
            }

            if (muting.is_topic_muted(stream_id, topic)) {
                return;
            }

            var key = 'topic:' + stream_id + ':' + topic;
            var current = key === curr_key;

            var topic_item = exports.get_topic_data({
                stream_id: stream_id,
                topic: topic,
                count: count,
                current: current,
                muted: false,
            });
            dct.set(key, topic_item);
        });
    });


    function add_curr_stream(stream_id) {
        var key = 'stream:' + stream_id;

        if (dct.has(key)) {
            return;
        }

        var sub = stream_data.get_sub_by_id(stream_id);
        var count = data.stream_count.get(stream_id) || '';
        var muted = !stream_data.in_home_view(stream_id);
        var current = key === curr_key;

        var stream_item = exports.get_stream_data({
            sub: sub,
            count: count,
            muted: muted,
            current: current,
        });

        dct.set(key, stream_item);
    }

    if (curr_stream_id) {
        add_curr_stream(curr_stream_id);
    }

    function add_curr_topic(stream_id, topic) {
        var key = 'topic:' + stream_id + ':' + topic;

        if (dct.has(key)) {
            return;
        }

        var count;
        var topic_dct = data.topic_count.get(stream_id);

        if (topic_dct) {
            count = topic_dct.get(topic);
        }

        var current = key === curr_key;
        var muted = muting.is_topic_muted(stream_id, topic);

        var topic_item = exports.get_topic_data({
            stream_id: stream_id,
            topic: topic,
            count: count,
            current: current,
            muted: muted,
        });
        dct.set(key, topic_item);
    }

    if (curr_topic) {
        add_curr_topic(curr_stream_id, curr_topic);
    }

    function add_curr_pm(user_ids_string) {
        var count = data.pm_count.get(user_ids_string);

        var key = 'pm:' + user_ids_string;
        var current = key === curr_key;

        var pm_item = exports.get_pm_data({
            user_ids_string: user_ids_string,
            count: count,
            current: current,
        });

        dct.set(key, pm_item);
    }

    if (curr_pm) {
        add_curr_pm(curr_pm);
    }

    var lst = dct.values();

    lst.sort(exports.compare_function);

    return lst;
};

exports.update_messaging = function (data) {
    var caught_up = data.length === 0;

    $('.unread_caught_up').toggle(caught_up);
};

exports.my_list = exports.list_widget({
    get_container: function () {
        return $('.unread_list_container');
    },
    get_bulk_data: exports.get_bulk_data,
    build_html: exports.build_html,
    update_messaging: exports.update_messaging,
});

exports.rebuild = function () {
    exports.my_list.rebuild();
};

var shown = false;

exports.show = function () {
    shown = true;
    $('.unread_view').show();
    $('.narrows_panel').hide();
    exports.rebuild();
    ui.set_up_scrollbar($('.unread_list_container'));
    ui.update_scrollbar('.unread_list_container');
};

exports.hide = function () {
    shown = false;
    $('.unread_view').hide();
    $('.narrows_panel').show();
};

exports.toggle = function () {
    if (shown) {
        exports.hide();
    } else {
        exports.show();
    }
};

exports.initialize = function () {
    exports.hide();
    $('.unread_view').on('dragstart', function () {
        return false;
    });

    $('.unread_view').on('click', '.unread_stream_pin', function (e) {
        e.stopPropagation();

        popovers.hide_all();

        var elt = e.target;
        var stream_div = $(elt).closest('.unread_list_stream');
        var stream_id = stream_div.attr('data-stream-id');

        // Hide the pin right away.
        var pin_icon = stream_div.find('i');
        pin_icon.hide();

        var sub = stream_data.get_sub_by_id(stream_id);
        stream_edit.set_stream_property(sub, 'pin_to_top', !sub.pin_to_top);

    });
};

return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = unread_list;
}
window.unread_list = unread_list;
