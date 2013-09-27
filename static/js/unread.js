var unread = (function () {

var exports = {};

var unread_counts = {
    'stream': new Dict(),
    'private': new Dict()
};
var unread_mentioned = new Dict();
var unread_subjects = new Dict({fold_case: true});

function unread_hashkey(message) {
    var hashkey;
    if (message.type === 'stream') {
        hashkey = stream_data.canonicalized_name(message.stream);
    } else {
        hashkey = message.reply_to;
    }

    unread_counts[message.type].setdefault(hashkey, new Dict());

    if (message.type === 'stream') {
        var canon_subject = stream_data.canonicalized_name(message.subject);
        unread_subjects.setdefault(hashkey, new Dict());
        unread_subjects.get(hashkey).setdefault(canon_subject, new Dict());
    }

    return hashkey;
}

exports.message_unread = function (message) {
    if (message === undefined) {
        return false;
    }
    return message.flags === undefined ||
           message.flags.indexOf('read') === -1;
};

exports.update_unread_subjects = function (msg, event) {
    var canon_stream = stream_data.canonicalized_name(msg.stream);
    var canon_subject = stream_data.canonicalized_name(msg.subject);

    if (event.subject !== undefined &&
        unread_subjects.has(canon_stream) &&
        unread_subjects.get(canon_stream).has(canon_subject) &&
        unread_subjects.get(canon_stream).get(canon_subject).get(msg.id)) {
        var new_canon_subject = stream_data.canonicalized_name(event.subject);
        // Move the unread subject count to the new subject
        unread_subjects.get(canon_stream).get(canon_subject).del(msg.id);
        if (unread_subjects.get(canon_stream).get(canon_subject).num_items() === 0) {
            unread_subjects.get(canon_stream).del(canon_subject);
        }
        unread_subjects.get(canon_stream).setdefault(new_canon_subject, new Dict());
        unread_subjects.get(canon_stream).get(new_canon_subject).set(msg.id, true);
    }
};

exports.process_loaded_messages = function (messages) {
    _.each(messages, function (message) {
        var unread = exports.message_unread(message);
        if (!unread) {
            return;
        }

        var hashkey = unread_hashkey(message);
        unread_counts[message.type].get(hashkey).set(message.id, true);

        if (message.type === 'stream') {
            var canon_subject = stream_data.canonicalized_name(message.subject);
            unread_subjects.get(hashkey).get(canon_subject).set(message.id, true);
        }

        if (message.mentioned) {
            unread_mentioned.set(message.id, true);
        }
    });
};

exports.process_read_message = function (message) {
    var hashkey = unread_hashkey(message);
    unread_counts[message.type].get(hashkey).del(message.id);
    if (message.type === 'stream') {
        var canon_stream = stream_data.canonicalized_name(message.stream);
        var canon_subject = stream_data.canonicalized_name(message.subject);
        unread_subjects.get(canon_stream).get(canon_subject).del(message.id);
    }
    unread_mentioned.del(message.id);
};

exports.declare_bankruptcy = function () {
    unread_counts = {'stream': new Dict(), 'private': new Dict()};
};

exports.num_unread_current_messages = function () {
    var num_unread = 0;

    _.each(current_msg_list.all(), function (msg) {
        if ((msg.id > current_msg_list.selected_id()) && exports.message_unread(msg)) {
            num_unread += 1;
        }
    });

    return num_unread;
};

exports.get_counts = function () {
    var res = {};

    // Return a data structure with various counts.  This function should be
    // pretty cheap, even if you don't care about all the counts, and you
    // should strive to keep it free of side effects on globals or DOM.
    res.private_message_count = 0;
    res.home_unread_messages = 0;
    res.mentioned_message_count = unread_mentioned.num_items();
    res.stream_count = new Dict();  // hash by stream -> count
    res.subject_count = new Dict(); // hash of hashes (stream, then subject -> count)
    res.pm_count = new Dict(); // Hash by email -> count

    unread_counts.stream.each(function (msgs, stream) {
        if (! stream_data.is_subscribed(stream)) {
            return true;
        }

        if (unread_subjects.has(stream)) {
            res.subject_count.set(stream, new Dict());
            var stream_count = 0;
            unread_subjects.get(stream).each(function (msgs, subject) {
                var subject_count = msgs.num_items();
                res.subject_count.get(stream).set(subject, subject_count);
                stream_count += subject_count;
            });
            res.stream_count.set(stream, stream_count);
            if (stream_data.in_home_view(stream)) {
                res.home_unread_messages += stream_count;
            }
        }

    });

    var pm_count = 0;
    unread_counts["private"].each(function (obj, index) {
        var count = obj.num_items();
        res.pm_count.set(index, count);
        pm_count += count;
    });
    res.private_message_count = pm_count;
    res.home_unread_messages += pm_count;

    if (narrow.active()) {
        res.unread_in_current_view = exports.num_unread_current_messages();
    }
    else {
        res.unread_in_current_view = res.home_unread_messages;
    }

    return res;
};

exports.num_unread_for_subject = function (stream, subject) {
    var num_unread = 0;
    if (unread_subjects.has(stream) &&
        unread_subjects.get(stream).has(subject)) {
        num_unread = unread_subjects.get(stream).get(subject).num_items();
    }
    return num_unread;
};

exports.num_unread_for_person = function (email) {
    if (!unread_counts['private'].has(email)) {
        return 0;
    }
    return unread_counts['private'].get(email).num_items();
};

return exports;
}());
if (typeof module !== 'undefined') {
    module.exports = unread;
}
