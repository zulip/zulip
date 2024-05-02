import $ from "jquery";

import render_keyboard_shortcut from "../templates/keyboard_shortcuts.hbs";
import render_markdown_help from "../templates/markdown_help.hbs";
import render_search_operator from "../templates/search_operators.hbs";

import * as browser_history from "./browser_history";
import * as common from "./common";
import * as components from "./components";
import type {Toggle} from "./components";
import {$t, $t_html} from "./i18n";
import * as keydown_util from "./keydown_util";
import * as markdown from "./markdown";
import * as overlays from "./overlays";
import * as rendered_markdown from "./rendered_markdown";
import * as scroll_util from "./scroll_util";
import {user_settings} from "./user_settings";
import * as util from "./util";

// Make it explicit that our toggler is undefined until
// set_up_toggler is called.
export let toggler: Toggle | undefined;

function format_usage_html(...keys: string[]): string {
    const get_formatted_keys: () => string = () => keys.map((key) => `<kbd>${key}</kbd>`).join("+");
    return $t_html(
        {
            defaultMessage: "(or <key-html></key-html>)",
        },
        {
            "key-html": get_formatted_keys,
        },
    );
}

const markdown_help_rows = [
    {
        markdown: "**bold**",
        usage_html: format_usage_html("Ctrl", "B"),
    },
    {
        markdown: "*italic*",
        usage_html: format_usage_html("Ctrl", "I"),
    },
    {
        markdown: "~~strikethrough~~",
    },
    {
        markdown: ":heart:",
    },
    {
        markdown: "[Zulip website](https://zulip.org)",
        usage_html: format_usage_html("Ctrl", "Shift", "L"),
    },
    {
        markdown: "#**channel name**",
        output_html: "<p><a>#channel name</a></p>",
        effect_html: "(links to a channel)",
    },
    {
        markdown: "#**channel name>topic name**",
        output_html: "<p><a>#channel name > topic name</a></p>",
        effect_html: "(links to topic)",
    },
    {
        markdown: "@**Joe Smith**",
        output_html: '<p><span class="user-mention">@Joe Smith</span></p>',
        effect_html: "(notifies Joe Smith)",
    },
    {
        markdown: "@_**Joe Smith**",
        output_html: '<p><span class="user-mention">Joe Smith</span></p>',
        effect_html: "(links to profile but doesn't notify Joe Smith)",
    },
    {
        markdown: "@*support team*",
        // Since there are no mentionable user groups that we can
        // assume exist, we use a fake data-user-group-id of 0 in
        // order to avoid upsetting the rendered_markdown.ts
        // validation logic for user group elements.
        //
        // Similar hackery is not required for user mentions as very
        // old mentions do not have data-user-id, so compatibility
        // code for that case works ... but it might be better to just
        // user your own name/user ID anyway.
        output_html:
            '<p><span class="user-group-mention" data-user-group-id="0">@support team</span></p>',
        effect_html: "(notifies <b>support team</b> group)",
    },
    {
        markdown: "@**all**",
        effect_html: "(notifies all recipients)",
    },
    {
        markdown: `\
* Milk
* Tea
  * Green tea
  * Black tea
* Coffee`,
    },
    {
        markdown: `\
1. Milk
1. Tea
1. Coffee`,
    },
    {
        markdown: "> Quoted",
    },
    {
        markdown: `\
\`\`\`quote
Quoted block
\`\`\``,
    },
    {
        markdown: `\
\`\`\`spoiler Always visible heading
This text won't be visible until the user clicks.
\`\`\``,
    },
    {
        markdown: "Some inline `code`",
    },
    {
        markdown: `\
\`\`\`
def zulip():
    print "Zulip"
\`\`\``,
    },
    {
        markdown: `\
\`\`\`python
def zulip():
    print "Zulip"
\`\`\``,
        output_html: `\
<div class="codehilite"><pre><span class="k">def</span> <span class="nf">zulip</span><span class="p">():</span>
    <span class="k">print</span> <span class="s">"Zulip"</span></pre></div>`,
    },
    {
        markdown: "Some inline math $$ e^{i \\pi} + 1 = 0 $$",
    },
    {
        markdown: `\
\`\`\`math
\\int_{0}^{1} f(x) dx
\`\`\``,
    },
    {
        markdown: "/me is busy working",
        output_html:
            '<p><span class="sender_name">Iago</span> <span class="status-message">is busy working</span></p>',
    },
    {
        markdown: "<time:2023-05-28T13:30:00+05:30>",
        output_html:
            '<p><time datetime="2023-05-28T08:00:00Z"><i class="fa fa-clock-o"></i>Sun, May 28, 2023, 1:30 PM</time></p>',
    },
    {
        markdown: `/poll What did you drink this morning?
Milk
Tea
Coffee`,
        output_html: `\
<div class="poll-widget">
    <h4 class="poll-question-header reduced-font-size">What did you drink this morning?</h4>
    <i class="fa fa-pencil poll-edit-question"></i>
    <ul class="poll-widget">
    <li>
        <button class="poll-vote">
            0
        </button>
        <span>Milk</span>
    </li>
    <li>
        <button class="poll-vote">
            0
        </button>
        <span>Tea</span>
    </li>
    <li>
        <button class="poll-vote">
            0
        </button>
        <span>Coffee</span>
    </li>
    </ul>
</div>
`,
    },
    {
        markdown: `/todo Today's tasks
Task 1: This is the first task.
Task 2: This is the second task
Last task`,
        output_html: `\
<div class="message_content rendered_markdown">
    <div class="widget-content">
        <div class="todo-widget">
            <h4>Today's tasks</h4>
            <ul class="todo-widget new-style">
                <li>
                    <label class="checkbox">
                        <div>
                            <input type="checkbox" class="task" checked="checked">
                            <span></span>
                        </div>
                        <div>
                            <strike><strong>Task 1:</strong> This is the first task.</strike>
                        </div>
                    </label>
                </li>
                <li>
                    <label class="checkbox">
                        <div>
                            <input type="checkbox" class="task">
                            <span></span>
                        </div>
                        <div>
                            <strong>Task 2:</strong> This is the second task.
                        </div>
                    </label>
                </li>
                <li>
                    <label class="checkbox">
                        <div>
                            <input type="checkbox" class="task">
                            <span></span>
                        </div>
                        <div>
                            <strong>Last task</strong>
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
    for (const row of markdown_help_rows) {
        if (row.markdown && !row.output_html) {
            const message = {
                raw_content: row.markdown,
                ...markdown.render(row.markdown),
            };
            row.output_html = util.clean_user_content_links(message.content);
        }
    }

    const $markdown_help = $(render_markdown_help({markdown_help_rows}));
    $markdown_help.find(".rendered_markdown").each(function () {
        rendered_markdown.update_elements($(this));
    });
    $(".informational-overlays .overlay-body").append($markdown_help);

    const $search_operators = $(render_search_operator());
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
        callback(_name: string, key: string) {
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

    $("#go-to-home-view-hotkey-help").toggleClass(
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
