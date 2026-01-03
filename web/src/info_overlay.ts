import $ from "jquery";

import render_keyboard_shortcut from "../templates/keyboard_shortcuts.hbs";
import render_markdown_help from "../templates/markdown_help.hbs";
import render_search_operator from "../templates/search_operators.hbs";
import render_status_message_example from "../templates/status_message_example.hbs";
import render_poll_widget_example from "../templates/widgets/poll_widget_example.hbs";
import render_todo_widget_example from "../templates/widgets/todo_widget_example.hbs";

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

export function printPane(paneId: string): void {
    const $pane = $(`#${CSS.escape(paneId)} .overlay-scroll-container`);
    if ($pane.length === 0) {
        blueslip.warn("printPane: pane not found", {paneId});
        return;
    }

    const titleMap: Record<string, string> = {
        "keyboard-shortcuts": $t({defaultMessage: "Keyboard shortcuts"}),
        "message-formatting": $t({defaultMessage: "Message formatting"}),
        "search-operators": $t({defaultMessage: "Search filters"}),
    };
    const title = titleMap[paneId] ?? $t({defaultMessage: "Help"});

    // Create print container
    const $printContainer = $("<div>")
        .attr("id", "zulip-print-container")
        .attr("aria-hidden", "true")
        .css("display", "none");

    // Add title
    const $title = $("<h1>").addClass("zulip-print-title").text(title);
    $printContainer.append($title);

    // Clone the pane to capture all content
    const $clone = $pane.clone(true, true);

    // Remove scrollbars or wrapper elements
    $clone.find(".simplebar-track, .simplebar-scrollbar").remove();

    // Extract inner content only (unwrapped), works for SimpleBar and default
    const $scrollContent =
        $clone.find(".simplebar-content").length > 0
            ? $clone.find(".simplebar-content").contents()
            : $clone.contents();

    // Append extracted content to print container
    const $body = $("<div>").addClass("zulip-print-body").append($scrollContent);
    $printContainer.append($body);

    // Add print container to document
    $("body").append($printContainer);

    // Print-specific CSS
    const printCss = `
@media print {
  body > * { display: none !important; }
  #zulip-print-container {
    display: block !important;
    position: static !important;
    width: auto !important;
    margin: 0;
    padding: 12mm !important;
  }
  #zulip-print-container .overlay-scroll-container {
    overflow: visible !important;
    max-height: none !important;
  }
  #zulip-print-container table {
    border-collapse: collapse;
    width: 100%;
    margin-bottom: 8px;
  }
  #zulip-print-container th,
  #zulip-print-container td {
    border: 1px solid #dcdcdc;
    padding: 8px;
    text-align: left;
    vertical-align: top;
  }
  #zulip-print-container th {
    background-color: #f5f5f5;
    font-weight: 600;
  }
  #zulip-print-container kbd {
    background: #f0f0f0;
    border: 1px solid #999;
    padding: 2px 6px;
    border-radius: 3px;
    font-family: monospace;
    font-size: 0.95em;
  }
  #zulip-print-container .zulip-print-title {
    font-size: 22px;
    margin: 0 0 12px 0;
    color: #222;
  }
}
`;

    // Inject CSS
    const styleEl = document.createElement("style");
    styleEl.setAttribute("id", "zulip-temp-print-style");
    styleEl.append(printCss);
    document.head.append(styleEl);

    // Cleanup function
    const cleanup = (): void => {
        $("#zulip-print-container").remove();
        const el = document.querySelector("#zulip-temp-print-style");
        if (el) {
            el.remove();
        }
        window.removeEventListener("afterprint", cleanup);
    };

    // Attach afterprint
    window.addEventListener("afterprint", cleanup);

    // Fallback cleanup if afterprint doesn’t fire
    const fallbackTimeout = window.setTimeout(() => {
        cleanup();
        window.clearTimeout(fallbackTimeout);
    }, 60_000);

    // Make container visible before printing
    $("#zulip-print-container").css("display", "block");

    try {
        window.print();
    } catch {
        cleanup();
        ui_report.error(
            $t({defaultMessage: "Unable to open print dialog."}),
            undefined,
            $("#status"),
        );
    }
}

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
        output_html: render_status_message_example(),
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
        output_html: render_poll_widget_example(),
    },
    {
        markdown: `/todo ${$t({defaultMessage: "Today's tasks"})}
${$t({defaultMessage: "Task 1"})}: ${$t({defaultMessage: "This is the first task."})}
${$t({defaultMessage: "Task 2"})}: ${$t({defaultMessage: "This is the second task."})}
${$t({defaultMessage: "Last task"})}`,
        // output_html required since todo rendering is done outside Markdown.
        output_html: render_todo_widget_example(),
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

function informationalOverlayPrintKeyHandler(e: JQuery.KeyDownEvent): void {
    const isPrintKey = (e.ctrlKey || e.metaKey) && (e.key === "p" || e.key === "P");
    if (!isPrintKey) {
        return;
    }
    // Only act when overlay is visible
    const $overlay = $(".informational-overlays");
    if (!$overlay.hasClass("show")) {
        return;
    }

    e.preventDefault();
    e.stopPropagation();

    // Determine which overlay modal is visible; pick the first visible overlay-modal inside the overlay-body
    const $visibleModal = $overlay
        .find(".overlay-modal")
        .filter(function () {
            return this instanceof HTMLElement && this.offsetParent !== null;
        })
        .first();

    let activePaneId = "keyboard-shortcuts"; // default
    if ($visibleModal.length > 0) {
        const attrId = $visibleModal.attr("id");
        if (attrId) {
            activePaneId = attrId;
        }
    }

    printPane(activePaneId);
}

export function show(target: string | undefined): void {
    const $overlay = $(".informational-overlays");

    if (!$overlay.hasClass("show")) {
        overlays.open_overlay({
            name: "informationalOverlays",
            $overlay,
            on_close() {
                browser_history.exit_overlay();
                // remove our key handler to avoid leaks
                $(document).off("keydown", informationalOverlayPrintKeyHandler);
            },
        });
    }

    if (!toggler) {
        set_up_toggler();
    }

    // Attach handler (avoid duplicate attachments)
    $(document).off("keydown", informationalOverlayPrintKeyHandler);
    $(document).on("keydown", informationalOverlayPrintKeyHandler);

    if (target) {
        toggler!.goto(target);
    }
}
