var search = (function () {

var exports = {};

var cached_term = "";
var cached_matches = [];
var cached_index;
var cached_table = $('table.focused_table');
var current_search_term;

// Data storage for the typeahead -- to go from object to string representation and vice versa.
var search_object = {};

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


// Convert a list of operators to a human-readable description.
function describe(operators) {
    return $.map(operators, function (elem) {
        var operand = elem[1];
        switch (narrow.canonicalize_operator(elem[0])) {
        case 'is':
            if (operand === 'private') {
                return 'Narrow to all private messages';
            } else if (operand === 'starred') {
                return 'Narrow to starred messages';
            } else if (operand === 'mentioned') {
                return 'Narrow to mentioned messages';
            }
            break;

        case 'stream':
            return 'Narrow to stream ' + operand;

        case 'topic':
            return 'Narrow to topic ' + operand;

        case 'sender':
            return 'Narrow to sender ' + operand;

        case 'pm-with':
            return 'Narrow to private messages with ' + operand;

        case 'search':
            return 'Search for ' + operand;

        case 'in':
            return 'Narrow to messages in ' + operand;
        }
        return 'Narrow to (unknown operator)';
    }).join(', ');
}

function narrow_or_search_for_term(item) {
    var search_query_box = $("#search_query");
    var obj = search_object[item];
    ui.change_tab_to('#home');
    var operators = narrow.parse(obj.search_string);
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

function get_stream_suggestions(query, max_num) {
    var streams = subs.subscribed_streams();

    streams = $.grep(streams, function (stream) {
        return stream_matches_query(stream, query);
    });

    streams = typeahead_helper.sorter(query, streams);
    streams = streams.slice(0, max_num);

    var objs = $.map(streams, function (stream) {
        var prefix = 'Narrow to stream';
        var highlighted_stream = typeahead_helper.highlight_query_in_phrase(query, stream);
        var description = prefix + ' ' + highlighted_stream;
        var search_string = narrow.unparse([['stream', stream]]);
        return {description: description, search_string: search_string};
    });

    return objs;
}

function get_person_suggestions(all_people, query, prefix, operator, max_num) {
    var people = $.grep(all_people, function (person) {
        return person_matches_query(person, query);
    });

    people.sort(typeahead_helper.compare_by_pms);
    people = people.slice(0, max_num);

    var objs = $.map(people, function (person) {
        var name = highlight_person(query, person);
        var description = prefix + ' ' + name;
        var search_string = operator + ':' + person.email;
        return {description: description, search_string: search_string};
    });

    return objs;
}

function get_suggestion_based_on_query(search_string, operators) {
    // We expect caller to call narrow.parse to get operators from search_string.
    var description = describe(operators);
    description = Handlebars.Utils.escapeExpression(description);
    return {description: description, search_string: search_string};
}

function get_topic_suggestions(query, query_operators, max_num) {
    if (query_operators.length === 0) {
        return [];
    }

    var last_term = query_operators.slice(-1)[0];
    var operator = narrow.canonicalize_operator(last_term[0]);
    var operand = last_term[1];
    var stream;
    var guess;

    // stream:Rome -> show all Rome topics
    // stream:Rome topic: -> show all Rome topics
    // stream:Rome f -> show all Rome topics with a word starting in f
    // stream:Rome topic:f -> show all Rome topics with a word starting in f
    // stream:Rome topic:f -> show all Rome topics with a word starting in f

    // When narrowed to a stream:
    //   topic: -> show all topics in current stream
    //   foo -> show all topics in current stream with words starting with foo

    // If somebody explicitly types search:, then we might
    // not want to suggest topics, but I feel this is a very
    // minor issue, and narrow.parse() is currently lossy
    // in terms of telling us whether they provided the operator,
    // i.e. "foo" and "search:foo" both become [['search', 'foo']].
    switch (operator) {
    case 'stream':
        guess = '';
        stream = operand;
        break;
    case 'topic':
    case 'search':
        guess = operand;
        query_operators = query_operators.slice(0, -1);
        var filter = new narrow.Filter(query_operators);
        if (filter.has_operator('topic')) {
            return [];
        }
        if (filter.has_operator('stream')) {
            stream = filter.operands('stream')[0];
        } else {
            stream = narrow.stream();
            query_operators.push(['stream', stream]);
        }
        break;
    default:
        return [];
    }

    if (!stream) {
        return [];
    }

    stream = subs.canonicalized_name(stream);

    var topics = recent_subjects[stream];

    if (!topics) {
        return [];
    }

    // Be defensive here in case recent_subjects gets super huge, but
    // still slice off enough topics to find matches.
    topics = topics.slice(0, 100);

    // topics = $.map(topics, (t) -> t.subject)
    topics = $.map(topics, function (topic) {
        return topic.subject; // "subject" is just the name of the topic
    });

    if (guess !== '') {
        topics = $.grep(topics, function (topic) {
            // Don't suggest a topic if the user has already typed out
            // the full topic name.
            var redundant = topic.toLowerCase() === guess.toLowerCase();
            if (redundant) {
                return false;
            }
            return phrase_match(topic, guess);
        });
    }

    topics = topics.slice(0, max_num);

    // Just use alphabetical order.  While recency and read/unreadness of
    // subjects do matter in some contexts, you can get that from the left sidebar,
    // and I'm leaning toward high scannability for autocompletion.  I also don't
    // care about case.
    topics.sort();

    return $.map(topics, function (topic) {
        var topic_operator = ['topic', topic];
        var operators = query_operators.concat([topic_operator]);
        var search_string = narrow.unparse(operators);
        var description = describe(operators);
        return {description: description, search_string: search_string};
    });
}

exports.initialize = function () {
    $( "#search_query" ).typeahead({
        source: function (query, process) {
            var result = [];
            var suggestion;
            var suggestions;

            // Add an entry for narrow by operators.
            var operators = narrow.parse(query);
            if (operators.length !== 0) {
                suggestion = get_suggestion_based_on_query(query, operators);
                result = [suggestion];
            } else {
                return [];
            }

            suggestions = get_stream_suggestions(query, 4);
            result = result.concat(suggestions);

            var people = page_params.people_list;

            suggestions = get_person_suggestions(people, query, 'Narrow to private messages with', 'pm-with', 4);
            result = result.concat(suggestions);

            suggestions = get_person_suggestions(people, query, 'Narrow to messages sent by', 'sender', 4);
            result = result.concat(suggestions);

            suggestions = get_topic_suggestions(query, operators, 15);
            result = result.concat(suggestions);

            // We can't send typeahead objects, only strings.
            search_object = {};
            $.each(result, function (idx, obj) {
                search_object[obj.search_string] = obj;
            });
            return $.map(result, function (obj) {
                return obj.search_string;
            });
        },
        items: 50,
        highlighter: function (item) {
            var obj = search_object[item];
            return obj.description;
        },
        matcher: function (item) {
            return true;
        },
        updater: narrow_or_search_for_term,
        sorter: function (items) {
            return items;
        },
        smartSpaceBar: true
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
            if (search_query_box.val().trim()) {
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
