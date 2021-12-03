import "../csrf";
import * as diff from "diff";
import * as diff2html from "diff2html";
import hljs from "highlight.js/lib/core";
import xml from "highlight.js/lib/languages/xml";
import $ from "jquery";
import * as html_parser from "prettier/parser-html";
import * as prettier from "prettier/standalone";

import generated_emoji_codes from "../../generated/emoji/emoji_codes.json";
import generated_pygments_data from "../../generated/pygments_data.json";
import * as emoji from "../../shared/js/emoji";
import * as fenced_code from "../../shared/js/fenced_code";
import * as channel from "../channel";
import * as markdown from "../markdown";
// Importing "stream_data.js" to avoid import error while
// importing "markdown_config.js".
import * as stream_data from "../stream_data"; // eslint-disable-line no-unused-vars
import {get_helpers} from "../markdown_config"; // eslint-disable-line import/order

// Avoid importing all the languages.
hljs.registerLanguage("xml", xml);

// Main JavaScript file for the markdown development panel at
// /devtools/markdown.

let active_tab = null;
let tabs = null;
let rendering = false;

const get_tabs_data = () => ({
    backend_markdown: {
        raw_html: "",
        raw_message: "",
        $tab: $("#markdown_tabs .backend-markdown-tab"),
        $content: $("#backend_markdown"),
    },
    frontend_markdown: {
        raw_html: "",
        raw_message: "",
        $tab: $("#markdown_tabs .frontend-markdown-tab"),
        $content: $("#frontend_markdown"),
    },
    diff: {
        raw_message: "",
        $tab: $("#markdown_tabs .diff-tab"),
        $content: $("#diff_data"),
    },
});

const focus_tab = {
    backend_markdown_tab() {
        $("#markdown_tabs .active").removeClass("active");
        tabs.backend_markdown.$tab.addClass("active");
        tabs.backend_markdown.$content.show();
        tabs.frontend_markdown.$content.hide();
        tabs.diff.$content.hide();
        active_tab = "backend_markdown";
    },
    frontend_markdown_tab() {
        $("#markdown_tabs .active").removeClass("active");
        tabs.frontend_markdown.$tab.addClass("active");
        tabs.backend_markdown.$content.hide();
        tabs.frontend_markdown.$content.show();
        tabs.diff.$content.hide();
        active_tab = "frontend_markdown";
    },
    diff_tab() {
        $("#markdown_tabs .active").removeClass("active");
        tabs.diff.$tab.addClass("active");
        tabs.backend_markdown.$content.hide();
        tabs.frontend_markdown.$content.hide();
        tabs.diff.$content.show();
        active_tab = "diff";
    },
};

function start_rendering() {
    $(".buttons .rendering").css("display", "inline-block");
    rendering = true;
}

function stop_rendering() {
    $(".buttons .rendering").hide();
    rendering = false;
}

function show_error(msg) {
    $(".error").text(msg).css("display", "block");
}

function hide_error() {
    $(".error").hide();
}

function place_code(tab_name, html) {
    const tab = tabs[tab_name];
    // Formating the HTML.
    tab.raw_html = prettier.format(html, {
        parser: "html",
        plugins: [html_parser],
        htmlWhitespaceSensitivity: "ignore",
    });
    // Syntax highlighting the HTML.
    tab.$content.html(hljs.highlight(tab.raw_html, {language: "xml"}).value);
}

function render_code() {
    if (active_tab === "backend_markdown") {
        get_backend_markdown();
    } else if (active_tab === "frontend_markdown") {
        get_frontend_markdown();
    } else {
        show_diff();
    }
}

function handle_unsuccessful_response(response) {
    try {
        const status_code = response.statusCode().status;
        response = JSON.parse(response.responseText);
        show_error(`(${status_code}) ${response.msg}`);
    } catch {
        // If the response is not a JSON response, then it is probably
        // Django returning an HTML response containing a stack trace
        // with useful debugging information regarding the backend
        // code.
        document.write(response.responseText);
    }
    return;
}

function get_backend_markdown() {
    const message = $("#raw_content").val().trim();
    // Avoid rendering if the message is the same as the previous one.
    if (tabs.backend_markdown.raw_message !== message) {
        start_rendering();
        tabs.backend_markdown.raw_message = message;
        channel.post({
            url: "/json/messages/render",
            data: {content: message},
            success(response) {
                place_code("backend_markdown", response.rendered);
                if (active_tab === "diff") {
                    show_diff();
                }
            },
            error(response) {
                handle_unsuccessful_response(response);
                tabs.backend_markdown.raw_message = "";
            },
            complete: stop_rendering,
        });
    }
}

function get_frontend_markdown() {
    const message = $("#raw_content").val().trim();
    // Avoid rendering if the message is the same as the previous one.
    if (tabs.frontend_markdown.raw_message !== message) {
        start_rendering();
        tabs.frontend_markdown.raw_message = message;
        const options = {raw_content: message};
        markdown.apply_markdown(options);
        place_code("frontend_markdown", options.content);
        stop_rendering();
    }
}

function get_markdown_fixture(fixture_name) {
    channel.get({
        url: "/devtools/markdown/" + encodeURIComponent(fixture_name) + "/fixture",
        // Since the user may add or modify fixtures as they edit.
        idempotent: false,
        success(response) {
            $("#raw_content").val(response.test_input);
        },
        error: handle_unsuccessful_response,
    });
}

function show_diff() {
    const message = $("#raw_content").val().trim();

    get_frontend_markdown();

    if (tabs.backend_markdown.raw_message !== message) {
        get_backend_markdown();
        return;
    }

    const diffString = diff.createTwoFilesPatch(
        "backend-markdown",
        "frontend-markdown",
        tabs.backend_markdown.raw_html,
        tabs.frontend_markdown.raw_html,
    );
    const diffHtml = diff2html.html(diffString, {
        drawFileList: false,
        matching: "lines",
        outputFormat: "line-by-line",
    });
    tabs.diff.$content.html(diffHtml);
}

// Initialization
$(() => {
    tabs = get_tabs_data();
    emoji.initialize({realm_emoji: {}, emoji_codes: generated_emoji_codes});
    markdown.initialize([], get_helpers());
    fenced_code.initialize(generated_pygments_data);
    focus_tab.backend_markdown_tab();

    $("#markdown_fixture_names").on("change", function () {
        const fixture_name = $(this).children("option:selected").val();
        get_markdown_fixture(fixture_name);
    });

    $("#markdown_tabs .backend-markdown-tab").on("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        if (!rendering) {
            hide_error();
            focus_tab.backend_markdown_tab();
            get_backend_markdown();
        }
    });

    $("#markdown_tabs .frontend-markdown-tab").on("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        if (!rendering) {
            hide_error();
            focus_tab.frontend_markdown_tab();
            get_frontend_markdown();
        }
    });

    $("#markdown_tabs .diff-tab").on("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        if (!rendering) {
            hide_error();
            focus_tab.diff_tab();
            show_diff();
        }
    });

    $("#render_button").on("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        if (!rendering) {
            render_code();
        }
    });

    $("#clear_button").on("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        $("#raw_content").val("");
    });
});
