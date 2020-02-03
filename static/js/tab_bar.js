const render_tab_bar = require('../templates/tab_bar.hbs');

function make_tab(title, hash, data, extra_class, home) {
    return {active: "inactive",
            cls: extra_class || "",
            title: title,
            hash: hash,
            data: data,
            home: home || false };
}

function make_tab_data() {
    const tabs = [];
    const filter = narrow_state.filter();

    function filtered_to_non_home_view_stream() {
        if (!filter.has_operator('stream')) {
            return false;
        }
        const stream_name = filter.operands('stream')[0];
        const stream_id = stream_data.get_stream_id(stream_name);
        if (!stream_id) {
            return true;
        }

        return stream_data.is_muted(stream_id);
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
        let stream;
        const ops = narrow_state.operators();
        // Second breadcrumb item
        let hashed = hash_util.operators_to_hash(ops.slice(0, 1));
        if (filter.has_operator("stream")) {
            stream = filter.operands("stream")[0];
            tabs.push(make_tab(stream, hashed, stream, 'stream'));
        } else if (filter.has_operator("pm-with") ||
                   filter.has_operand("is", "private")) {

            tabs.push(make_tab("Private Messages", '#narrow/is/private',
                               undefined, 'private_message '));

            if (filter.has_operator("pm-with")) {
                const emails = filter.operands("pm-with")[0].split(',');
                const names = emails.map(email => {
                    if (!people.get_by_email(email)) {
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
        } else if (filter.has_operand("streams", "public")) {
            tabs.push(make_tab("Public Streams", hashed));
        } else if (filter.has_operator("near")) {
            tabs.push(make_tab("Near " + filter.operands("near")[0], hashed));
        } else if (filter.has_operator("id")) {
            tabs.push(make_tab("ID " + filter.operands("id")[0], hashed));
        } else if (filter.has_operand("is", "mentioned")) {
            tabs.push(make_tab("Mentions", hashed));
        } else if (filter.has_operator("sender")) {
            let sender = filter.operands("sender")[0];
            if (people.get_by_email(sender)) {
                sender = people.get_by_email(sender).full_name;
            }
            tabs.push(make_tab("Sent by " + sender, hashed));
        }  else if (filter.has_operator("search")) {
            // Search is not a clickable link, since we don't have
            // a search narrow
            tabs.push(make_tab("Search results", false));
        }

        // Third breadcrumb item for stream-topic naarrows
        if (filter.has_operator("stream") &&
            filter.has_operator("topic")) {
            const topic = filter.operands("topic")[0];
            hashed = hash_util.operators_to_hash(ops.slice(0, 2));

            tabs.push(make_tab(topic, hashed, null));
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
    const stream_tab = $('#tab_list .stream');
    if (stream_tab.length > 0) {
        let stream_name = stream_tab.data('name');
        if (stream_name === undefined) {
            return;
        }
        stream_name = stream_name.toString();

        const color_for_stream = stream_data.get_color(stream_name);
        const stream_dark = stream_color.get_color_class(color_for_stream);
        const stream_light = colorspace.getHexColor(
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
    const tabs = make_tab_data();

    const tab_bar = $("#tab_bar");
    tab_bar.empty();

    tabs[tabs.length - 1].active = "active";
    const rendered =  render_tab_bar({tabs: tabs});

    tab_bar.append(rendered);
    exports.colorize_tab_bar();
    tab_bar.removeClass('notdisplayed');
}

exports.update_stream_name = function (new_name) {
    // noop
    if (new_name) {
        return;
    }
};

exports.update_stream_description = function (rendered_new_description) {
    // noop as .narrow_description does not exist (undefined)
    const stream_description = $(".narrow_description");
    if (stream_description !== undefined) {
        stream_description.html(rendered_new_description);
    }
};

exports.initialize = function () {
    build_tab_bar();
};

window.tab_bar = exports;
