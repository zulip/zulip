"use strict";

/*
This library implements two related, similar concepts:

- condensing, i.e. cutting off messages taller than about a half
  screen so that they aren't distractingly tall (and offering a button
  to uncondense them).

- Collapsing, i.e. taking a message and reducing its height to a
  single line, with a button to see the content.

*/

const _message_content_height_cache = new Map();

function show_more_link(row) {
    row.find(".message_condenser").hide();
    row.find(".message_expander").show();
}

function show_condense_link(row) {
    row.find(".message_expander").hide();
    row.find(".message_condenser").show();
}

function condense_row(row) {
    const content = row.find(".message_content");
    content.addClass("condensed");
    show_more_link(row);
}

function uncondense_row(row) {
    const content = row.find(".message_content");
    content.removeClass("condensed");
    show_condense_link(row);
}

exports.uncollapse = function (row) {
    // Uncollapse a message, restoring the condensed message [More] or
    // [Condense] link if necessary.
    const message = current_msg_list.get(rows.id(row));
    message.collapsed = false;
    message_flags.save_uncollapsed(message);

    const process_row = function process_row(row) {
        const content = row.find(".message_content");
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
    const home_row = home_msg_list.get_row(rows.id(row));

    process_row(row);
    process_row(home_row);
};

exports.collapse = function (row) {
    // Collapse a message, hiding the condensed message [More] or
    // [Condense] link if necessary.
    const message = current_msg_list.get(rows.id(row));
    message.collapsed = true;

    if (message.locally_echoed) {
        // Trying to collapse a locally echoed message is
        // very rare, and in our current implementation the
        // server response overwrites the flag, so we just
        // punt for now.
        return;
    }

    message_flags.save_collapsed(message);

    const process_row = function process_row(row) {
        row.find(".message_content").addClass("collapsed");
        show_more_link(row);
    };

    // We also need to collapse this message in the home view
    const home_row = home_msg_list.get_row(rows.id(row));

    process_row(row);
    process_row(home_row);
};

exports.toggle_collapse = function (message) {
    if (message.is_me_message) {
        // Disabled temporarily because /me messages don't have a
        // styling for collapsing /me messages (they only recently
        // added multi-line support).  See also popovers.js.
        return;
    }

    // This function implements a multi-way toggle, to try to do what
    // the user wants for messages:
    //
    // * If the message is currently showing any [More] link, either
    //   because it was previously condensed or collapsed, fully display it.
    // * If the message is fully visible, either because it's too short to
    //   condense or because it's already uncondensed, collapse it

    const row = current_msg_list.get_row(message.id);
    if (!row) {
        return;
    }

    const content = row.find(".message_content");
    const is_condensable = content.hasClass("could-be-condensed");
    const is_condensed = content.hasClass("condensed");
    if (message.collapsed) {
        if (is_condensable) {
            message.condensed = true;
            content.addClass("condensed");
            exports.show_message_expander(row);
            row.find(".message_condenser").hide();
        }
        exports.uncollapse(row);
    } else {
        if (is_condensed) {
            message.condensed = false;
            content.removeClass("condensed");
            exports.hide_message_expander(row);
            row.find(".message_condenser").show();
        } else {
            exports.collapse(row);
        }
    }
};

exports.clear_message_content_height_cache = function () {
    _message_content_height_cache.clear();
};

exports.un_cache_message_content_height = function (message_id) {
    _message_content_height_cache.delete(message_id);
};

function get_message_height(elem, message_id) {
    if (_message_content_height_cache.has(message_id)) {
        return _message_content_height_cache.get(message_id);
    }

    // shown to be ~2.5x faster than Node.getBoundingClientRect().
    const height = elem.offsetHeight;
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
    const height_cutoff = message_viewport.height() * 0.65;

    for (const elem of elems) {
        const content = $(elem).find(".message_content");

        if (content.length !== 1) {
            // We could have a "/me did this" message or something
            // else without a `message_content` div.
            continue;
        }

        const message_id = rows.id($(elem));

        if (!message_id) {
            continue;
        }

        const message = current_msg_list.get(message_id);
        if (message === undefined) {
            continue;
        }

        const message_height = get_message_height(elem, message.id);
        const long_message = message_height > height_cutoff;
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
            continue;
        }

        if (message.condensed === false) {
            uncondense_row($(elem));
            continue;
        }

        if (long_message) {
            // By default, condense a long message.
            condense_row($(elem));
        } else {
            content.removeClass("condensed");
            $(elem).find(".message_expander").hide();
        }

        // Completely hide the message and replace it with a [More]
        // link if the user has collapsed it.
        if (message.collapsed) {
            content.addClass("collapsed");
            $(elem).find(".message_expander").show();
        }
    }
};

exports.initialize = function () {
    $("#message_feed_container").on("click", ".message_expander", function (e) {
        // Expanding a message can mean either uncollapsing or
        // uncondensing it.
        const row = $(this).closest(".message_row");
        const message = current_msg_list.get(rows.id(row));
        const content = row.find(".message_content");
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
        e.stopPropagation();
        e.preventDefault();
    });

    $("#message_feed_container").on("click", ".message_condenser", function (e) {
        const row = $(this).closest(".message_row");
        current_msg_list.get(rows.id(row)).condensed = true;
        condense_row(row);
        e.stopPropagation();
        e.preventDefault();
    });
};

window.condense = exports;
