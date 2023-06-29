import $ from "jquery";

import render_search_list_item from "../templates/search_list_item.hbs";

import {Filter} from "./filter";
import * as keydown_util from "./keydown_util";
import * as message_view_header from "./message_view_header";
import * as search_suggestion from "./search_suggestion";

// Exported for unit testing
export let is_using_input_method = false;

export function narrow_or_search_for_term(search_string, {on_narrow_search}) {
    const $search_query_box = $("#search_query");
    if (is_using_input_method) {
        // Neither narrow nor search when using input tools as
        // `updater` is also triggered when 'enter' is triggered
        // while using input tool
        return $search_query_box.val();
    }

    const operators = Filter.parse(search_string);
    on_narrow_search(operators, {trigger: "search"});

    // It's sort of annoying that this is not in a position to
    // blur the search box, because it means that Esc won't
    // unnarrow, it'll leave the searchbox.

    // Narrowing will have already put some operators in the search box,
    // so leave the current text in.
    $search_query_box.trigger("blur");
    return $search_query_box.val();
}

export function initialize({on_narrow_search}) {
    const $search_query_box = $("#search_query");
    const $searchbox_form = $("#searchbox_form");

    // Data storage for the typeahead.
    // This maps a search string to an object with a "description_html" field.
    // (It's a bit of legacy that we have an object with only one important
    // field.  There's also a "search_string" field on each element that actually
    // just represents the key of the hash, so it's redundant.)
    let search_map = new Map();

    $search_query_box.typeahead({
        source(query) {
            const suggestions = search_suggestion.get_suggestions(query);
            // Update our global search_map hash
            search_map = suggestions.lookup_table;
            return suggestions.strings;
        },
        parentElement: "#searchbox",
        items: search_suggestion.max_num_of_search_results,
        helpOnEmptyStrings: true,
        naturalSearch: true,
        highlighter(item) {
            const obj = search_map.get(item);
            return render_search_list_item(obj);
        },
        matcher() {
            return true;
        },
        updater(search_string) {
            return narrow_or_search_for_term(search_string, {on_narrow_search});
        },
        sorter(items) {
            return items;
        },
        advanceKeyCodes: [8],

        // Use our custom typeahead `on_escape` hook to exit
        // the search bar as soon as the user hits Esc.
        on_escape: message_view_header.exit_search,
    });

    $searchbox_form.on("compositionend", () => {
        // Set `is_using_input_method` to true if Enter is pressed to exit
        // the input tool popover and get the text in the search bar. Then
        // we suppress searching triggered by this Enter key by checking
        // `is_using_input_method` before searching.
        // More details in the commit message that added this line.
        is_using_input_method = true;
    });

    $searchbox_form
        .on("keydown", (e) => {
            if (keydown_util.is_enter_event(e) && $search_query_box.is(":focus")) {
                // Don't submit the form so that the typeahead can instead
                // handle our Enter keypress. Any searching that needs
                // to be done will be handled in the keyup.
                e.preventDefault();
            }
        })
        .on("keyup", (e) => {
            if (is_using_input_method) {
                is_using_input_method = false;
                return;
            }

            if (keydown_util.is_enter_event(e) && $search_query_box.is(":focus")) {
                // We just pressed Enter and the box had focus, which
                // means we didn't use the typeahead at all.  In that
                // case, we should act as though we're searching by
                // operators.  (The reason the other actions don't call
                // this codepath is that they first all blur the box to
                // indicate that they've done what they need to do)

                // Pill is already added during keydown event of input pills.
                narrow_or_search_for_term($search_query_box.val(), {on_narrow_search});
                $search_query_box.trigger("blur");
            }
        });
}

export function initiate_search() {
    message_view_header.open_search_bar_and_close_narrow_description();
    $("#search_query").typeahead("lookup").trigger("select");
}

export function clear_search_form() {
    $("#search_query").val("");
    $("#search_query").trigger("blur");
}
