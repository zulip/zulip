var unread = (function () {

var exports = {};

var unread_counts = {
    'stream': new Dict(),
    'private': new Dict()
};
var unread_mentioned = {};
var unread_subjects = new Dict();

function unread_hashkey(message) {
    var hashkey;
    if (message.type === 'stream') {
        hashkey = subs.canonicalized_name(message.stream);
    } else {
        hashkey = message.reply_to;
    }

    if (! unread_counts[message.type].has(hashkey)) {
        unread_counts[message.type].set(hashkey, {});
    }

    if (message.type === 'stream') {
        var canon_subject = subs.canonicalized_name(message.subject);
        if (! unread_subjects.has(hashkey)) {
            unread_subjects.set(hashkey, new Dict());
        }
        if (! unread_subjects.get(hashkey).has(canon_subject)) {
            unread_subjects.get(hashkey).set(canon_subject, {});
        }
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
    var canon_stream = subs.canonicalized_name(msg.stream);
    var canon_subject = subs.canonicalized_name(msg.subject);

    if (event.subject !== undefined &&
        unread_subjects.has(canon_stream) &&
        unread_subjects.get(canon_stream).has(canon_subject) &&
        unread_subjects.get(canon_stream).get(canon_subject)[msg.id]) {
        var new_canon_subject = subs.canonicalized_name(event.subject);
        // Move the unread subject count to the new subject
        delete unread_subjects.get(canon_stream).get(canon_subject)[msg.id];
        if (unread_subjects.get(canon_stream).get(canon_subject).length === 0) {
            unread_subjects.get(canon_stream).del(canon_subject);
        }
        if (! unread_subjects.get(canon_stream).has(new_canon_subject)) {
            unread_subjects.get(canon_stream).set(new_canon_subject, {});
        }
        unread_subjects.get(canon_stream).get(new_canon_subject)[msg.id] = true;
    }
};

exports.process_loaded_messages = function (messages) {
    _.each(messages, function (message) {
        var unread = exports.message_unread(message);
        if (!unread) {
            return;
        }

        var hashkey = unread_hashkey(message);
        unread_counts[message.type].get(hashkey)[message.id] = true;

        if (message.type === 'stream') {
            var canon_subject = subs.canonicalized_name(message.subject);
            unread_subjects.get(hashkey).get(canon_subject)[message.id] = true;
        }

        if (message.mentioned) {
            unread_mentioned[message.id] = true;
        }
    });
};

exports.process_read_message = function (message) {
    var hashkey = unread_hashkey(message);
    delete unread_counts[message.type].get(hashkey)[message.id];
    if (message.type === 'stream') {
        var canon_stream = subs.canonicalized_name(message.stream);
        var canon_subject = subs.canonicalized_name(message.subject);
        delete unread_subjects.get(canon_stream).get(canon_subject)[message.id];
    }
    delete unread_mentioned[message.id];
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
    res.mentioned_message_count = Object.keys(unread_mentioned).length;
    res.stream_count = new Dict();  // hash by stream -> count
    res.subject_count = new Dict(); // hash of hashes (stream, then subject -> count)
    res.pm_count = new Dict(); // Hash by email -> count

    function only_in_home_view(msgids) {
        return _.filter(msgids, function (msgid) {
            return home_msg_list.get(msgid) !== undefined;
        });
    }

    unread_counts.stream.each(function (msgs, stream) {
        if (! subs.is_subscribed(stream)) {
            return true;
        }

        var count = Object.keys(msgs).length;
        res.stream_count.set(stream, count);

        if (subs.in_home_view(stream)) {
            res.home_unread_messages += only_in_home_view(Object.keys(msgs)).length;
        }

        if (unread_subjects.has(stream)) {
            res.subject_count.set(stream, new Dict());
            unread_subjects.get(stream).each(function (msgs, subject) {
                res.subject_count.get(stream).set(subject, Object.keys(msgs).length);
            });
        }

    });

    var pm_count = 0;
    unread_counts["private"].each(function (obj, index) {
        var count = Object.keys(obj).length;
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
        num_unread = Object.keys(unread_subjects.get(stream).get(subject)).length;
    }
    return num_unread;
};

return exports;
}());
if (typeof module !== 'undefined') {
    module.exports = unread;
}
