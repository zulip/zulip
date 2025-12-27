import $ from "jquery";

import render_keyboard_shortcut from "../templates/keyboard_shortcuts.hbs";
import render_markdown_help from "../templates/markdown_help.hbs";
import render_search_operator from "../templates/search_operators.hbs";

import * as blueslip from "./blueslip.ts";
import * as browser_history from "./browser_history.ts";
import * as common from "./common.ts";
import * as components from "./components.ts";
import type {Toggle} from "./components.ts";
import {$t, $t_html} from "./i18n.ts";
import * as keydown_util from "./keydown_util.ts";
import * as markdown from "./markdown.ts";
import * as overlays from "./overlays.ts";
import {page_params} from "./page_params.ts";
import {postprocess_content} from "./postprocess_content.ts";
import * as rendered_markdown from "./rendered_markdown.ts";
import * as scroll_util from "./scroll_util.ts";
import {current_user} from "./state_data.ts";
import * as ui_report from "./ui_report.ts";
import {user_settings} from "./user_settings.ts";

// Make it explicit that our toggler is undefined until
// set_up_toggler is called.
export let toggler: Toggle | undefined;

function format_usage_html(...keys: string[]): string {
    return $t_html(
        {
            defaultMessage: "(or <key-html></key-html>)",
        },
        {
            "key-html": () => keys.map((key) => `<kbd>${key}</kbd>`).join("+"),
        },
    );
}

const markdown_help_rows = [
    {
        markdown: `**${$t({defaultMessage: "bold"})}**`,
        usage_html: format_usage_html("Ctrl", "B"),
    },
    {
        markdown: `*${$t({defaultMessage: "italic"})}*`,
        usage_html: format_usage_html("Ctrl", "I"),
    },
    {
        markdown: `~~${$t({defaultMessage: "strikethrough"})}~~`,
    },
    {
        markdown: ":heart:",
    },
    {
        markdown: `[${$t({defaultMessage: "Zulip website"})}](https://zulip.org)`,
        usage_html: format_usage_html("Ctrl", "Shift", "L"),
    },
    {
        markdown: `#**${$t({defaultMessage: "channel name"})}**`,
        effect_html: $t({defaultMessage: "(links to a channel)"}),
    },
    {
        markdown: `#**${$t({defaultMessage: "channel name"})}>${$t({defaultMessage: "topic name"})}**`,
        effect_html: $t({defaultMessage: "(links to topic)"}),
    },
    {
        markdown: `@**${$t({defaultMessage: "Joe Smith"})}**`,
        effect_html: $t(
            {defaultMessage: "(notifies {user})"},
            {user: $t({defaultMessage: "Joe Smith"})},
        ),
    },
    {
        markdown: `@_**${$t({defaultMessage: "Joe Smith"})}**`,
        effect_html: $t(
            {defaultMessage: "(links to profile but doesn't notify {user})"},
            {user: $t({defaultMessage: "Joe Smith"})},
        ),
    },
    {
        markdown: `@*${$t({defaultMessage: "support team"})}*`,
        effect_html: $t_html(
            {defaultMessage: "(notifies <z-user-group></z-user-group> group)"},
            {"z-user-group": () => `<b>${$t_html({defaultMessage: "support team"})}</b>`},
        ),
    },
    {
        markdown: "@**all**",
        effect_html: $t({defaultMessage: "(notifies all recipients)"}),
    },
    {
        markdown: `\
* ${$t({defaultMessage: "Milk"})}
* ${$t({defaultMessage: "Tea"})}
  * ${$t({defaultMessage: "Green tea"})}
  * ${$t({defaultMessage: "Black tea"})}
* ${$t({defaultMessage: "Coffee"})}`,
    },
    {
        markdown: `\
1. ${$t({defaultMessage: "Milk"})}
1. ${$t({defaultMessage: "Tea"})}
1. ${$t({defaultMessage: "Coffee"})}`,
    },
    {
        markdown: `> ${$t({defaultMessage: "Quoted"})}`,
    },
    {
        markdown: `\
\`\`\`quote
${$t({defaultMessage: "Quoted block"})}
\`\`\``,
    },
    {
        markdown: `\
\`\`\`spoiler ${$t({defaultMessage: "Always visible heading"})}
${$t({defaultMessage: "This text won't be visible until the user clicks."})}
\`\`\``,
    },
    {
        markdown: $t({defaultMessage: "Some inline `code`"}),
    },
    // These code block examples are chosen to include no strings needing translation.
    {
        markdown: `\
\`\`\`
def f():
    print("Zulip")
\`\`\``,
        usage_html: format_usage_html("Ctrl", "Shift", "C"),
    },
    {
        markdown: `\
\`\`\`python
def f():
    print("Zulip")
\`\`\``,
        // output_html required because we don't have pygments in the web app processor.
        output_html: `\
<div class="codehilite zulip-code-block" data-code-language="Python"><pre><div class="code-buttons-container">
    </span></div><span></span><code><span class="k">def</span><span class="w"> </span><span class="nf">f</span><span class="p">():</span>
    <span class="nb">print</span><span class="p">(</span><span class="s2">"Zulip"</span><span class="p">)</span>
</code></pre></div>`,
    },
    {
        markdown: $t(
            {defaultMessage: "Some inline math {math}"},
            {math: "$$ e^{i \\pi} + 1 = 0 $$"},
        ),
    },
    {
        markdown: `\
\`\`\`math
\\int_{0}^{1} f(x) dx
\`\`\``,
    },
    {
        markdown: `/me ${$t({defaultMessage: "is busy working"})}`,
        // output_html required since /me rendering is not done in Markdown processor.
        output_html: `<p><span class="sender_name">Iago</span> <span class="status-message">${$t({defaultMessage: "is busy working"})}</span></p>`,
    },
    {
        markdown: "<time:2023-05-28T13:30:00+05:30>",
    },
    {
        markdown: `/poll ${$t({defaultMessage: "What did you drink this morning?"})}
${$t({defaultMessage: "Milk"})}
${$t({defaultMessage: "Tea"})}
${$t({defaultMessage: "Coffee"})}`,
        // output_html required since poll rendering is done outside Markdown.
        output_html: `\
<div class="poll-widget">
    <h4 class="poll-question-header">${$t({defaultMessage: "What did you drink this morning?"})}</h4>
    <i class="fa fa-pencil poll-edit-question"></i>
    <ul class="poll-widget">
    <li>
        <button class="poll-vote">
            0
        </button>
        <span>${$t({defaultMessage: "Milk"})}</span>
    </li>
    <li>
        <button class="poll-vote">
            0
        </button>
        <span>${$t({defaultMessage: "Tea"})}</span>
    </li>
    <li>
        <button class="poll-vote">
            0
        </button>
        <span>${$t({defaultMessage: "Coffee"})}</span>
    </li>
    </ul>
</div>
`,
    },
    {
        markdown: `/todo ${$t({defaultMessage: "Today's tasks"})}
${$t({defaultMessage: "Task 1"})}: ${$t({defaultMessage: "This is the first task."})}
${$t({defaultMessage: "Task 2"})}: ${$t({defaultMessage: "This is the second task."})}
${$t({defaultMessage: "Last task"})}`,
        // output_html required since todo rendering is done outside Markdown.
        output_html: `\
<div class="message_content rendered_markdown">
    <div class="widget-content">
        <div class="todo-widget">
            <h4>${$t({defaultMessage: "Today's tasks"})}</h4>
            <ul class="todo-widget">
                <li>
                    <label class="checkbox">
                        <div>
                            <input type="checkbox" class="task" checked="checked">
                            <span class="rendered-checkbox"></span>
                        </div>
                        <div>
                            <s><strong>${$t({defaultMessage: "Task 1"})}:</strong> ${$t({defaultMessage: "This is the first task."})}</s>
                        </div>
                    </label>
                </li>
                <li>
                    <label class="checkbox">
                        <div>
                            <input type="checkbox" class="task">
                            <span class="rendered-checkbox"></span>
                        </div>
                        <div>
                            <strong>${$t({defaultMessage: "Task 2"})}:</strong> ${$t({defaultMessage: "This is the second task."})}
                        </div>
                    </label>
                </li>
                <li>
                    <label class="checkbox">
                        <div>
                            <input type="checkbox" class="task">
                            <span class="rendered-checkbox"></span>
                        </div>
                        <div>
                            <strong>${$t({defaultMessage: "Last task"})}</strong>
                        </div>
                    </label>
                </li>
            </ul>
        </div>
    </div>
</div>
`,
    },
    {
        markdown: "---",
    },
    {
        note_html: $t_html(
            {
                defaultMessage:
                    "You can also make <z-link>tables</z-link> with this <z-link>Markdown-ish table syntax</z-link>.",
            },
            {
                "z-link": (content_html) =>
                    `<a target="_blank" rel="noopener noreferrer" href="https://github.com/adam-p/markdown-here/wiki/Markdown-Cheatsheet#wiki-tables">${content_html.join(
                        "",
                    )}</a>`,
            },
        ),
    },
];

export function set_up_toggler(): void {
    const helper_config: markdown.MarkdownHelpers = {
        ...markdown.web_app_helpers!,
        get_actual_name_from_user_id() {
            return $t({defaultMessage: "Joe Smith"});
        },
        get_user_id_from_name() {
            return 0;
        },
        get_user_group_from_name(name) {
            return {id: 0, name};
        },
        is_member_of_user_group() {
            return true;
        },
        stream_hash() {
            return "";
        },
        get_stream_by_name(stream_name) {
            return {stream_id: 0, name: stream_name};
        },
    };
    for (const row of markdown_help_rows) {
        if (row.markdown && !row.output_html) {
            const message = {
                raw_content: row.markdown,
                ...markdown.render(row.markdown, helper_config),
            };
            const rendered_content = new DOMParser().parseFromString(message.content, "text/html");
            // We remove all attributes from stream links in the markdown content since
            // we just want to display a mock template.
            for (const elt of rendered_content.querySelectorAll("a[data-stream-id]")) {
                const anchor_element = document.createElement("a");
                anchor_element.innerHTML = elt.innerHTML;
                elt.replaceWith(anchor_element);
            }
            message.content = rendered_content.body.innerHTML;
            row.output_html = postprocess_content(message.content);
        }
    }

    const $markdown_help = $(render_markdown_help({markdown_help_rows}));
    $markdown_help.find(".rendered_markdown").each(function () {
        rendered_markdown.update_elements($(this));
    });
    $(".informational-overlays .overlay-body").append($markdown_help);

    const $search_operators = $(
        render_search_operator({
            can_access_all_public_channels: !page_params.is_spectator && !current_user.is_guest,
        }),
    );
    $(".informational-overlays .overlay-body").append($search_operators);

    const $keyboard_shortcuts = $(render_keyboard_shortcut());
    $(".informational-overlays .overlay-body").append($keyboard_shortcuts);

    // Handle print button clicks for all info overlay panes
    $(document).on("click", ".print-help-pane", function (event) {
        event.preventDefault();
        event.stopPropagation();

        // Get which pane we're printing
        const $button = $(this);
        const paneId = $button.attr("data-pane-id") ?? "keyboard-shortcuts";

        const $pane = $(`#${CSS.escape(paneId)} .overlay-scroll-container`);

        if ($pane.length === 0) {
            blueslip.warn("Pane not found", {pane_id: paneId});
            return;
        }

        // Get pane title and content
        let title: string;
        const content = $pane.html() ?? "";

        switch (paneId) {
            case "keyboard-shortcuts":
                title = $t({defaultMessage: "Keyboard shortcuts"});
                break;
            case "message-formatting":
                title = $t({defaultMessage: "Message formatting"});
                break;
            case "search-operators":
                title = $t({defaultMessage: "Search filters"});
                break;
            default:
                title = $t({defaultMessage: "Help"});
                break;
        }

        // Open print window
        const printWindow = window.open("", "_blank");
        if (!printWindow?.document) {
            const $status_box = $("<div>").addClass("status-box").appendTo("body");
            ui_report.message(
                $t({defaultMessage: "Print window blocked. Please allow popups for this site."}),
                $status_box,
                "alert",
                3000,
            );
            return;
        }

        const doc = printWindow.document;

        // Reset document
        doc.documentElement.innerHTML = "<!DOCTYPE html><html><head></head><body></body></html>";

        // Fill <head>
        doc.head.innerHTML = `
        <meta charset="UTF-8">
        <title>${title}</title>
        <style>
            body {
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
                margin: 20px;
                color: #333;
            }
            h1 {
                margin-top: 0;
                font-size: 28px;
                border-bottom: 2px solid #087e8b;
                padding-bottom: 10px;
            }
            table {
                border-collapse: collapse;
                width: 100%;
                margin-bottom: 20px;
                border: 1px solid #ddd;
            }
            th {
                background-color: #f5f5f5;
                font-weight: bold;
                border: 1px solid #ddd;
                padding: 12px;
                text-align: left;
            }
            td {
                border: 1px solid #ddd;
                padding: 10px;
            }
            tr:nth-child(even) {
                background-color: #fafafa;
            }
            .hotkey {
                font-family: "Courier New", monospace;
                background-color: #e8e8e8;
                padding: 3px 8px;
                border-radius: 4px;
                font-weight: 500;
            }
            kbd {
                font-family: "Courier New", monospace;
                background-color: #e8e8e8;
                border: 1px solid #999;
                border-radius: 3px;
                padding: 2px 6px;
                margin: 0 2px;
            }
            .definition { width: 50%; }
            .operator { font-family: monospace; }
            .operator_value { background-color: #f0f0f0; padding: 2px 4px; }
            hr { border: none; border-top: 1px solid #ddd; margin: 20px 0; }
            a { color: #087e8b; text-decoration: none; }

            @media print {
                body { margin: 0; padding: 10mm; }
                a { color: #087e8b; }
            }
        </style>
    `;

        // Fill <body>
        const h1 = doc.createElement("h1");
        h1.textContent = title;
        doc.body.append(h1);

        const div = doc.createElement("div");
        div.innerHTML = content;
        doc.body.append(div);

        // Trigger print after window loads
        printWindow.addEventListener("load", () => {
            printWindow.print();
        });
    });

    const opts = {
        selected: 0,
        child_wants_focus: true,
        values: [
            {label: $t({defaultMessage: "Keyboard shortcuts"}), key: "keyboard-shortcuts"},
            {label: $t({defaultMessage: "Message formatting"}), key: "message-formatting"},
            {label: $t({defaultMessage: "Search filters"}), key: "search-operators"},
        ],
        callback(_name: string | undefined, key: string) {
            $(".overlay-modal").hide();
            $(`#${CSS.escape(key)}`).show();
            scroll_util
                .get_scroll_element($(`#${CSS.escape(key)}`).find(".overlay-scroll-container"))
                .trigger("focus");
        },
    };

    toggler = components.toggle(opts);
    const $elem = toggler.get();
    $elem.addClass("large allow-overflow");

    const modals = opts.values.map((item) => {
        const key = item.key; // e.g. message-formatting
        const $modal = $(`#${CSS.escape(key)}`).find(".overlay-scroll-container");
        return $modal;
    });

    for (const $modal of modals) {
        scroll_util.get_scroll_element($modal).prop("tabindex", 0);
        keydown_util.handle({
            $elem: $modal,
            handlers: {
                ArrowLeft: toggler.maybe_go_left,
                ArrowRight: toggler.maybe_go_right,
            },
        });
    }

    $(".informational-overlays .overlay-tabs").append($elem);

    $("#keyboard-shortcuts .go-to-home-view-hotkey-help").toggleClass(
        "notdisplayed",
        !user_settings.web_escape_navigates_to_home_view,
    );
    common.adjust_mac_kbd_tags(".hotkeys_table .hotkey kbd");
    common.adjust_mac_kbd_tags("#markdown-instructions kbd");
}

export function show(target: string | undefined): void {
    const $overlay = $(".informational-overlays");

    if (!$overlay.hasClass("show")) {
        overlays.open_overlay({
            name: "informationalOverlays",
            $overlay,
            on_close() {
                browser_history.exit_overlay();
            },
        });
    }

    if (!toggler) {
        set_up_toggler();
    }

    if (target) {
        toggler!.goto(target);
    }
}
