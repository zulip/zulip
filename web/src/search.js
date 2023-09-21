import $ from "jquery";

import render_search_list_item from "../templates/search_list_item.hbs";

import {Filter} from "./filter";
import * as keydown_util from "./keydown_util";
import * as narrow_state from "./narrow_state";
import * as popovers from "./popovers";
import * as search_pill from "./search_pill";
import * as search_suggestion from "./search_suggestion";

// Exported for unit testing
export let is_using_input_method = false;
export let search_pill_widget = null;
let search_input_has_changed = false;

export function set_search_bar_text(text) {
    $("#search_query").text(text);
}

function get_search_bar_text() {
    return $("#search_query").text();
}

function narrow_or_search_for_term({on_narrow_search}) {
    if (is_using_input_method) {
        // Neither narrow nor search when using input tools as
        // `updater` is also triggered when 'enter' is triggered
        // while using input tool
        return get_search_bar_text();
    }

    const search_query = search_pill.get_search_string_for_current_filter(search_pill_widget);
    if (search_query === "") {
        exit_search({keep_search_narrow_open: true});
        return "";
    }
    const operators = Filter.parse(search_query);
    on_narrow_search(operators, {trigger: "search"});

    // It's sort of annoying that this is not in a position to
    // blur the search box, because it means that Esc won't
    // unnarrow, it'll leave the searchbox.

    // Narrowing will have already put some operators in the search box,
    // so leave the current text in.
    $("#search_query").trigger("blur");
    return get_search_bar_text();
}

export function initialize({on_narrow_search}) {
    const $search_query_box = $("#search_query");
    const $searchbox_form = $("#searchbox_form");
    const $pill_container = $("#searchbox-input-container.pill-container");

    search_pill_widget = search_pill.create_pills($pill_container);
    search_pill_widget.onPillCreate(() => {
        $search_query_box.trigger("focus");
    });

    // Data storage for the typeahead.
    // This maps a search string to an object with a "description_html" field.
    // (It's a bit of legacy that we have an object with only one important
    // field.  There's also a "search_string" field on each element that actually
    // just represents the key of the hash, so it's redundant.)
    let search_map = new Map();

    $search_query_box.typeahead({
        source(query) {
            if (query !== "") {
                search_input_has_changed = true;
            }
            const suggestions = search_suggestion.get_suggestions(query);
            // Update our global search_map hash
            search_map = suggestions.lookup_table;
            const existing_pill_strings = new Set(
                search_pill_widget.items().map((item) => item.display_value),
            );
            return suggestions.strings.filter(
                (suggestion) => !existing_pill_strings.has(suggestion),
            );
        },
        parentElement: "#searchbox_form",
        items: search_suggestion.max_num_of_search_results,
        helpOnEmptyStrings: true,
        stopAdvance: true,
        allowNoHighlight: true,
        highlighter(item) {
            const obj = search_map.get(item);
            return render_search_list_item(obj);
        },
        // When the user starts typing new search operands,
        // we want to highlight the first typeahead row by default
        // so that pressing Enter creates the default pill.
        // But when user isn't in the middle of typing a new pill,
        // pressing Enter should let them search for what's currently
        // in the search bar, so we remove the highlight (so that
        // Enter won't have anything to select).
        shouldHighlightFirstResult() {
            return get_search_bar_text() !== "";
        },
        matcher() {
            return true;
        },
        updater(search_string) {
            if (search_string) {
                search_input_has_changed = true;
                search_pill.append_search_string(search_string, search_pill_widget);
            }
            return get_search_bar_text();
        },
        sorter(items) {
            return items;
        },
        advanceKeyCodes: [8],

        // Use our custom typeahead `on_escape` hook to exit
        // the search bar as soon as the user hits Esc.
        on_escape: () => exit_search({keep_search_narrow_open: false}),
        tabIsEnter: false,
        openInputFieldOnKeyUp() {
            if ($(".navbar-search.expanded").length === 0) {
                open_search_bar_and_close_narrow_description();
            }
        },
        // This is here so that we can close the search bar
        // when a user opens it and immediately changes their
        // mind and clicks away.
        closeInputFieldOnHide() {
            if (!search_input_has_changed) {
                const filter = narrow_state.filter();
                if (!filter || filter.is_common_narrow()) {
                    close_search_bar_and_open_narrow_description();
                }
            }
        },
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

            if (e.key === "Escape" && $search_query_box.is(":focus")) {
                exit_search({keep_search_narrow_open: false});
            } else if (keydown_util.is_enter_event(e) && $search_query_box.is(":focus")) {
                narrow_or_search_for_term({on_narrow_search});
            }
        });

    // We don't want to make this a focus handler because selecting the
    // typehead seems to trigger this (and we don't want to open search
    // when an option is selected and we're closing search).
    // Instead we explicitly initiate search on click and on specific keyboard
    // shortcuts.
    $search_query_box.on("click", (e) => {
        if ($(e.target).parents(".navbar-search.expanded").length === 0) {
            initiate_search();
        }
    });

    $(".search_icon").on("mousedown", (e) => {
        e.preventDefault();
        // Clicking on the collapsed search box's icon opens search, but
        // clicking on the expanded search box's search icon does nothing.
        if ($(e.target).parents(".navbar-search.expanded").length === 0) {
            initiate_search();
        }
    });

    // register searchbar click handler
    $("#search_exit").on("click", (e) => {
        exit_search({keep_search_narrow_open: false});
        e.preventDefault();
        e.stopPropagation();
    });
    $("#search_exit").on("blur", (e) => {
        // Blurs that move focus to elsewhere within the search input shouldn't
        // close search.
        if ($(e.relatedTarget).parents("#searchbox-input-container").length > 0) {
            return;
        }
        // But otherwise, it should behave like the input blurring.
        $("#search_query").trigger("blur");
    });
    // This prevents a bug where tab shows a visual change before the blur handler kicks in
    $("#search_exit").on("keydown", (e) => {
        if (e.key === "tab") {
            popovers.hide_all();
            exit_search({keep_search_narrow_open: false});
            e.preventDefault();
            e.stopPropagation();
        }
    });
}

export function initiate_search() {
    open_search_bar_and_close_narrow_description();

    // Open the typeahead after opening the search bar, so that we don't
    // get a weird visual jump where the typeahead results are narrow
    // before the search bar expands and then wider it expands.

    // TODO: this doesn't work because "select" doesn't work for
    // contentedible fields.
    $("#search_query").typeahead("lookup").trigger("select");
}

export function clear_search_form() {
    set_search_bar_text("");
    $("#search_query").trigger("blur");
}

// we rely entirely on this function to ensure
// the searchbar has the right text/pills.
function reset_searchbox() {
    set_search_bar_text("");
    search_pill_widget.clear(true);
    search_input_has_changed = false;
    for (const operator of narrow_state.operators()) {
        const search_string = Filter.unparse([operator]);
        search_pill.append_search_string(search_string, search_pill_widget);
    }
}

function exit_search(opts) {
    const filter = narrow_state.filter();
    if (!filter || filter.is_common_narrow()) {
        // for common narrows, we change the UI (and don't redirect)
        close_search_bar_and_open_narrow_description();
    } else if (opts.keep_search_narrow_open) {
        // If the user is in a search narrow and we don't want to redirect,
        // we just keep the search bar open and don't do anything.
        return;
    } else {
        window.location.href = filter.generate_redirect_url();
    }
    $("#search_query").trigger("blur");
    $(".app").trigger("focus");
}

export function open_search_bar_and_close_narrow_description() {
    // Preserve user input if they've already started typing, but
    // otherwise fill the input field with the text operators for
    // the current narrow.
    if (get_search_bar_text() === "") {
        reset_searchbox();
    }
    $(".navbar-search").addClass("expanded");
    $("#message_view_header").addClass("hidden");
    popovers.hide_all();
}

export function close_search_bar_and_open_narrow_description() {
    // Hide the dropdown before closing the search bar. We do this
    // to avoid being in a situation where the typeahead gets narrow
    // in width as the search bar closes, which doesn't look great.
    $("#searchbox_form .dropdown-menu").hide();

    if (search_pill_widget) {
        search_pill_widget.clear(true);
    }

    $(".navbar-search").removeClass("expanded");
    $("#message_view_header").removeClass("hidden");

    if ($("#search_query").is(":focus")) {
        $("#search_query").trigger("blur");
        $(".app").trigger("focus");
    }
}
