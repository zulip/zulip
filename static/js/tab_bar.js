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
        return (filter !== undefined &&
               (filtered_to_non_home_view_stream() ||
                filter.has_operand("in", "all")));
    }

    if (in_all()) {
        tabs.push(make_tab("All Messages", "#narrow/in/all", undefined, "root"));
    } else if (page_params.narrow !== undefined) {
        tabs.push(make_tab("Stream " + page_params.narrow_stream,
                           hashchange.operators_to_hash([page_params.narrow[0]]),
                           page_params.narrow_stream, 'stream'));
        if (page_params.narrow_topic !== undefined) {
            tabs.push(make_tab("Topic " + page_params.narrow_topic,
                               hashchange.operators_to_hash(page_params.narrow),
                               null));
        }
    }

    if (narrow_state.active() && narrow_state.operators().length > 0) {
        var stream;
        var ops = narrow_state.operators();
        // Second breadcrumb item
        var hashed = hashchange.operators_to_hash(ops.slice(0, 1));
        if (filter.has_operator("stream")) {
            stream = filter.operands("stream")[0];
            tabs.push(make_tab(stream, hashed, stream, 'stream'));
        } else if (filter.has_operator("pm-with") ||
                   filter.has_operand("is", "private")) {

            tabs.push(make_tab("Private Messages", '#narrow/is/private',
                                undefined, 'private_message '));

            if (filter.has_operator("pm-with")) {
                var emails = filter.operands("pm-with")[0].split(',');
                var names = _.map(emails, function (email) {
                    if (! people.get_by_email(email)) {
                        return email;
                    }
                    return people.get_by_email(email).full_name;
                });

                tabs.push(make_tab(names.join(', '), hashed));
            }

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

        // Third breadcrumb item for stream-subject naarrows
        if (filter.has_operator("stream") &&
            filter.has_operator("topic")) {
            var subject = filter.operands("topic")[0];
            hashed = hashchange.operators_to_hash(ops.slice(0, 2));

            tabs.push(make_tab(subject, hashed, null));
        }
    }

    if (tabs.length === 0) {
        tabs.push(make_tab('Home', "#", "home", "root", true));
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

function build_tab_bar() {
    var tabs = make_tab_data();

    var tab_bar = $("#tab_bar");
    tab_bar.empty();

    tabs[tabs.length - 1].active = "active";
    var rendered =  templates.render('tab_bar', {tabs: tabs});

    tab_bar.append(rendered);
    exports.colorize_tab_bar();
    tab_bar.removeClass('notdisplayed');
}

$(function () {
    $(document).on('narrow_activated.zulip', function () {
        build_tab_bar();
    });
    $(document).on('narrow_deactivated.zulip', function () {
        build_tab_bar();
    });

    build_tab_bar();
});

return exports;

}());

if (typeof module !== 'undefined') {
    module.exports = tab_bar;
}
