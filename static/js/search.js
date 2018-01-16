var search = (function () {

var exports = {};

function narrow_or_search_for_term(search_string) {
    var search_query_box = $("#search_query");
    ui_util.change_tab_to('#home');
    var operators = Filter.parse(search_string);
    narrow.activate(operators, {trigger: 'search'});

    // It's sort of annoying that this is not in a position to
    // blur the search box, because it means that Esc won't
    // unnarrow, it'll leave the searchbox.

    // Narrowing will have already put some operators in the search box,
    // so leave the current text in.
    search_query_box.blur();
    return search_query_box.val();
}

function update_buttons_with_focus(focused) {
    var search_query = $('#search_query');

    // Show buttons iff the search input is focused, or has non-empty contents,
    // or we are narrowed.
    if (focused
        || search_query.val()
        || narrow_state.active()) {
        $('.search_button').prop('disabled', false);
    } else {
        $('.search_button').attr('disabled', 'disabled');
    }
}

exports.update_button_visibility = function () {
    update_buttons_with_focus($('#search_query').is(':focus'));
};

exports.initialize = function () {

    // Data storage for the typeahead.
    // This maps a search string to an object with a "description" field.
    // (It's a bit of legacy that we have an object with only one important
    // field.  There's also a "search_string" field on each element that actually
    // just represents the key of the hash, so it's redundant.)
    var search_object = {};

    $("#search_query").typeahead({
        source: function (query) {
            var suggestions = search_suggestion.get_suggestions(query);
            // Update our global search_object hash
            search_object = suggestions.lookup_table;
            return suggestions.strings;
        },
        fixed: true,
        items: 12,
        helpOnEmptyStrings: true,
        naturalSearch: true,
        highlighter: function (item) {
            var obj = search_object[item];
            return obj.description;
        },
        matcher: function () {
            return true;
        },
        updater: narrow_or_search_for_term,
        sorter: function (items) {
            return items;
        },
    });

    $("#searchbox_form").keydown(function (e) {
        exports.update_button_visibility();
        var code = e.which;
        var search_query_box = $("#search_query");
        if (code === 13 && search_query_box.is(":focus")) {
            // Don't submit the form so that the typeahead can instead
            // handle our Enter keypress. Any searching that needs
            // to be done will be handled in the keyup.
            e.preventDefault();
            return false;
        }
    }).keyup(function (e) {
        var code = e.which;
        var search_query_box = $("#search_query");
        if (code === 13 && search_query_box.is(":focus")) {
            // We just pressed enter and the box had focus, which
            // means we didn't use the typeahead at all.  In that
            // case, we should act as though we're searching by
            // operators.  (The reason the other actions don't call
            // this codepath is that they first all blur the box to
            // indicate that they've done what they need to do)
            narrow.activate(Filter.parse(search_query_box.val()), {trigger: 'search'});
            search_query_box.blur();
            update_buttons_with_focus(false);
        }
    });

    // Some of these functions don't actually need to be exported,
    // but the code was moved here from elsewhere, and it would be
    // more work to re-order everything and make them private.
    $('#search_exit').on('click', exports.clear_search);

    var query = $('#search_query');
    query.on('focus', exports.focus_search)
         .on('blur' , function () {

        // The search query box is a visual cue as to
        // whether search or narrowing is active.  If
        // the user blurs the search box, then we should
        // update the search string to reflect the currect
        // narrow (or lack of narrow).
        //
        // But we can't do this right away, because
        // selecting something in the typeahead menu causes
        // the box to lose focus a moment before.
        //
        // The workaround is to check 100ms later -- long
        // enough for the search to have gone through, but
        // short enough that the user won't notice (though
        // really it would be OK if they did).

        setTimeout(function () {
            var search_string = narrow_state.search_string();
            query.val(search_string);
            exports.update_button_visibility();
        }, 100);
    });
};

exports.focus_search = function () {
    // The search bar is not focused yet, but will be.
    update_buttons_with_focus(true);
};

exports.initiate_search = function () {
    $('#search_query').select();
};

exports.clear_search = function () {
    narrow.deactivate();

    $('#search_query').blur();
    exports.update_button_visibility();
};

return exports;

}());
if (typeof module !== 'undefined') {
    module.exports = search;
}
