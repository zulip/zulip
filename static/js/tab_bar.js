const render_tab_bar = require("../templates/tab_bar.hbs");

const rendered_markdown = require("./rendered_markdown");

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
            title: i18n.t("All messages"),
            icon: "home",
        };
    }
    tab_data.title = filter.get_title();
    tab_data.icon = filter.get_icon();
    if (filter.has_operator("stream") && !filter._sub) {
        tab_data.sub_count = "0";
        tab_data.formatted_sub_count = "0";
        tab_data.rendered_narrow_description = i18n.t("This stream does not exist or is private.");
        return tab_data;
    }
    if (filter._sub) {
        // We can now be certain that the narrow
        // involves a stream which exists and
        // the current user can access.
        const current_stream = filter._sub;
        tab_data.rendered_narrow_description = current_stream.rendered_description;
        tab_data.sub_count = get_sub_count(current_stream);
        tab_data.formatted_sub_count = get_formatted_sub_count(current_stream);
        // the "title" is passed as a variable and doesn't get translated (nor should it)
        tab_data.sub_count_tooltip_text = i18n.t("__count__ users are subscribed to #__title__", {
            count: tab_data.sub_count,
            title: tab_data.title,
        });
        tab_data.stream_settings_link =
            "#streams/" + current_stream.stream_id + "/" + current_stream.name;
    }
    return tab_data;
}

exports.colorize_tab_bar = function () {
    const filter = narrow_state.filter();
    if (filter === undefined || !filter._sub) {
        return;
    }
    $("#tab_bar .stream > .fa").css("color", filter._sub.color);
};

function append_and_display_title_area(tab_bar_data) {
    const tab_bar_elem = $("#tab_bar");
    tab_bar_elem.empty();
    const rendered = render_tab_bar(tab_bar_data);
    tab_bar_elem.append(rendered);
    if (tab_bar_data.stream_settings_link) {
        exports.colorize_tab_bar();
    }
    tab_bar_elem.removeClass("notdisplayed");
    const content = tab_bar_elem.find("span.rendered_markdown");
    if (content) {
        // Update syntax like stream names, emojis, mentions, timestamps.
        rendered_markdown.update_elements(content);
    }
}

function bind_title_area_handlers() {
    $(".search_closed").on("click", (e) => {
        search.initiate_search();
        e.preventDefault();
        e.stopPropagation();
    });

    $("#tab_bar span:nth-last-child(2)").on("click", (e) => {
        if (document.getSelection().type === "Range") {
            // Allow copy/paste to work normally without interference.
            return;
        }

        // Let links behave normally, ie, do nothing if <a>
        if ($(e.target).closest("a").length === 0) {
            search.initiate_search();
            e.preventDefault();
            e.stopPropagation();
        }
    });

    // handler that makes sure that hover plays nicely
    // with whether search is being opened or not.
    $("#tab_bar .narrow_description > a")
        .on("mouseenter", () => {
            $("#tab_bar .search_closed").addClass("search_icon_hover_highlight");
        })
        .on("mouseleave", () => {
            $("#tab_bar .search_closed").removeClass("search_icon_hover_highlight");
        });
}

function build_tab_bar(filter) {
    // This makes sure we don't waste time appending tab_bar on a template where it's never used
    if (filter && !filter.is_common_narrow()) {
        exports.open_search_bar_and_close_narrow_description();
    } else {
        const tab_bar_data = make_tab_data(filter);
        append_and_display_title_area(tab_bar_data);
        bind_title_area_handlers();
        if (page_params.search_pills_enabled && $("#search_query").is(":focus")) {
            exports.open_search_bar_and_close_narrow_description();
        } else {
            exports.close_search_bar_and_open_narrow_description();
        }
    }
}

// we rely entirely on this function to ensure
// the searchbar has the right text.
exports.reset_searchbox_text = function () {
    let search_string = narrow_state.search_string();
    if (search_string !== "") {
        if (!page_params.search_pills_enabled && !narrow_state.filter().is_search()) {
            // saves the user a keystroke for quick searches
            search_string = search_string + " ";
        }
        $("#search_query").val(search_string);
    }
};

exports.exit_search = function () {
    const filter = narrow_state.filter();
    if (!filter || filter.is_common_narrow()) {
        // for common narrows, we change the UI (and don't redirect)
        exports.close_search_bar_and_open_narrow_description();
    } else {
        // for "searching narrows", we redirect
        window.location.replace(filter.generate_redirect_url());
    }
};

exports.initialize = function () {
    exports.render_title_area();

    // register searchbar click handler
    $("#search_exit").on("click", (e) => {
        tab_bar.exit_search();
        e.preventDefault();
        e.stopPropagation();
    });
};

exports.render_title_area = function () {
    const filter = narrow_state.filter();
    build_tab_bar(filter);
};

// This function checks if "modified_sub" which is the stream whose values
// have been updated is the same as the stream which is currently
// narrowed (filter._sub) and rerenders if necessary
exports.maybe_rerender_title_area_for_stream = function (modified_sub) {
    const filter = narrow_state.filter();
    if (filter && filter._sub && filter._sub.stream_id === modified_sub.stream_id) {
        tab_bar.render_title_area();
    }
};

exports.open_search_bar_and_close_narrow_description = function () {
    exports.reset_searchbox_text();
    $(".navbar-search").addClass("expanded");
    $("#tab_bar").addClass("hidden");
};

exports.close_search_bar_and_open_narrow_description = function () {
    const filter = narrow_state.filter();
    if (!(filter && !filter.is_common_narrow())) {
        $(".navbar-search").removeClass("expanded");
        $("#tab_bar").removeClass("hidden");
    }
};

window.tab_bar = exports;
