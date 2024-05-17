import $ from "jquery";
import assert from "minimalistic-assert";

import render_search_list_item from "../templates/search_list_item.hbs";

import {Typeahead} from "./bootstrap_typeahead";
import type {TypeaheadInputElement} from "./bootstrap_typeahead";
import {Filter} from "./filter";
import * as keydown_util from "./keydown_util";
import * as narrow_state from "./narrow_state";
import * as popovers from "./popovers";
import * as search_suggestion from "./search_suggestion";
import type {NarrowTerm} from "./state_data";

// Exported for unit testing
export let is_using_input_method = false;

let search_typeahead: Typeahead<string>;

export function set_search_bar_text(text: string): void {
    $("#search_query").val(text);
}

function get_search_bar_text(): string {
    const val = $<HTMLInputElement>("#search_query").val();
    assert(val !== undefined);
    return val;
}

// TODO/typescript: Add the rest of the options when converting narrow.js to typescript.
type NarrowSearchOptions = {
    trigger: string;
};

type OnNarrowSearch = (terms: NarrowTerm[], options: NarrowSearchOptions) => void;

function narrow_or_search_for_term(
    search_string: string,
    {on_narrow_search}: {on_narrow_search: OnNarrowSearch},
): string {
    if (search_string === "") {
        exit_search({keep_search_narrow_open: true});
        return "";
    }
    const $search_query_box = $("#search_query");
    if (is_using_input_method) {
        // Neither narrow nor search when using input tools as
        // `updater` is also triggered when 'enter' is triggered
        // while using input tool
        return get_search_bar_text();
    }

    const terms = Filter.parse(search_string);
    on_narrow_search(terms, {trigger: "search"});

    // It's sort of annoying that this is not in a position to
    // blur the search box, because it means that Esc won't
    // unnarrow, it'll leave the searchbox.

    // Narrowing will have already put some terms in the search box,
    // so leave the current text in.
    $search_query_box.trigger("blur");
    return get_search_bar_text();
}

export function initialize({on_narrow_search}: {on_narrow_search: OnNarrowSearch}): void {
    const $search_query_box = $<HTMLInputElement>("#search_query");
    const $searchbox_form = $("#searchbox_form");

    // Data storage for the typeahead.
    // This maps a search string to an object with a "description_html" field.
    // (It's a bit of legacy that we have an object with only one important
    // field.  There's also a "search_string" field on each element that actually
    // just represents the key of the hash, so it's redundant.)
    let search_map = new Map<string, search_suggestion.Suggestion>();

    const bootstrap_typeahead_input: TypeaheadInputElement = {
        $element: $search_query_box,
        type: "input",
    };
    search_typeahead = new Typeahead(bootstrap_typeahead_input, {
        source(query: string): string[] {
            const suggestions = search_suggestion.get_suggestions(query);
            // Update our global search_map hash
            search_map = suggestions.lookup_table;
            return suggestions.strings;
        },
        parentElement: "#searchbox_form",
        items: search_suggestion.max_num_of_search_results,
        helpOnEmptyStrings: true,
        naturalSearch: true,
        highlighter_html(item: string): string {
            const obj = search_map.get(item);
            return render_search_list_item(obj);
        },
        matcher(): boolean {
            return true;
        },
        updater(search_string: string): string {
            return narrow_or_search_for_term(search_string, {on_narrow_search});
        },
        sorter(items: string[]): string[] {
            return items;
        },
        advanceKeyCodes: [8],

        // Use our custom typeahead `on_escape` hook to exit
        // the search bar as soon as the user hits Esc.
        on_escape() {
            exit_search({keep_search_narrow_open: false});
        },
        tabIsEnter: false,
        openInputFieldOnKeyUp(): void {
            if ($(".navbar-search.expanded").length === 0) {
                open_search_bar_and_close_narrow_description();
            }
        },
        closeInputFieldOnHide(): void {
            // Don't close the search bar if the user has changed
            // the text from the default, they might accidentally
            // click away and not want to lose it.
            if (get_initial_search_string() !== get_search_bar_text()) {
                return;
            }
            const filter = narrow_state.filter();
            if (!filter || filter.is_common_narrow()) {
                close_search_bar_and_open_narrow_description();
            }
        },
    });

    $searchbox_form.on("compositionend", (): void => {
        // Set `is_using_input_method` to true if Enter is pressed to exit
        // the input tool popover and get the text in the search bar. Then
        // we suppress searching triggered by this Enter key by checking
        // `is_using_input_method` before searching.
        // More details in the commit message that added this line.
        is_using_input_method = true;
    });

    $searchbox_form
        .on("keydown", (e: JQuery.KeyDownEvent): void => {
            if (keydown_util.is_enter_event(e) && $search_query_box.is(":focus")) {
                // Don't submit the form so that the typeahead can instead
                // handle our Enter keypress. Any searching that needs
                // to be done will be handled in the keyup.
                e.preventDefault();
            }
        })
        .on("keyup", (e: JQuery.KeyUpEvent): void => {
            if (is_using_input_method) {
                is_using_input_method = false;
                return;
            }

            if (keydown_util.is_enter_event(e) && $search_query_box.is(":focus")) {
                // We just pressed Enter and the box had focus, which
                // means we didn't use the typeahead at all.  In that
                // case, we should act as though we're searching by
                // terms.  (The reason the other actions don't call
                // this codepath is that they first all blur the box to
                // indicate that they've done what they need to do)

                // Pill is already added during keydown event of input pills.
                narrow_or_search_for_term(get_search_bar_text(), {on_narrow_search});
                $search_query_box.trigger("blur");
            }
        });

    // We don't want to make this a focus handler because selecting the
    // typehead seems to trigger this (and we don't want to open search
    // when an option is selected and we're closing search).
    // Instead we explicitly initiate search on click and on specific keyboard
    // shortcuts.
    $search_query_box.on("click", (e: JQuery.ClickEvent): void => {
        if ($(e.target).parents(".navbar-search.expanded").length === 0) {
            initiate_search();
        }
    });

    $(".search_icon").on("mousedown", (e: JQuery.MouseDownEvent): void => {
        e.preventDefault();
        // Clicking on the collapsed search box's icon opens search, but
        // clicking on the expanded search box's search icon does nothing.
        if ($(e.target).parents(".navbar-search.expanded").length === 0) {
            initiate_search();
        }
    });

    // register searchbar click handler
    $("#search_exit").on("click", (e: JQuery.ClickEvent): void => {
        exit_search({keep_search_narrow_open: false});
        e.preventDefault();
        e.stopPropagation();
    });
    $("#search_exit").on("blur", (e: JQuery.BlurEvent): void => {
        // Blurs that move focus to elsewhere within the search input shouldn't
        // close search.
        const related_target = e.relatedTarget;
        if (related_target && $(related_target).parents("#searchbox-input-container").length > 0) {
            return;
        }
        // But otherwise, it should behave like the input blurring.
        $("#search_query").trigger("blur");
    });
    // This prevents a bug where tab shows a visual change before the blur handler kicks in
    $("#search_exit").on("keydown", (e: JQuery.KeyDownEvent): void => {
        if (e.key === "tab") {
            popovers.hide_all();
            exit_search({keep_search_narrow_open: false});
            e.preventDefault();
            e.stopPropagation();
        }
    });
}

export function initiate_search(): void {
    open_search_bar_and_close_narrow_description();

    // Open the typeahead after opening the search bar, so that we don't
    // get a weird visual jump where the typeahead results are narrow
    // before the search bar expands and then wider it expands.
    search_typeahead.lookup(false);
    $("#search_query").trigger("select");
}

// This is what the default searchbox text would be for this narrow,
// NOT what might be currently displayed there. We can use this both
// to set the initial text and to see if the user has changed it.
function get_initial_search_string(): string {
    let search_string = narrow_state.search_string();
    if (search_string !== "" && !narrow_state.filter()?.is_keyword_search()) {
        // saves the user a keystroke for quick searches
        search_string = search_string + " ";
    }
    return search_string;
}

// we rely entirely on this function to ensure
// the searchbar has the right text.
function reset_searchbox_text(): void {
    set_search_bar_text(get_initial_search_string());
}

function exit_search(opts: {keep_search_narrow_open: boolean}): void {
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

export function open_search_bar_and_close_narrow_description(): void {
    // Preserve user input if they've already started typing, but
    // otherwise fill the input field with the text terms for
    // the current narrow.
    if (get_search_bar_text() === "") {
        reset_searchbox_text();
    }
    $(".navbar-search").addClass("expanded");
    $("#message_view_header").addClass("hidden");
    popovers.hide_all();
}

export function close_search_bar_and_open_narrow_description(): void {
    // Hide the dropdown before closing the search bar. We do this
    // to avoid being in a situation where the typeahead gets narrow
    // in width as the search bar closes, which doesn't look great.
    $("#searchbox_form .dropdown-menu").hide();

    set_search_bar_text("");
    $(".navbar-search").removeClass("expanded");
    $("#message_view_header").removeClass("hidden");
}
