"use strict";

const render_message_view_header = require("../templates/message_view_header.hbs");

const rendered_markdown = require("./rendered_markdown");

function get_sub_count(current_stream) {
    const sub_count = current_stream.subscriber_count;
    return sub_count;
}

function get_formatted_sub_count(current_stream) {
    let sub_count = get_sub_count(current_stream);
    if (sub_count >= 1000) {
        // parseInt() is used to floor the value of division to an integer
        sub_count = Number.parseInt(sub_count / 1000, 10) + "k";
    }
    return sub_count;
}

function make_message_view_header(filter) {
    const message_view_header = {};
    if (recent_topics.is_visible()) {
        return {
            title: i18n.t("Recent topics (beta)"),
            icon: "clock-o",
        };
    }
    if (filter === undefined) {
        return {
            title: i18n.t("All messages"),
            icon: "home",
        };
    }
    message_view_header.title = filter.get_title();
    message_view_header.icon = filter.get_icon();
    if (filter.has_operator("stream") && !filter._sub) {
        message_view_header.sub_count = "0";
        message_view_header.formatted_sub_count = "0";
        message_view_header.rendered_narrow_description = i18n.t(
            "This stream does not exist or is private.",
        );
        return message_view_header;
    }
    if (filter._sub) {
        // We can now be certain that the narrow
        // involves a stream which exists and
        // the current user can access.
        const current_stream = filter._sub;
        message_view_header.rendered_narrow_description = current_stream.rendered_description;
        message_view_header.sub_count = get_sub_count(current_stream);
        message_view_header.formatted_sub_count = get_formatted_sub_count(current_stream);
        // the "title" is passed as a variable and doesn't get translated (nor should it)
        message_view_header.sub_count_tooltip_text = i18n.t(
            "__count__ users are subscribed to #__title__",
            {count: message_view_header.sub_count, title: message_view_header.title},
        );
        message_view_header.stream_settings_link =
            "#streams/" + current_stream.stream_id + "/" + current_stream.name;
    }
    return message_view_header;
}

exports.colorize_message_view_header = function () {
    const filter = narrow_state.filter();
    if (filter === undefined || !filter._sub) {
        return;
    }
    $("#message_view_header .stream > .fa").css("color", filter._sub.color);
};

function append_and_display_title_area(message_view_header_data) {
    const message_view_header_elem = $("#message_view_header");
    message_view_header_elem.empty();
    const rendered = render_message_view_header(message_view_header_data);
    message_view_header_elem.append(rendered);
    if (message_view_header_data.stream_settings_link) {
        exports.colorize_message_view_header();
    }
    message_view_header_elem.removeClass("notdisplayed");
    const content = message_view_header_elem.find("span.rendered_markdown");
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

    $("#message_view_header span:nth-last-child(2)").on("click", (e) => {
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
    $("#message_view_header .narrow_description > a")
        .on("mouseenter", () => {
            $("#message_view_header .search_closed").addClass("search_icon_hover_highlight");
        })
        .on("mouseleave", () => {
            $("#message_view_header .search_closed").removeClass("search_icon_hover_highlight");
        });
}

function build_message_view_header(filter) {
    // This makes sure we don't waste time appending
    // message_view_header on a template where it's never used
    if (filter && !filter.is_common_narrow()) {
        exports.open_search_bar_and_close_narrow_description();
    } else {
        const message_view_header_data = make_message_view_header(filter);
        append_and_display_title_area(message_view_header_data);
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
        window.location.href = filter.generate_redirect_url();
    }
    $(".app").trigger("focus");
};

exports.initialize = function () {
    exports.render_title_area();

    // register searchbar click handler
    $("#search_exit").on("click", (e) => {
        message_view_header.exit_search();
        e.preventDefault();
        e.stopPropagation();
    });
};

exports.render_title_area = function () {
    const filter = narrow_state.filter();
    build_message_view_header(filter);
};

// This function checks if "modified_sub" which is the stream whose values
// have been updated is the same as the stream which is currently
// narrowed (filter._sub) and rerenders if necessary
exports.maybe_rerender_title_area_for_stream = function (modified_sub) {
    const filter = narrow_state.filter();
    if (filter && filter._sub && filter._sub.stream_id === modified_sub.stream_id) {
        message_view_header.render_title_area();
    }
};

exports.open_search_bar_and_close_narrow_description = function () {
    exports.reset_searchbox_text();
    $(".navbar-search").addClass("expanded");
    $("#message_view_header").addClass("hidden");
};

exports.close_search_bar_and_open_narrow_description = function () {
    const filter = narrow_state.filter();
    if (!(filter && !filter.is_common_narrow())) {
        $(".navbar-search").removeClass("expanded");
        $("#message_view_header").removeClass("hidden");
    }
};

window.message_view_header = exports;
