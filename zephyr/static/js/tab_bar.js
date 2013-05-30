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
        var ops = narrow.operators();
        var hash = hashchange.operators_to_hash(ops);

        // Root breadcrumb item: Either Home or All Messages
        var operator = ops[0][0];
        var operand = ops[0][1];
        if ((operator === 'stream' && !narrow.stream_in_home(operand)) ||
            (operator === 'in' && operand === 'all')) {
            tabs.push(make_tab("All Messages", "#narrow/in/all", undefined, "root"));
        } else {
            tabs.push(make_tab("Home", "#", "home", "root"));
        }

        // Second breadcrumb item
        var hashed = hashchange.operators_to_hash(ops.slice(0, 1));
        if (operator === 'stream') {
            tabs.push(make_tab(operand, hashed, operand, 'stream'));
        } else if ((operator === 'is' && operand === 'private-message') ||
                   (operator === 'pm-with')) {
            var extra_cls = "";
            if (operator === 'pm-with') {
                extra_cls = "dark_background";
            }

            tabs.push(make_tab("Private Messages", '#narrow/is/private-message',
                                undefined, 'private_message ' + extra_cls));

            if (operator === 'pm-with') {
                var emails = operand.split(',');
                var names = $.map(emails, function (email) {
                    if (! people_dict[email]) {
                        return email;
                    }
                    return people_dict[email].full_name;
                });

                tabs.push(make_tab(names.join(', '), hashed));
            }

        } else if (operator === 'is' && operand === 'starred') {
            tabs.push(make_tab("Starred", hashed));
        } else if (operator === 'is' && operand === 'mentioned') {
            tabs.push(make_tab("Mentions", hashed));
        } else if (operator === 'sender') {
            var sender = operand;
            if (people_dict[operand]) {
                sender = people_dict[operand].full_name;
            }
            tabs.push(make_tab("Sent by " + sender, hashed));
        }  else if (operator === 'search') {
            // Search is not a clickable link, since we don't have
            // a search narrow
            tabs.push(make_tab("Search", false));
        }

        // Third breadcrumb item for stream-subject naarrows
        if (ops.length > 1) {
            operator = ops[1][0];
            operand = ops[1][1];
            hashed = hashchange.operators_to_hash(ops.slice(0, 2));

            if (operator === 'subject') {
                // Colorize text of stream name properly
                var stream = ops[0][1];
                tabs[tabs.length - 1].cls += ' ' + subs.get_color_class(subs.get_color(stream));

                tabs.push(make_tab(operand, hashed));
            }
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
    // The active tab color should be the same color as the message list background
    var bg_color = $('#main_div').css('background-color');
    $('#tab_list .active').css('background-color', bg_color);
    $('#tab_bar_underpadding').css('background-color', bg_color);

    // The stream tab, if it exists, should be the same color as that stream's chosen color
    // Likewise, the border and outline should be the stream color as well
    var stream_tab = $('#tab_list .stream');
    if (stream_tab.length > 0) {
        var stream_name = stream_tab.data('name');
        if (stream_name === undefined) {
            return;
        }

        var stream_color = subs.get_color(stream_name);

        if (!stream_tab.hasClass('active')) {
            stream_tab.css('background-color', stream_color);
        }

        $('#tab_list li.active').toggleClass('colorize_tab_outline', true);
        $('.colorize_tab_outline').css('border-color', stream_color);
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
