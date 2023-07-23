import $ from "jquery";

import render_keyboard_shortcut from "../templates/keyboard_shortcuts.hbs";
import render_markdown_help from "../templates/markdown_help.hbs";
import render_search_operator from "../templates/search_operators.hbs";

import * as browser_history from "./browser_history";
import * as common from "./common";
import * as components from "./components";
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
export let toggler;

function format_usage_html(...keys) {
    const get_formatted_keys = () => keys.map((key) => `<kbd>${key}</kbd>`).join("+");
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
        markdown: $t(
            {
                defaultMessage: "{markdown_syntax}bold{markdown_syntax}",
            },
            {markdown_syntax: "**"},
        ),
        usage_html: format_usage_html("Ctrl", "B"),
    },
    {
        markdown: $t(
            {
                defaultMessage: "{markdown_syntax}italic{markdown_syntax}",
            },
            {markdown_syntax: "*"},
        ),
        usage_html: format_usage_html("Ctrl", "I"),
    },
    {
        markdown: $t(
            {
                defaultMessage: "{markdown_syntax}strikethrough{markdown_syntax}",
            },
            {markdown_syntax: "~~"},
        ),
    },
    {
        markdown: ":heart:",
    },
    {
        markdown: $t(
            {
                defaultMessage: "{open_markdown_syntax}Zulip website{close_markdown_syntax}",
            },
            {open_markdown_syntax: "[", close_markdown_syntax: "](https://zulip.org)"},
        ),
        usage_html: format_usage_html("Ctrl", "Shift", "L"),
    },
    {
        markdown: $t(
            {
                defaultMessage: "{open_markdown_syntax}stream name{close_markdown_syntax}",
            },
            {open_markdown_syntax: "#**", close_markdown_syntax: "**"},
        ),
        output_html: "<p><a>#stream name</a></p>",
        effect_html: "(links to a stream)",
    },
    {
        markdown: $t(
            {
                defaultMessage:
                    "{open_markdown_syntax}stream name>topic name{close_markdown_syntax}",
            },
            {open_markdown_syntax: "#**", close_markdown_syntax: "**"},
        ),
        output_html: "<p><a>#stream name > topic name</a></p>",
        effect_html: "(links to topic)",
    },
    {
        markdown: $t(
            {
                defaultMessage: "{open_markdown_syntax}Joe Smith{close_markdown_syntax}",
            },
            {open_markdown_syntax: "@**", close_markdown_syntax: "**"},
        ),
        output_html: '<p><span class="user-mention">@Joe Smith</span></p>',
        effect_html: "(notifies Joe Smith)",
    },
    {
        markdown: $t(
            {
                defaultMessage: "{open_markdown_syntax}Joe Smith{close_markdown_syntax}",
            },
            {open_markdown_syntax: "@_**", close_markdown_syntax: "**"},
        ),
        output_html: '<p><span class="user-mention">Joe Smith</span></p>',
        effect_html: "(links to profile but doesn't notify Joe Smith)",
    },
    {
        markdown: $t(
            {
                defaultMessage: "{open_markdown_syntax}support team{close_markdown_syntax}",
            },
            {open_markdown_syntax: "@*", close_markdown_syntax: "*"},
        ),
        output_html: '<p><span class="user-group-mention">@support team</span></p>',
        effect_html: "(notifies <b>support team</b> group)",
    },
    {
        markdown: $t(
            {
                defaultMessage: "{open_markdown_syntax}all{close_markdown_syntax}",
            },
            {open_markdown_syntax: "@**", close_markdown_syntax: "**"},
        ),
        effect_html: "(notifies all recipients)",
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
        markdown: $t(
            {
                defaultMessage: "{quote_markdown_syntax} Quoted",
            },
            {quote_markdown_syntax: ">"},
        ),
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
        markdown: $t(
            {defaultMessage: "Some inline {code_markdown_syntax}"},
            {code_markdown_syntax: "`code`"},
        ),
    },
    {
        markdown: `\
\`\`\`
def ${$t({defaultMessage: "zulip"})}():
    print "${$t({defaultMessage: "Zulip"})}"
\`\`\``,
    },
    {
        markdown: `\
\`\`\`python
def ${$t({defaultMessage: "zulip"})}():
    print "${$t({defaultMessage: "Zulip"})}"
\`\`\``,
        output_html: `\
<div class="codehilite"><pre><span class="k">def</span> <span class="nf">zulip</span><span class="p">():</span>
    <span class="k">print</span> <span class="s">"Zulip"</span></pre></div>`,
    },
    {
        markdown: $t(
            {
                defaultMessage: "Some inline math {math_markdown_syntax}",
            },
            {math_markdown_syntax: "$$ e^{i \\pi} + 1 = 0 $$"},
        ),
    },
    {
        markdown: `\
\`\`\`math
\\int_{0}^{1} f(x) dx
\`\`\``,
    },
    {
        markdown: $t(
            {
                defaultMessage: "{me_markdown_syntax} is busy working",
            },
            {me_markdown_syntax: "/me"},
        ),
        output_html:
            '<p><span class="sender_name">Iago</span> <span class="status-message">is busy working</span></p>',
    },
    {
        markdown: "<time:2023-05-28T13:30:00+05:30>",
        output_html: '<time datetime="2023-05-28T13:30:00+05:30"></time>',
    },
    {
        markdown: `/poll ${$t({defaultMessage: "What did you drink this morning?"})}
${$t({defaultMessage: "Milk"})}
${$t({defaultMessage: "Tea"})}
${$t({defaultMessage: "Coffee"})}`,
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
        markdown: "/todo",
        output_html: `\
<div class="message_content rendered_markdown">
   <div class="widget-content">
      <div class="todo-widget">
        <h4>Task list</h4>
        <ul class="todo-widget new-style">
            <li>
                <label class="checkbox">
                    <div>
                        <input type="checkbox" class="task">
                        <span></span>
                    </div>
                    <div>
                        <strong>Submit final budget</strong> - Due Friday
                    </div>
                </label>
            </li>
            <li>
                <label class="checkbox">
                    <div>
                        <input type="checkbox" class="task" checked="checked">
                        <span></span>
                    </div>
                    <del><em><strong>Share draft budget</strong> - By Tuesday</em></del>
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

export function set_up_toggler() {
    for (const row of markdown_help_rows) {
        if (row.markdown && !row.output_html) {
            const message = {raw_content: row.markdown};
            markdown.apply_markdown(message);
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
        callback(_name, key) {
            $(".overlay-modal").hide();
            $(`#${CSS.escape(key)}`).show();
            scroll_util
                .get_scroll_element($(`#${CSS.escape(key)}`).find(".modal-body"))
                .trigger("focus");
        },
    };

    toggler = components.toggle(opts);
    const $elem = toggler.get();
    $elem.addClass("large allow-overflow");

    const modals = opts.values.map((item) => {
        const key = item.key; // e.g. message-formatting
        const $modal = $(`#${CSS.escape(key)}`).find(".modal-body");
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

    $("#go-to-default-view-hotkey-help").toggleClass(
        "notdisplayed",
        !user_settings.escape_navigates_to_default_view,
    );
    common.adjust_mac_kbd_tags(".hotkeys_table .hotkey kbd");
    common.adjust_mac_kbd_tags("#markdown-instructions kbd");
}

export function show(target) {
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
        toggler.goto(target);
    }
}
