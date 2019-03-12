var tab_bar = (function () {

var exports = {};

function make_tab(title, hash, data, extra_class, home) {
    return {active: "inactive",
            cls: extra_class || "",
            title: title,
            hash: hash,
            data: data,
            home: home || false };
}

function make_tab_data() {
    var tabs = [];
    var filter = narrow_state.filter();

    function filtered_to_non_home_view_stream() {
        if (!filter.has_operator('stream')) {
            return false;
        }
        var stream_name = filter.operands('stream')[0];
        var stream_id = stream_data.get_stream_id(stream_name);
        if (!stream_id) {
            return true;
        }

        return !stream_data.in_home_view(stream_id);
    }

    function in_all() {
        return filter !== undefined &&
               (filtered_to_non_home_view_stream() ||
                filter.has_operand("in", "all"));
    }

    if (in_all()) {
        tabs.push(make_tab("All Messages", "#narrow/in/all", undefined, "root"));
    } else if (page_params.narrow !== undefined) {
        tabs.push(make_tab("Stream " + page_params.narrow_stream,
                           hash_util.operators_to_hash([page_params.narrow[0]]),
                           page_params.narrow_stream, 'stream'));
        if (page_params.narrow_topic !== undefined) {
            tabs.push(make_tab("Topic " + page_params.narrow_topic,
                               hash_util.operators_to_hash(page_params.narrow),
                               null));
        }
    }

    if (narrow_state.active() && narrow_state.operators().length > 0) {
        var stream;
        var ops = narrow_state.operators();
        // Second breadcrumb item
        var hashed = hash_util.operators_to_hash(ops.slice(0, 1));
        if (filter.has_operator("stream")) {
            stream = filter.operands("stream")[0];
            tabs.push(make_tab(stream, hashed, stream, 'stream'));
        } else if (filter.has_operand("is", "private")) {
            tabs.push(make_tab("Private Messages", '#narrow/is/private',
                               undefined, 'private_message '));

        } else if (filter.has_operator("pm-with")) {
            // We show PMs tabs as just the name(s) of the participant(s)
            var emails = filter.operands("pm-with")[0].split(',');
            var names = _.map(emails, function (email) {
                if (!people.get_by_email(email)) {
                    return email;
                }
                return people.get_by_email(email).full_name;
            });

            tabs.push(make_tab(names.join(', '), hashed));

        } else if (filter.has_operator("group-pm-with")) {
            tabs.push(make_tab("Group Private", '#narrow/group-pm-with',
                               undefined, 'private_message '));

        } else if (filter.has_operand("is", "starred")) {
            tabs.push(make_tab("Starred", hashed));
        } else if (filter.has_operator("near")) {
            tabs.push(make_tab("Near " + filter.operands("near")[0], hashed));
        } else if (filter.has_operator("id")) {
            tabs.push(make_tab("ID " + filter.operands("id")[0], hashed));
        } else if (filter.has_operand("is", "mentioned")) {
            tabs.push(make_tab("Mentions", hashed));
        } else if (filter.has_operator("sender")) {
            var sender = filter.operands("sender")[0];
            if (people.get_by_email(sender)) {
                sender = people.get_by_email(sender).full_name;
            }
            tabs.push(make_tab("Sent by " + sender, hashed));
        }  else if (filter.has_operator("search")) {
            // Search is not a clickable link, since we don't have
            // a search narrow
            tabs.push(make_tab("Search results", false));
        }
    }

    if (tabs.length === 0) {
        tabs.push(make_tab('All messages', "#", "home", "root", true));
    }

    // Last tab is not a link
    tabs[tabs.length - 1].hash = null;

    return tabs;
}

exports.colorize_tab_bar = function () {
    var stream_tab = $('#tab_list .stream');
    if (stream_tab.length > 0) {
        var stream_name = stream_tab.data('name');
        if (stream_name === undefined) {
            return;
        }
        stream_name = stream_name.toString();

        var color_for_stream = stream_data.get_color(stream_name);
        var stream_dark = stream_color.get_color_class(color_for_stream);
        var stream_light = colorspace.getHexColor(
            colorspace.getLighterColor(
                colorspace.getDecimalColor(color_for_stream), 0.2));

        if (stream_tab.hasClass("stream")) {
            stream_tab.css('background-color', color_for_stream);
            if (stream_tab.hasClass("inactive")) {
                stream_tab.hover (
                    function () {
                        $(this).css('background-color', stream_light);
                    }, function () {
                        $(this).css('background-color', color_for_stream);
                    }
                );
            }
            stream_tab.removeClass(stream_color.color_classes);
            stream_tab.addClass(stream_dark);
        }
    }
};

function hide_stream_details() {
    $(".stream_description").hide();
    $(".number_of_users").hide();
}

function empty_nav_bar() {
    $("#tab_list").addClass("hidden");
    hide_stream_details();
    $(".hash").hide();
    $(".navbar-lock").hide();
    $(".navbar-search").removeClass("expanded");
}

function render_stream_details(stream_term) {
    $("#tab_list").removeClass("hidden");
    var stream_name = stream_term.operand;
    var stream  = stream_data.get_sub_by_name(stream_name);
    if (stream === undefined) {
        return;
    }
    $(".stream_description").text(stream.description);
    $(".nav_bar_user_count").append("<i class=\"fa fa-user-o\"></i> ");
    $(".nav_bar_user_count").append(stream.subscriber_count);
    $(".stream_description").show();
    $(".number_of_users").show();
    if (stream.invite_only) {
        $(".navbar-lock").show();
    } else {
        $(".hash").show();
    }
}

function close_search_bar() {
    $("#tab_list").removeClass("hidden");
    $(".navbar-search").removeClass("expanded");
}

function open_search_bar() {
    $("#tab_list").addClass("hidden");
    $(".navbar-search").addClass("expanded");
}

function display_navbar_elements() {
    empty_nav_bar();
    // Handle initializing and home narrow
    var filter = narrow_state.filter();
    if (filter === undefined) {
        close_search_bar();
        return;
    }

    var operator_terms = narrow_state.operators();

    var stream_term = _.find(operator_terms, function (term) { return term.operator === "stream";});
    // Handle stream narrow
    if (stream_term) {
        render_stream_details(stream_term);
        // Does not return in order to handle stream + search or stream + topic + search
    }

    // Handle search narrow and ANY multi-filter narrows
    var search_term = _.find(operator_terms, function (term) { return term.operator === "search";});
    if (search_term ||
        operator_terms.length > 1 &&
        // NOT stream > topic
        !(operator_terms.length === 2 && stream_term && _.find(operator_terms, function (term) { return term.operator === "topic";}))) {
        open_search_bar();
        return; // Stream + search or stream + topic + search would return at this point
    }

    $("#tab_list").removeClass("hidden");

    var operator_term = operator_terms[0];

    if (operator_term.operator === "is") {
        // Keep navbar open for is:unread or is:alerted
        if (operator_term.operand === "unread" || operator_term.operand === "alerted") {
            open_search_bar();
        }

        // TODO: show mention and star with custom icons instead of lock icon
        // hide hash and lock for is:mention and is:starred narrows (displayed without any icons)
        // if (operator_term.operand === "mentioned" || operator_term.operand === "starred") {
        // }
    }
    // TODO: show PMs with mail icon instead of lock icon
    // hide hash for private messages (private messages displayed with lock icons)
    if (operator_term.operator === "pm-with" ||
    operator_term.operator === "group-pm-with" ||
    operator_term.operator === "is" && operator_term.operand === "private") {
        $(".navbar-lock").show();
    }
    // hide hash and lock for "sent by X" (displayed without any icons)
    // if (operator_term.operator === "sender") {
    // }
}

function build_tab_bar() {
    var tabs = make_tab_data();

    var tab_bar = $("#tab_bar");
    tab_bar.empty();

    tabs[tabs.length - 1].active = "active";
    var rendered =  templates.render('tab_bar', {tabs: tabs});

    tab_bar.append(rendered);
    exports.colorize_tab_bar();
    display_navbar_elements();
    tab_bar.removeClass('notdisplayed');
}

exports.initialize = function () {
    build_tab_bar();
};

return exports;

}());

if (typeof module !== 'undefined') {
    module.exports = tab_bar;
}
window.tab_bar = tab_bar;
