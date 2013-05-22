var unread = (function () {

var exports = {};

var unread_counts = {'stream': {}, 'private': {}};
var unread_subjects = {};

function unread_hashkey(message) {
    var hashkey;
    if (message.type === 'stream') {
        hashkey = subs.canonicalized_name(message.stream);
    } else {
        hashkey = message.display_reply_to;
    }

    if (unread_counts[message.type][hashkey] === undefined) {
        unread_counts[message.type][hashkey] = {};
    }

    if (message.type === 'stream') {
        var canon_subject = subs.canonicalized_name(message.subject);
        if (unread_subjects[hashkey] === undefined) {
            unread_subjects[hashkey] = {};
        }
        if (unread_subjects[hashkey][canon_subject] === undefined) {
            unread_subjects[hashkey][canon_subject] = {};
        }
    }

    return hashkey;
}

exports.message_unread = function (message) {
    // This is the only halfway interesting function in this module.
    // Everything else is just slinging hashes around.

    if (message === undefined) {
        return false;
    }

    var sent_by_human = ['website', 'iphone', 'android']
                            .indexOf(message.client.toLowerCase()) !== -1;

    if (message.sender_email === page_params.email && sent_by_human) {
        return false;
    }

    return message.flags === undefined ||
           message.flags.indexOf('read') === -1;
};

exports.update_unread_subjects = function (msg, event) {
    var canon_stream = subs.canonicalized_name(msg.stream);
    var canon_subject = subs.canonicalized_name(msg.subject);

    if (event.subject !== undefined &&
        unread_subjects[canon_stream] !== undefined &&
        unread_subjects[canon_stream][canon_subject] !== undefined &&
        unread_subjects[canon_stream][canon_subject][msg.id]) {
        var new_canon_subject = subs.canonicalized_name(event.subject);
        // Move the unread subject count to the new subject
        delete unread_subjects[canon_stream][canon_subject][msg.id];
        if (unread_subjects[canon_stream][canon_subject].length === 0) {
            delete unread_subjects[canon_stream][canon_subject];
        }
        if (unread_subjects[canon_stream][new_canon_subject] === undefined) {
            unread_subjects[canon_stream][new_canon_subject] = {};
        }
        unread_subjects[canon_stream][new_canon_subject][msg.id] = true;
    }
};

exports.process_loaded_messages = function (messages) {
    $.each(messages, function (idx, message) {
        var unread = exports.message_unread(message);
        if (!unread) {
            return;
        }

        var hashkey = unread_hashkey(message);
        unread_counts[message.type][hashkey][message.id] = true;

        if (message.type === 'stream') {
            var canon_subject = subs.canonicalized_name(message.subject);
            unread_subjects[hashkey][canon_subject][message.id] = true;
        }
    });
};

exports.process_read_message = function (message) {
    var hashkey = unread_hashkey(message);
    delete unread_counts[message.type][hashkey][message.id];
    if (message.type === 'stream') {
        var canon_stream = subs.canonicalized_name(message.stream);
        var canon_subject = subs.canonicalized_name(message.subject);
        delete unread_subjects[canon_stream][canon_subject][message.id];
    }
};

exports.declare_bankruptcy = function () {
    unread_counts = {'stream': {}, 'private': {}};
};

exports.get_counts = function () {
    var res = {};

    // Return a data structure with various counts.  This function should be
    // pretty cheap, even if you don't care about all the counts, and you
    // should strive to keep it free of side effects on globals or DOM.
    res.private_message_count = 0;
    res.home_unread_messages = 0;
    res.stream_count = {};  // hash by stream -> count
    res.subject_count = {}; // hash of hashes (stream, then subject -> count)

    function only_in_home_view(msgids) {
        return $.grep(msgids, function (msgid) {
            return home_msg_list.get(msgid) !== undefined;
        });
    }

    $.each(unread_counts.stream, function(stream, msgs) {
        if (! subs.have(stream)) {
            return true;
        }

        var count = Object.keys(msgs).length;
        res.stream_count[stream]= count;

        if (narrow.stream_in_home(stream)) {
            res.home_unread_messages += only_in_home_view(Object.keys(msgs)).length;
        }

        if (unread_subjects[stream] !== undefined) {
            res.subject_count[stream] = {};
            $.each(unread_subjects[stream], function (subject, msgs) {
                res.subject_count[stream][subject] = Object.keys(msgs).length;
            });
        }

    });

    var pm_count = 0;
    $.each(unread_counts["private"], function(index, obj) {
        pm_count += Object.keys(obj).length;
    });
    res.private_message_count = pm_count;
    res.home_unread_messages += pm_count;

    return res;
};

exports.num_unread_for_subject = function (stream, subject) {
    var num_unread = 0;
    if (unread_subjects[stream] !== undefined &&
        unread_subjects[stream][subject] !== undefined) {
        num_unread = Object.keys(unread_subjects[stream][subject]).length;
    }
    return num_unread;
};

return exports;
}());

