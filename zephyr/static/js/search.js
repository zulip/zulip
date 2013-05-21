var search = (function () {

var exports = {};

var cached_term = "";
var cached_matches = [];
var cached_index;
var cached_table = $('table.focused_table');
var current_search_term;

// Data storage for the typeahead -- to go from object to string representation and vice versa.
var labels = [];
var mapped = {};

function get_query(obj) {
    return obj.query;
}

function get_person(obj) {
    return typeahead_helper.render_person(obj.query);
}

function phrase_match(phrase, q) {
    // match "tes" to "test" and "stream test" but not "hostess"
    var i;
    q = q.toLowerCase();

    var parts = phrase.split(' ');
    for (i = 0; i < parts.length; i++) {
        if (parts[i].toLowerCase().indexOf(q) === 0) {
            return true;
        }
    }
    return false;
}

function person_matches_query(person, q) {
    return phrase_match(person.full_name, q) || phrase_match(person.email, q);
}

function stream_matches_query(stream_name, q) {
    return phrase_match(stream_name, q);
}

function render_object_in_parts(obj) {
    // N.B. action is *not* escaped by the caller
    switch (obj.action) {
    case 'stream':
        return {prefix: 'Narrow to stream', query: get_query(obj), suffix: ''};

    case 'private_message':
        return {prefix: 'Narrow to private messages with',
                query: get_person(obj),
                suffix: ''};

    case 'sender':
        return {prefix: 'Narrow to messages sent by',
                query: get_person(obj),
                suffix: ''};

    case 'operators':
        // HACK: This label needs to be distinct from the above, because of the
        // way we identify action objects by their labels.  Using two spaces
        // after 'Narrow to' ensures this, and is invisible with standard HTML
        // whitespace handling.
        return {prefix: '',
                query: narrow.describe(obj.operators),
                suffix: ''};
    }
    return {prefix: 'Error', query: 'Error', suffix: 'Error'};
}

function render_object(obj) {
    var parts = render_object_in_parts(obj);
    return parts.prefix + " " + parts.query + " " + parts.suffix;
}

exports.update_typeahead = function () {
    var stream_names = subs.subscribed_streams();
    stream_names.sort();

    var streams = $.map(stream_names, function(elt,idx) {
        return {action: 'stream', query: elt};
    });

    var people_names = page_params.people_list;

    var people = $.map(people_names, function(elt,idx) {
        return {action: 'private_message', query: elt};
    });
    var senders = $.map(people_names, function(elt,idx) {
        return {action: 'sender', query: elt};
    });

    var options = streams.concat(people).concat(senders);
    // The first slot is reserved for "search for x".
    // (this is updated in the source function for our typeahead as well)
    options.unshift({action: 'operators', query: '', operators: []});

    mapped = {};
    labels = [];
    $.each(options, function (i, obj) {
        var label = render_object(obj);
        mapped[label] = obj;
        labels.push(label);
    });
};

function narrow_or_search_for_term(item) {
    var search_query_box = $("#search_query");
    var obj = mapped[item];
    ui.change_tab_to('#home');
    switch (obj.action) {
    case 'stream':
        narrow.by('stream', obj.query, {trigger: 'search'});
        // It's sort of annoying that this is not in a position to
        // blur the search box, because it means that Esc won't
        // unnarrow, it'll leave the searchbox.

        // Narrowing will have already put some operators in the search box,
        // so leave the current text in.
        search_query_box.blur();
        return search_query_box.val();

    case 'private_message':
        narrow.by('pm-with', obj.query.email, {trigger: 'search'});
        search_query_box.blur();
        return search_query_box.val();

    case 'sender':
        narrow.by('sender', obj.query.email, {trigger: 'search'});
        search_query_box.blur();
        return search_query_box.val();

    case 'operators':
        narrow.activate(obj.operators, {trigger: 'search'});
        search_query_box.blur();
        return search_query_box.val();
    }
    return item;
}

function searchbox_sorter(items) {
    var objects_by_action = {};
    var result = [];

    $.each(items, function (idx, elt) {
        var obj = mapped[elt];
        if (objects_by_action[obj.action] === undefined)
            objects_by_action[obj.action] = [];
        objects_by_action[obj.action].push(obj);
    });

    var query = this.query;
    $.each(['operators', 'private_message', 'sender', 'stream'], function (idx, action) {
        var objs = objects_by_action[action];
        if (!objs)
            return;
        // Get the first object in sorted order.
        if (action === 'private_message' || action === 'sender') {
            objs.sort(function (x, y) {
                return typeahead_helper.compare_by_pms(get_person(x), get_person(y));
            });
        } else if (action !== 'stream') {
            // streams are already sorted
            objs = typeahead_helper.sorter(query, objs, get_query);
        }

        result = result.concat($.map(objs.slice(0, 4), render_object));
    });

    return result;
}

function update_buttons_with_focus(focused) {
    var search_query = $('#search_query');

    // Show buttons iff the search input is focused, or has non-empty contents,
    // or we are narrowed.
    if (focused
        || search_query.val()
        || narrow.active()) {
        $('.search_button').removeAttr('disabled');
    } else {
        $('.search_button').attr('disabled', 'disabled');
    }
}

exports.update_button_visibility = function () {
    update_buttons_with_focus($('#search_query').is(':focus'));
};

function highlight_person(query, person) {
    var hilite = typeahead_helper.highlight_query_in_phrase;
    return hilite(query, person.full_name) + " &lt;" + hilite(query, person.email) + "&gt;";
}

exports.initialize = function () {
    $( "#search_query" ).typeahead({
        source: function (query, process) {
            // Delete our old search queries (one for find-in-page, one for operators)
            delete mapped[labels.shift()]; // Operators

            // Add an entry for narrow by operators.
            var operators = narrow.parse(query);
            var obj = {action: 'operators', query: query, operators: operators};
            var label = render_object(obj);
            mapped[label] = obj;
            labels.unshift(label);

            return labels;
        },
        items: 20,
        highlighter: function (item) {
            var query = this.query;
            var obj = mapped[item];
            var prefix;
            var person;
            var name;
            var stream;

            if (obj.action === 'private_message') {
                prefix = 'Narrow to private messages with';
                person = obj.query;
                name = highlight_person(query, person);
                return prefix + ' ' + name;
            }

            if (obj.action === 'sender') {
                prefix = 'Narrow to messages sent by';
                person = obj.query;
                name = highlight_person(query, person);
                return prefix + ' ' + name;
            }

            if (obj.action === 'stream') {
                prefix = 'Narrow to stream';
                stream = obj.query;
                stream = typeahead_helper.highlight_query_in_phrase(query, stream);
                return prefix + ' ' + stream;
            }

            var parts = render_object_in_parts(obj);
            parts.query = Handlebars.Utils.escapeExpression(parts.query);
            return parts.prefix + " " + parts.query + " " + parts.suffix;
        },
        matcher: function (item) {
            var obj = mapped[item];
            if (obj.disabled)
                return false;
            if (obj.action === 'stream') {
                return stream_matches_query(obj.query, this.query);
            }
            if (obj.action === 'private_message' || obj.action === "sender") {
                return person_matches_query(obj.query, this.query);
            }
            var actual_search_term = obj.query;
            // Case-insensitive (from Bootstrap's default matcher).
            return (actual_search_term.toLowerCase().indexOf(this.query.toLowerCase()) !== -1);
        },
        updater: narrow_or_search_for_term,
        sorter: searchbox_sorter
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
            if (search_query_box.val()) {
                narrow.activate(narrow.parse(search_query_box.val()));
            }
            search_query_box.blur();
            update_buttons_with_focus(false);
        }
    });

    // Some of these functions don't actually need to be exported,
    // but the code was moved here from elsewhere, and it would be
    // more work to re-order everything and make them private.
    $('#search_exit' ).on('click', exports.clear_search);

    var query = $('#search_query');
    query.on('focus', exports.focus_search)
         .on('blur' , function () {

        // The search query box is a visual cue as to
        // whether search or narrowing is active.  If
        // neither is active, we should clear the box on
        // blur.
        //
        // But we can't do this right away, because
        // selecting something in the typeahead menu causes
        // the box to lose focus a moment before.  We would
        // clear the thing we're about to search for.
        //
        // The workaround is to check 100ms later -- long
        // enough for the search to have gone through, but
        // short enough that the user won't notice (though
        // really it would be OK if they did).

        setTimeout(function () {
            if (!(narrow.active())) {
                query.val('');
            }
            exports.update_button_visibility();
        }, 100);
    });
};

function match_on_visible_text(row, search_term) {
    // You can't select on :visible, since that includes hidden elements that
    // take up space.
    return row.find(".message_content, .message_header")
              .text().toLowerCase().indexOf(search_term) !== -1;
}

exports.focus_search = function () {
    // The search bar is not focused yet, but will be.
    update_buttons_with_focus(true);
};

exports.initiate_search = function () {
    $('#search_query').select();
};

exports.clear_search = function () {
    narrow.deactivate();

    $('table tr').removeHighlight();
    $('#search_query').blur();
    exports.update_button_visibility();
};

return exports;

}());
