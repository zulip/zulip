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
import * as ui from "./ui";
import {user_settings} from "./user_settings";
import * as util from "./util";

// Make it explicit that our toggler is undefined until
// set_up_toggler is called.
export let toggler;

const markdown_help_rows = [
    {
        markdown: "*italic*",
        usage_html: "(or <kbd>Ctrl</kbd>+<kbd>I</kbd>)",
    },
    {
        markdown: "**bold**",
        usage_html: "(or <kbd>Ctrl</kbd>+<kbd>B</kbd>)",
    },
    {
        markdown: "~~strikethrough~~",
    },
    {
        markdown: "[Zulip website](https://zulip.org)",
        usage_html: "(or <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>L</kbd>)",
    },
    {
        markdown: `\
* Milk
* Tea
  * Green tea
  * Black tea
  * Oolong tea
* Coffee`,
    },
    {
        markdown: `\
1. Milk
1. Tea
1. Coffee`,
    },
    {
        markdown: ":heart:",
        usage_html:
            '(and <a href="https://www.webfx.com/tools/emoji-cheat-sheet/" target="_blank" rel="noopener noreferrer">many others</a>, from the <a href="https://code.google.com/p/noto/" target="_blank" rel="noopener noreferrer">Noto Project</a>)',
    },
    {
        markdown: "@**Joe Smith**",
        usage_html: "(autocompletes from @joe)",
        output_html: '<p><span class="user-mention">@Joe Smith</span></p>',
        effect_html: "(notifies Joe Smith)",
    },
    {
        markdown: "@_**Joe Smith**",
        usage_html: "(autocompletes from @_joe)",
        output_html: '<p><span class="user-mention">Joe Smith</span></p>',
        effect_html: "(links to profile but doesn't notify Joe Smith)",
    },
    {
        markdown: "@**all**",
        effect_html: "(notifies all recipients)",
    },
    {
        markdown: "#**streamName**",
        output_html: "<p><a>#streamName</a></p>",
        effect_html: "(links to a stream)",
    },
    {
        markdown: "/me is busy working",
        output_html: '<p><span class="sender_name-in-status">Iago</span> is busy working</p>',
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
        note_html: $t_html(
            {
                defaultMessage:
                    "To add syntax highlighting to a multi-line code block, add the language's <b>first</b> <z-link>Pygments short name</z-link> after the first set of back-ticks. You can also make a code block by indenting each line with 4 spaces.",
            },
            {
                "z-link": (content_html) =>
                    `<a target="_blank" rel="noopener noreferrer" href="https://pygments.org/docs/lexers/">${content_html.join(
                        "",
                    )}</a>`,
            },
        ),
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
        markdown: "Some inline math $$ e^{i \\pi} + 1 = 0 $$",
    },
    {
        markdown: `\
\`\`\`math
\\int_{0}^{1} f(x) dx
\`\`\``,
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
        callback(name, key) {
            $(".overlay-modal").hide();
            $(`#${CSS.escape(key)}`).show();
            ui.get_scroll_element($(`#${CSS.escape(key)}`).find(".modal-body")).trigger("focus");
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
        ui.get_scroll_element($modal).prop("tabindex", 0);
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
    common.adjust_mac_shortcuts(".hotkeys_table .hotkey kbd");
    common.adjust_mac_shortcuts("#markdown-instructions kbd");
}

export function show(target) {
    if (!toggler) {
        set_up_toggler();
    }

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

    if (target) {
        toggler.goto(target);
    }
}
