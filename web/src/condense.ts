import $ from "jquery";
import assert from "minimalistic-assert";

import * as message_flags from "./message_flags";
import * as message_lists from "./message_lists";
import type {Message} from "./message_store";
import * as message_viewport from "./message_viewport";
import * as rows from "./rows";

/*
This library implements two related, similar concepts:

- condensing, i.e. cutting off messages taller than about a half
  screen so that they aren't distractingly tall (and offering a button
  to uncondense them).

- Collapsing, i.e. taking a message and reducing its height to a
  single line, with a button to see the content.

*/

function show_more_link($row: JQuery): void {
    $row.find(".message_condenser").hide();
    $row.find(".message_expander").show();
}

function show_condense_link($row: JQuery): void {
    $row.find(".message_expander").hide();
    $row.find(".message_condenser").show();
}

function condense_row($row: JQuery): void {
    const $content = $row.find(".message_content");
    $content.addClass("condensed");
    show_more_link($row);
}

function uncondense_row($row: JQuery): void {
    const $content = $row.find(".message_content");
    $content.removeClass("condensed");
    show_condense_link($row);
}

export function uncollapse(message: Message): void {
    // Uncollapse a message, restoring the condensed message "Show more" or
    // "Show less" button if necessary.
    message.collapsed = false;
    message_flags.save_uncollapsed(message);

    const process_row = function process_row($row: JQuery): void {
        const $content = $row.find(".message_content");
        $content.removeClass("collapsed");

        if (message.condensed === true) {
            // This message was condensed by the user, so re-show the
            // "Show more" button.
            condense_row($row);
        } else if (message.condensed === false) {
            // This message was un-condensed by the user, so re-show the
            // "Show less" button.
            uncondense_row($row);
        } else if ($content.hasClass("could-be-condensed")) {
            // By default, condense a long message.
            condense_row($row);
        } else {
            // This was a short message, no more need for a [More] link.
            $row.find(".message_expander").hide();
        }
    };

    for (const list of message_lists.all_rendered_message_lists()) {
        const $rendered_row = list.get_row(message.id);
        if ($rendered_row.length !== 0) {
            process_row($rendered_row);
        }
    }
}

export function collapse(message: Message): void {
    message.collapsed = true;

    if (message.locally_echoed) {
        // Trying to collapse a locally echoed message is
        // very rare, and in our current implementation the
        // server response overwrites the flag, so we just
        // punt for now.
        return;
    }

    message_flags.save_collapsed(message);

    const process_row = function process_row($row: JQuery): void {
        $row.find(".message_content").addClass("collapsed");
        show_more_link($row);
    };

    for (const list of message_lists.all_rendered_message_lists()) {
        const $rendered_row = list.get_row(message.id);
        if ($rendered_row.length !== 0) {
            process_row($rendered_row);
        }
    }
}

export function toggle_collapse(message: Message): void {
    if (message.is_me_message) {
        // Disabled temporarily because /me messages don't have a
        // styling for collapsing /me messages (they only recently
        // added multi-line support).  See also popover_menus_data.js.
        return;
    }

    // This function implements a multi-way toggle, to try to do what
    // the user wants for messages:
    //
    // * If the message is currently showing any "Show more" button, either
    //   because it was previously condensed or collapsed, fully display it.
    // * If the message is fully visible, either because it's too short to
    //   condense or because it's already uncondensed, collapse it

    assert(message_lists.current !== undefined);
    const $row = message_lists.current.get_row(message.id);
    if (!$row) {
        return;
    }

    const $content = $row.find(".message_content");
    const is_condensable = $content.hasClass("could-be-condensed");
    const is_condensed = $content.hasClass("condensed");
    if (message.collapsed) {
        if (is_condensable) {
            message.condensed = true;
            $content.addClass("condensed");
            show_message_expander($row);
            $row.find(".message_condenser").hide();
        }
        uncollapse(message);
    } else {
        if (is_condensed) {
            message.condensed = false;
            $content.removeClass("condensed");
            hide_message_expander($row);
            $row.find(".message_condenser").show();
        } else {
            collapse(message);
        }
    }
}

function get_message_height(elem: HTMLElement): number {
    // This needs to be very fast. This function runs hundreds of times
    // when displaying a message feed view that has hundreds of message
    // history, which ideally should render in <100ms.
    return $(elem).find(".message_content")[0].scrollHeight;
}

export function hide_message_expander($row: JQuery): void {
    if ($row.find(".could-be-condensed").length !== 0) {
        $row.find(".message_expander").hide();
    }
}

export function hide_message_condenser($row: JQuery): void {
    if ($row.find(".could-be-condensed").length !== 0) {
        $row.find(".message_condenser").hide();
    }
}

export function show_message_expander($row: JQuery): void {
    if ($row.find(".could-be-condensed").length !== 0) {
        $row.find(".message_expander").show();
    }
}

export function show_message_condenser($row: JQuery): void {
    if ($row.find(".could-be-condensed").length !== 0) {
        $row.find(".message_condenser").show();
    }
}

export function condense_and_collapse(elems: JQuery): void {
    if (message_lists.current === undefined) {
        return;
    }

    const height_cutoff = message_viewport.max_message_height();
    const rows_to_resize = [];

    for (const elem of elems) {
        const $content = $(elem).find(".message_content");

        if ($content.length !== 1) {
            // We could have a "/me did this" message or something
            // else without a `message_content` div.
            continue;
        }

        const message_id = rows.id($(elem));

        if (!message_id) {
            continue;
        }

        const message = message_lists.current.get(message_id);
        if (message === undefined) {
            continue;
        }

        const message_height = get_message_height(elem);

        rows_to_resize.push({
            elem,
            $content,
            message,
            message_height,
        });
    }

    // Note that we resize all the rows *after* we calculate if we should
    // resize them or not. This allows us to do all measurements before
    // changing the layout of the page, which is more performanant.
    // More information here: https://web.dev/avoid-large-complex-layouts-and-layout-thrashing/#avoid-layout-thrashing
    for (const {elem, $content, message, message_height} of rows_to_resize) {
        const long_message = message_height > height_cutoff;
        if (long_message) {
            // All long messages are flagged as such.
            $content.addClass("could-be-condensed");
        } else {
            $content.removeClass("could-be-condensed");
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
            $content.removeClass("condensed");
            $(elem).find(".message_expander").hide();
        }

        // Completely hide the message and replace it with a "Show more"
        // button if the user has collapsed it.
        if (message.collapsed) {
            $content.addClass("collapsed");
            $(elem).find(".message_expander").show();
        }
    }
}

export function initialize(): void {
    $("#message_feed_container").on("click", ".message_expander", function (this: HTMLElement, e) {
        // Expanding a message can mean either uncollapsing or
        // uncondensing it.
        const $row = $(this).closest(".message_row");
        const id = rows.id($row);
        assert(message_lists.current !== undefined);
        const message = message_lists.current.get(id);
        assert(message !== undefined);
        // Focus on the expanded message.
        message_lists.current.select_id(id);
        const $content = $row.find(".message_content");
        if (message.collapsed) {
            // Uncollapse.
            uncollapse(message);
        } else if ($content.hasClass("condensed")) {
            // Uncondense (show the full long message).
            message.condensed = false;
            $content.removeClass("condensed");
            $(this).hide();
            $row.find(".message_condenser").show();
        }
        e.stopPropagation();
        e.preventDefault();
    });

    $("#message_feed_container").on("click", ".message_condenser", function (this: HTMLElement, e) {
        const $row = $(this).closest(".message_row");
        const id = rows.id($row);
        // Focus on the condensed message.
        assert(message_lists.current !== undefined);
        message_lists.current.select_id(id);
        const message = message_lists.current.get(id);
        assert(message !== undefined);
        message.condensed = true;
        condense_row($row);
        e.stopPropagation();
        e.preventDefault();
    });
}
