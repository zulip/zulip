var tabbar = (function () {

var exports = {};

function make_tab(title, hash, data, extra_class) {
    return {active: "inactive",
            cls: extra_class || "",
            title: title,
            hash: hash,
            data: data};
}

function make_tab_data() {
    var tabs = [];

    if (narrow.active() && narrow.operators().length > 0) {
        var stream, ops = narrow.operators();
        var filter = narrow.filter();
        var hash = hashchange.operators_to_hash(ops);

        // Root breadcrumb item: Either Home or All Messages
        if ((filter.has_operator("stream") &&
             !subs.in_home_view(filter.operands("stream")[0])) ||
            filter.has_operand("in", "all")) {
            tabs.push(make_tab("All Messages", "#narrow/in/all", undefined, "root"));
        } else {
            tabs.push(make_tab("Home", "#", "home", "root"));
        }

        // Second breadcrumb item
        var hashed = hashchange.operators_to_hash(ops.slice(0, 1));
        if (filter.has_operator("stream")) {
            stream = filter.operands("stream")[0];
            tabs.push(make_tab(stream, hashed, stream, 'stream'));
        } else if (filter.has_operator("pm-with") ||
                   filter.has_operand("is", "private-message")) {

            tabs.push(make_tab("Private Messages", '#narrow/is/private-message',
                                undefined, 'private_message '));

            if (filter.has_operator("pm-with")) {
                var emails = filter.operands("pm-with")[0].split(',');
                var names = $.map(emails, function (email) {
                    if (! people_dict[email]) {
                        return email;
                    }
                    return people_dict[email].full_name;
                });

                tabs.push(make_tab(names.join(', '), hashed));
            }

        } else if (filter.has_operand("is", "starred")) {
            tabs.push(make_tab("Starred", hashed));
        } else if (filter.has_operand("is", "mentioned-message")) {
            tabs.push(make_tab("Mentions", hashed));
        } else if (filter.has_operator("sender")) {
            var sender = filter.operands("sender")[0];
            if (people_dict[sender]) {
                sender = people_dict[sender].full_name;
            }
            tabs.push(make_tab("Sent by " + sender, hashed));
        }  else if (filter.has_operator("search")) {
            // Search is not a clickable link, since we don't have
            // a search narrow
            tabs.push(make_tab("Search results", false));
        }

        // Third breadcrumb item for stream-subject naarrows
        if (filter.has_operator("stream") &&
            filter.has_operator("subject")) {
            stream = filter.operands("stream")[0];
            var subject = filter.operands("subject")[0];
            hashed = hashchange.operators_to_hash(ops.slice(0, 2));

            tabs.push(make_tab(subject, hashed, null));
        }
    } else {
        // Just the home view
        tabs.push(make_tab("Home", '#', "home", "root"));
    }

    // Last tab is not a link
    tabs[tabs.length - 1].hash = false;

    return tabs;
}

function colorize_tab_bar() {
    // The stream tab, if it exists, should be the same color as that stream's chosen color
    // Likewise, the border and outline should be the stream color as well
    var stream_tab = $('#tab_list .stream');
    if (stream_tab.length > 0) {
        var stream_name = stream_tab.data('name');
        if (stream_name === undefined) {
            return;
        }
        stream_name = stream_name.toString();

        var stream_color = subs.get_color(stream_name);

        if (!stream_tab.hasClass('active')) {
            stream_tab.css('border-color', stream_color);
        }

        $('#tab_list li.active').css('border-color', stream_color);
    }
}

function build_tab_bar() {
    var tabs = make_tab_data();

    // Insert the narrow spacer between each tab
    if (tabs.length > 1) {
        var idx = -1;
        while (Math.abs(idx) < tabs.length) {
            tabs.splice(idx, 0, {cls: "narrow_spacer", icon: true});
            idx -= 2;
        }
    }

    var tab_bar = $("#tab_bar");
    tab_bar.empty();

    tabs[tabs.length - 1].active = "active";
    var rendered =  templates.render('tab_bar', {tabs: tabs});

    tab_bar.append(rendered);
    colorize_tab_bar();
    tab_bar.removeClass('notdisplayed');
}

$(function () {
    $(document).on('narrow_activated.zephyr', function (event) {
        build_tab_bar();
    });
    $(document).on('narrow_deactivated.zephyr', function (event) {
        build_tab_bar();
    });

    build_tab_bar();
});

}());
