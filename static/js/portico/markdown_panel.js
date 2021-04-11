import * as diff from "diff";
import * as diff2html from "diff2html";
import hljs from "highlight.js/lib/core";
import xml from "highlight.js/lib/languages/xml";
import $ from "jquery";
import * as pretty from "pretty";

import * as channel from "../channel";
import * as markdown from "../markdown";
// Importing stream_data to avoid import error
// while importing markdown_config.
import * as stream_data from "../stream_data"; // eslint-disable-line no-unused-vars
import {get_helpers} from "../markdown_config"; // eslint-disable-line import/order

// Avoid importing all the languages.
hljs.registerLanguage("xml", xml);

// Main JavaScript file for the markdown development panel at
// /devtools/markdown.

let active_tab = null;
let tabs = null;

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

function place_code(tab_name, html) {
    const tab = tabs[tab_name];
    tab.raw_html = pretty(html);
    const pretty_html = hljs.highlight(tab.raw_html, {language: "xml"}).value;
    tab.$content.html(pretty_html);
}

function render_code() {
    // Avoid rendering if the message is the same as the previous one.
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
        $(".error").text(`Error: (${status_code}) ${response.msg}`).css("display", "block");
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
    if (tabs.backend_markdown.raw_message !== message) {
        tabs.backend_markdown.raw_message = message;
        const $spinner = $(".buttons .rendering");
        channel.post({
            url: "/json/messages/render",
            data: {content: message},
            beforeSend(xhr) {
                $spinner.css("display", "inline-block");
                xhr.setRequestHeader("X-CSRFToken", $("#csrf_token").val());
            },
            success(response) {
                place_code("backend_markdown", response.rendered);
                if (active_tab === "diff") {
                    show_diff();
                }
            },
            error: handle_unsuccessful_response,
            complete() {
                $spinner.hide();
            },
        });
    }
}
function get_frontend_markdown() {
    const message = $("#raw_content").val().trim();
    if (tabs.frontend_markdown.raw_message !== message) {
        tabs.frontend_markdown.raw_message = message;
        const options = {raw_content: message};
        markdown.apply_markdown(options);
        place_code("frontend_markdown", options.content);
    }
}

function show_diff() {
    const message = $("#raw_content").val().trim();
    const $spinner = $(".buttons .rendering");

    $spinner.css("display", "inline-block");

    if (tabs.frontend_markdown.raw_message !== message) {
        get_frontend_markdown();
    }
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
    $spinner.hide();
}

// Initialization
$(() => {
    tabs = get_tabs_data();
    markdown.initialize([], get_helpers());
    focus_tab.backend_markdown_tab();

    $("#markdown_tabs .backend-markdown-tab").on("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        $(".error").hide();
        focus_tab.backend_markdown_tab();
        get_backend_markdown();
    });

    $("#markdown_tabs .frontend-markdown-tab").on("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        $(".error").hide();
        focus_tab.frontend_markdown_tab();
        get_frontend_markdown();
    });

    $("#markdown_tabs .diff-tab").on("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        $(".error").hide();
        focus_tab.diff_tab();
        show_diff();
    });

    $("#render_button").on("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        render_code();
    });

    $("#clear_button").on("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        $("#raw_content").val("");
    });
});
