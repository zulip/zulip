/*
This library implements two related, similar concepts:

- condensing, i.e. cutting off messages taller than about a half
  screen so that they aren't distractingly tall (and offering a button
  to uncondense them).

- Collapsing, i.e. taking a message and reducing its height to a
  single line, with a button to see the content.

*/

/*


    This modules solves two closely-related problems:

    * Some messages are **too tall**.  They take up
      two much space on the screen and we want to
      **condense** them for users.

    * Some messages are **annoying**.  This can be
      due to spam, mixes, animated gifs, etc., and
      this can apply to both short and tall messages.
      We allow users to **collapse** them.

    There are three different states for a message:

        COLLAPSED - show none of the message
        CONDENSED - show up to N pixels of the message
        NORMAL - show whole message

    For NORMAL messages that are tall, we show this link:

        [Condense this message]

    For COLLAPSED or CONDENSED messages, we show this link

        [More...]

    We have a hotkey (`-`) that toggles messages:

        Short messages:

            NORMAL -> COLLASED -> repeat cycle

        Tall messages:

            NORMAL -> CONDENSED -> COLLASED -> repeat cycle

    In the message menu, we have two options:

        * Collapse (will either condense or collapse)
        * Un-collapse (will go back to NORMAL)

    (Todo: we may want to change the wording from "Collapse"
    to "Condense" when tall messages are displayed normally.)

    The user's view of the world are controlled by these
    HTML elements:

        .messagebox-content .collapsed -> causes CSS to hide it
        .messagebox-content .condensed -> causes CSS to set max height
        .message_condenser -> link for "[Condense this message]"
        .message_expander -> link for "More..."

    For view stuff we use these three methods:

        show_row_as_collapsed
        show_row_as_condensed
        show_row_as_normal

    These are wrapped by bigger methods which update
    any data elements, as well as updating the row in
    our "home" view:

        move_to_collapsed_state
        move_to_condensed_state
        move_from_collapsed_to_normal_state

    There are three flags on the `message` data object:

        is_tall
        condensed
        collapsed

    Note that `collapsed` is a server-side concept.  The
    other two flags are more transient client-side concepts.

    The `message.is_tall` flag is particularly sensitive to
    screen dimensions, so we clear it during resize events.

    Finally, the most important method here is the following:

        exports.condense_and_collapse

    This method goes through all message row elements in a
    particular message list and updates their views.  It also
    calculates `message.is_tall` on a "lazy" basis.
*/


exports.clear_message_content_height_cache = function () {
    message_store.each(function (message) {
        message.is_tall = undefined;
    });
};

exports.un_cache_message_content_height = function (message_id) {
    message_store.get(message_id).is_tall = undefined;
};

function get_height_cutoff() {
    const height_cutoff = message_viewport.height() * 0.65;
    return height_cutoff;
}

function get_message(row) {
    const message_id = rows.id(row);
    return message_store.get(message_id);
}

exports.start_edit = function (row) {
    row.find(".messagebox-content").removeClass("condensed");
    row.find(".messagebox-content").removeClass("collapsed");
    row.find(".message_condenser").hide();
    row.find(".message_expander").hide();
};

function show_row_as_collapsed(row) {
    row.find(".messagebox-content").removeClass("condensed");
    row.find(".messagebox-content").addClass("collapsed");
    row.find(".message_condenser").hide();
    row.find(".message_expander").show();
}

function show_row_as_condensed(row) {
    row.find(".messagebox-content").addClass("condensed");
    row.find(".messagebox-content").removeClass("collapsed");
    row.find(".message_condenser").hide();
    row.find(".message_expander").show();
}

function show_row_as_normal(row) {
    row.find(".messagebox-content").removeClass("condensed");
    row.find(".messagebox-content").removeClass("collapsed");
    row.find(".message_expander").hide();

    const message = get_message(row);
    row.find(".message_condenser").toggle(message.is_tall);
}

function get_home_row(row) {
    return home_msg_list.get_row(rows.id(row));
}

exports.move_to_condensed_state = function (row) {
    const message = get_message(row);

    message.condensed = true;

    show_row_as_condensed(row);
    show_row_as_condensed(get_home_row(row));
};

exports.move_to_collapsed_state = function (row) {
    const message = get_message(row);

    if (message.locally_echoed) {
        // Trying to collapse a locally echoed message is
        // very rare, and in our current implementation the
        // server response overwrites the flag, so we just
        // punt for now.
        return;
    }

    message.collapsed = true;
    message_flags.save_collapsed(message);

    show_row_as_collapsed(row);
    show_row_as_collapsed(get_home_row(row));
};

exports.move_from_collapsed_to_normal_state = function (row) {
    const message = get_message(row);

    if (message.locally_echoed) {
        return;
    }

    message.collapsed = false;
    message.condensed = false;
    message_flags.save_uncollapsed(message);

    show_row_as_normal(row);
    show_row_as_normal(get_home_row(row));
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

    // We always try to make the message smaller, unless
    // we are completely collased--and then we go back
    // to the tallest, aka normal, state.
    if (message.collapsed) {
        exports.move_from_collapsed_to_normal_state(row);
        return;
    }

    if (message.condensed) {
        exports.move_to_collapsed_state(row);
        return;
    }

    if (message.is_tall) {
        exports.move_to_condensed_state(row);
        return;
    }

    // Short messages go straight to collapsed state.
    exports.move_to_collapsed_state(row);
};

exports.condense_and_collapse = function (elems) {
    const height_cutoff = get_height_cutoff();

    _.each(elems, function (elem) {
        exports._redraw_elem(elem, height_cutoff);
    });
};

exports._redraw_elem = function (elem, height_cutoff) {
    const row = $(elem);
    const message = get_message(row);
    if (message === undefined) {
        return;
    }

    if (message.condensed) {
        show_row_as_condensed(row);
        return;
    }

    if (message.collapsed) {
        show_row_as_collapsed(row);
        return;
    }

    if (message.is_tall === undefined) {
        if (elem.offsetHeight === 0) {
            // If our callers are feeding us rows from some
            // hidden view, it's just wasteful.
            blueslip.warn('We are trying to redraw zero-size rows.');
            return;
        }

        message.is_tall = elem.offsetHeight > height_cutoff;

        if (message.is_tall) {
            message.condensed = true;
            show_row_as_condensed(row);
            return;
        }
    }

    show_row_as_normal(row);
};

exports.initialize = function () {
    $("#home").on("click", ".message_expander", function () {
        const row = $(this).closest(".message_row");
        exports.move_from_collapsed_to_normal_state(row);
    });

    $("#home").on("click", ".message_condenser", function () {
        const row = $(this).closest(".message_row");
        exports.move_to_condensed_state(row);
    });
};

window.condense = exports;
