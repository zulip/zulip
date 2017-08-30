var condense = (function () {

var exports = {};

var _message_content_height_cache = new Dict();

function show_more_link(row) {
    row.find(".message_condenser").hide();
    row.find(".message_expander").show();
}

function show_condense_link(row) {
    row.find(".message_expander").hide();
    row.find(".message_condenser").show();
}

function condense_row(row) {
    var content = row.find(".message_content");
    content.addClass("condensed");
    show_more_link(row);
}

function uncondense_row(row) {
    var content = row.find(".message_content");
    content.removeClass("condensed");
    show_condense_link(row);
}

exports.uncollapse = function (row) {
    // Uncollapse a message, restoring the condensed message [More] or
    // [Condense] link if necessary.
    var message = current_msg_list.get(rows.id(row));
    message.collapsed = false;
    message_flags.send_collapsed([message], false);

    var process_row = function process_row(row) {
        var content = row.find(".message_content");
        content.removeClass("collapsed");

        if (message.condensed === true) {
            // This message was condensed by the user, so re-show the
            // [More] link.
            condense_row(row);
        } else if (message.condensed === false) {
            // This message was un-condensed by the user, so re-show the
            // [Condense] link.
            uncondense_row(row);
        } else if (content.hasClass("could-be-condensed")) {
            // By default, condense a long message.
            condense_row(row);
        } else {
            // This was a short message, no more need for a [More] link.
            row.find(".message_expander").hide();
        }
    };

    // We also need to collapse this message in the home view
    var home_row = home_msg_list.get_row(rows.id(row));

    process_row(row);
    process_row(home_row);
};

exports.collapse = function (row) {
    // Collapse a message, hiding the condensed message [More] or
    // [Condense] link if necessary.
    var message = current_msg_list.get(rows.id(row));
    message.collapsed = true;
    message_flags.send_collapsed([message], true);

    var process_row = function process_row(row) {
        row.find(".message_content").addClass("collapsed");
        show_more_link(row);
    };

    // We also need to collapse this message in the home view
    var home_row = home_msg_list.get_row(rows.id(row));

    process_row(row);
    process_row(home_row);
};

exports.toggle_collapse = function (message) {
    var row = current_msg_list.get_row(message.id);
    if (!row) {
        return;
    }
    var condensed = row.find(".could-be-condensed");
    if (message.collapsed) {
        message.condensed = true;
        condense.uncollapse(row);
        condensed.addClass("condensed");
        exports.show_message_expander(row);
        row.find(".message_condenser").hide();
    } else if (!message.collapsed && condensed.hasClass("condensed")) {
        message.condensed = false;
        condensed.removeClass("condensed");
        exports.hide_message_expander(row);
        row.find(".message_condenser").show();
    } else if (!message.collapsed && !condensed.hasClass("condensed")) {
        condense.collapse(row);
    }
};

exports.clear_message_content_height_cache = function () {
    _message_content_height_cache = new Dict();
};

exports.un_cache_message_content_height = function (message_id) {
    _message_content_height_cache.del(message_id);
};

function get_message_height(elem, message_id) {
    if (_message_content_height_cache.has(message_id)) {
        return _message_content_height_cache.get(message_id);
    }

    // shown to be ~2.5x faster than Node.getBoundingClientRect().
    var height = elem.offsetHeight;
    _message_content_height_cache.set(message_id, height);
    return height;
}

exports.hide_message_expander = function (row) {
    if (row.find(".could-be-condensed").length !== 0) {
        row.find(".message_expander").hide();
    }
};

exports.show_message_expander = function (row) {
    if (row.find(".could-be-condensed").length !== 0) {
        row.find(".message_expander").show();
    }
};

exports.condense_and_collapse = function (elems) {
    var height_cutoff = message_viewport.height() * 0.65;

    _.each(elems, function (elem) {
        var content = $(elem).find(".message_content");
        var message = current_msg_list.get(rows.id($(elem)));
        if (content !== undefined && message !== undefined) {
            var message_height = get_message_height(elem, message.id);
            var long_message = message_height > height_cutoff;
            if (long_message) {
                // All long messages are flagged as such.
                content.addClass("could-be-condensed");
            } else {
                content.removeClass("could-be-condensed");
            }

            // If message.condensed is defined, then the user has manually
            // specified whether this message should be expanded or condensed.
            if (message.condensed === true) {
                condense_row($(elem));
                return;
            } else if (message.condensed === false) {
                uncondense_row($(elem));
                return;
            } else if (long_message) {
                // By default, condense a long message.
                condense_row($(elem));
            } else {
                content.removeClass('condensed');
                $(elem).find(".message_expander").hide();
            }

            // Completely hide the message and replace it with a [More]
            // link if the user has collapsed it.
            if (message.collapsed) {
                content.addClass("collapsed");
                $(elem).find(".message_expander").show();
            }
        }
    });
};

$(function () {
    $("#home").on("click", ".message_expander", function () {
        // Expanding a message can mean either uncollapsing or
        // uncondensing it.
        var row = $(this).closest(".message_row");
        var message = current_msg_list.get(rows.id(row));
        var content = row.find(".message_content");
        if (message.collapsed) {
            // Uncollapse.
            exports.uncollapse(row);
        } else if (content.hasClass("condensed")) {
            // Uncondense (show the full long message).
            message.condensed = false;
            content.removeClass("condensed");
            $(this).hide();
            row.find(".message_condenser").show();
        }
    });

    $("#home").on("click", ".message_condenser", function () {
        var row = $(this).closest(".message_row");
        current_msg_list.get(rows.id(row)).condensed = true;
        condense_row(row);
    });
});

return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = condense;
}
