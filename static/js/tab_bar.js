const make_tab_bar_template = require('../templates/tab_bar.hbs');
const rendered_markdown = require('./rendered_markdown');

function get_sub_count(current_stream) {
    const sub_count = current_stream.subscriber_count;
    return sub_count;
}

function get_formatted_sub_count(current_stream) {
    let sub_count = get_sub_count(current_stream);
    if (sub_count >= 1000) {
        // parseInt() is used to floor the value of division to an integer
        sub_count = parseInt(sub_count / 1000, 10) + "k";
    }
    return sub_count;
}

function make_tab_data(filter) {
    const tab_data = {};
    if (filter === undefined) {
        return {
            title: 'All messages',
            icon: 'home',
        };
    }
    tab_data.title = filter.get_title();
    tab_data.icon = filter.get_icon();
    if (tab_data.icon === 'hashtag' || tab_data.icon === 'lock') {
        const stream = filter.operands("stream")[0];
        const current_stream  = stream_data.get_sub_by_name(stream);
        if (current_stream) {
            tab_data.rendered_narrow_description = current_stream.rendered_description;
            tab_data.sub_count = get_sub_count(current_stream);
            tab_data.formatted_sub_count = get_formatted_sub_count(current_stream);
            tab_data.stream_settings_link = "#streams/" + current_stream.stream_id + "/" + current_stream.name;
        } else {
            tab_data.title = 'Unknown Stream';
            tab_data.sub_count = '0';
            tab_data.formatted_sub_count = '0';
            tab_data.rendered_narrow_description = "This stream does not exist or is private.";
        }
    }
    return tab_data;
}

exports.colorize_tab_bar = function () {
    const filter = narrow_state.filter();
    if (filter === undefined || !filter.has_operator('stream')) {return;}
    const color_for_stream = stream_data.get_color(filter.operands("stream")[0]);
    const stream_light = colorspace.getHexColor(colorspace.getDecimalColor(color_for_stream));
    $("#tab_list .fa-hashtag").css('color', stream_light);
    $("#tab_list .fa-lock").css('color', stream_light);
};

function append_and_display_tab_bar(tab_bar_data) {
    const tab_bar = $("#tab_bar");
    tab_bar.empty();
    const tab_bar_template = make_tab_bar_template(tab_bar_data);
    tab_bar.append(tab_bar_template);
    if (tab_bar_data.stream_settings_link) {
        exports.colorize_tab_bar();
    }
    tab_bar.removeClass('notdisplayed');
    const content = tab_bar.find('span.rendered_markdown');
    if (content) {
        // Update syntax like stream names, emojis, mentions, timestamps.
        rendered_markdown.update_elements(content);
    }
}

function bind_tab_bar_handlers() {
    $("#tab_list span:nth-last-child(2)").on("click", function (e) {
        if (document.getSelection().type === "Range") {
            // Allow copy/paste to work normally without interference.
            return;
        }

        // Let links behave normally, ie, do nothing if <a>
        if ($(e.target).closest("a").length === 0) {
            exports.open_search_bar_and_close_narrow_description();
            search.initiate_search();
            e.preventDefault();
            e.stopPropagation();
        }
    });

    const color = $(".search_closed").css("color");
    const night_mode_color = $(".nightmode .closed_icon").css("color");

    // make sure that hover plays nicely with whether search is being
    // opened or not.
    $(".narrow_description > a").hover(function () {
        if (night_mode_color) {
            $(".search_closed").css("color", night_mode_color);
        } else {
            $(".search_closed").css("color", color);
        }
    }, function () {
        $(".search_closed").css("color", "");
    });
}

function build_tab_bar(filter) {
    // This makes sure we don't waste time appending tab_bar on a template where it's never used
    if (filter && !filter.is_common_narrow()) {
        exports.open_search_bar_and_close_narrow_description();
    } else {
        const tab_bar_data = make_tab_data(filter);

        append_and_display_tab_bar(tab_bar_data);

        bind_tab_bar_handlers();

        exports.close_search_bar_and_open_narrow_description();
    }
}

exports.exit_search = function () {
    const filter = narrow_state.filter();
    if (!filter || filter.is_common_narrow()) {
        // for common narrows, we change the UI (and don't redirect)
        exports.close_search_bar_and_open_narrow_description();

        // reset searchbox text
        const search_string = narrow_state.search_string();
        // This does not need to be conditional like the corresponding
        // function call in narrow.activate because search filters are
        // not common narrows
        if (search_string !== "") {
            $("#search_query").val(search_string + " ");
        }
    } else {
        // for "searching narrows", we redirect
        window.location.replace(filter.generate_redirect_url());
    }
};

exports.initialize = function () {
    exports.render_tab_bar();

    // register searchbar click handler
    $('#search_exit').on("click", function (e) {
        tab_bar.exit_search();
        e.preventDefault();
        e.stopPropagation();
    });
};

exports.update_stream_name = function (new_name) {
    // TODO: Implement this properly. Really, this does not need to
    // be a separate function call and should just be replaced by a
    // call to render_tab_bar, however, that will work iff the filter
    // is correctly reset to the new stream name (which involves
    // handling complicated searching states and multiple filters).
    const stream_name = $(".stream a");
    if (stream_name !== undefined) {
        stream_name.text(new_name);
    }
};

exports.render_tab_bar = function () {
    // TODO: Implement rerendering for stream privacy or subscriber
    // count changes. We simply need to call this function in the
    // appropriate places.
    const filter = narrow_state.filter();
    build_tab_bar(filter);
};

exports.open_search_bar_and_close_narrow_description = function () {
    $(".navbar-search").addClass("expanded");
    $("#tab_list").addClass("hidden");
};

exports.close_search_bar_and_open_narrow_description = function () {
    const filter = narrow_state.filter();
    if (!(filter && !filter.is_common_narrow())) {
        $(".navbar-search").removeClass("expanded");
        $("#tab_list").removeClass("hidden");
    }
};

window.tab_bar = exports;
