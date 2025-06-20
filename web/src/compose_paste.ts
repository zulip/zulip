import isUrl from "is-url";
import $ from "jquery";
import _ from "lodash";
import assert from "minimalistic-assert";
import {insertTextIntoField} from "text-field-edit";
import TurndownService from "turndown";

import * as compose_ui from "./compose_ui.ts";
import * as hash_util from "./hash_util.ts";
import * as stream_data from "./stream_data.ts";
import * as topic_link_util from "./topic_link_util.ts";
import * as util from "./util.ts";

declare global {
    // eslint-disable-next-line @typescript-eslint/consistent-type-definitions
    interface HTMLElementTagNameMap {
        math: HTMLElement;
        strike: HTMLElement;
    }
}

function deduplicate_newlines(attribute: string): string {
    // We replace any occurrences of one or more consecutive newlines followed by
    // zero or more whitespace characters with a single newline character.
    return attribute ? attribute.replaceAll(/(\n+\s*)+/g, "\n") : "";
}

function image_to_zulip_markdown(
    _content: string,
    node: Element | Document | DocumentFragment,
): string {
    assert(node instanceof Element);
    if (node.nodeName === "IMG" && node.classList.contains("emoji") && node.hasAttribute("alt")) {
        // For Zulip's custom emoji
        return node.getAttribute("alt") ?? "";
    }
    const src = node.getAttribute("src") ?? node.getAttribute("href") ?? "";
    const title = deduplicate_newlines(node.getAttribute("title") ?? "");
    // Using Zulip's link like syntax for images
    return src ? "![" + title + "](" + src + ")" : (node.getAttribute("alt") ?? "");
}

// Returns 2 or more if there are multiple valid text nodes in the tree.
function check_multiple_text_nodes(child_nodes: ChildNode[]): number {
    let textful_nodes = 0;

    for (const child of child_nodes) {
        // We do not consider empty childNodes, comments and
        // childNodes containing newlines.
        if (child.nodeValue?.trim() === "" || child.nodeName === "#comment") {
            continue;
        }

        if (child.nodeValue && child.nodeType === Node.TEXT_NODE) {
            textful_nodes += 1;
            if (textful_nodes >= 2) {
                return textful_nodes;
            }
        }

        textful_nodes += check_multiple_text_nodes([...child.childNodes]);

        if (textful_nodes >= 2) {
            return textful_nodes;
        }
    }

    return textful_nodes;
}

function within_single_element(html_fragment: HTMLElement): boolean {
    return (
        html_fragment.childNodes.length === 1 &&
        html_fragment.firstElementChild !== null &&
        html_fragment.firstElementChild.innerHTML !== ""
    );
}

// We count textful child nodes to decide if styles should
// be removed (e.g., for headings that contain <br> and other tags in the fragment).
// Empty nodes like comments or newline-only text should not be counted.
function has_single_textful_child_node(html_fragment: HTMLElement): boolean {
    let textful_nodes = 0;
    textful_nodes = check_multiple_text_nodes([...html_fragment.childNodes]);
    if (textful_nodes >= 2) {
        return false;
    }
    return (
        html_fragment.firstElementChild !== null && html_fragment.firstElementChild.innerHTML !== ""
    );
}

function get_the_only_textful_child_content(child_nodes: ChildNode[]): string | null {
    for (const child of child_nodes) {
        if (child.nodeValue?.trim() === "" || child.nodeName === "#comment") {
            continue;
        }

        if (child.nodeValue && child.nodeType === Node.TEXT_NODE) {
            // We return directly, as it is already verified that exactly one
            // such text node exists.
            return child.nodeValue;
        }
        const child_text_node = get_the_only_textful_child_content([...child.childNodes]);
        if (child_text_node) {
            return child_text_node;
        }
    }
    return null;
}

export function is_white_space_pre(paste_html: string): boolean {
    const html_fragment = new DOMParser()
        .parseFromString(paste_html, "text/html")
        .querySelector("body");
    assert(html_fragment !== null);
    return (
        within_single_element(html_fragment) &&
        html_fragment.firstElementChild instanceof HTMLElement &&
        html_fragment.firstElementChild.style.whiteSpace === "pre"
    );
}

function is_from_excel(html_fragment: HTMLBodyElement): boolean {
    const html_tag = html_fragment.parentElement;
    if (!html_tag || html_tag.nodeName !== "HTML") {
        return false;
    }

    const excel_namespaces = [
        "urn:schemas-microsoft-com:office:excel",
        "urn:schemas-microsoft-com:office:office",
    ];

    const has_excel_metadata = [...html_tag.querySelectorAll("meta")].some(
        (meta) =>
            (meta.name === "ProgId" && meta.content === "Excel.Sheet") ||
            (meta.name === "Generator" && meta.content?.includes("Microsoft Excel")),
    );
    if (!has_excel_metadata) {
        return false;
    }

    if (!html_tag.querySelector("[class^='xl']")) {
        return false;
    }

    const html_outer = html_tag.outerHTML;

    if (!html_outer.includes("<!--StartFragment-->")) {
        return false;
    }

    if (!excel_namespaces.some((ns) => html_outer.includes(ns))) {
        return false;
    }

    return true;
}

export function is_single_image(paste_html: string): boolean {
    const html_fragment = new DOMParser()
        .parseFromString(paste_html, "text/html")
        .querySelector("body");
    assert(html_fragment !== null);
    return (
        is_from_excel(html_fragment) ||
        (html_fragment.childNodes.length === 1 &&
            html_fragment.firstElementChild !== null &&
            html_fragment.firstElementChild.nodeName === "IMG")
    );
}

export function paste_handler_converter(
    paste_html: string,
    $textarea?: JQuery<HTMLTextAreaElement>,
): string {
    const copied_html_fragment = new DOMParser()
        .parseFromString(paste_html, "text/html")
        .querySelector("body");
    assert(copied_html_fragment !== null);

    const has_single_child_with_valid_text = has_single_textful_child_node(copied_html_fragment);

    const outer_elements_to_retain = ["PRE", "UL", "OL", "A", "CODE"];
    // If the entire selection copied is within a single HTML element (like an
    // `h1`), we don't want to retain its styling, except when it is needed to
    // identify the intended structure of the copied content.
    if (
        has_single_child_with_valid_text &&
        copied_html_fragment.firstElementChild !== null &&
        !outer_elements_to_retain.includes(copied_html_fragment.firstElementChild.nodeName)
    ) {
        // This will always return some text as it is already ensured
        // that such a text node exists in `has_single_textful_child_node`.
        const text_content = get_the_only_textful_child_content([...copied_html_fragment.children]);
        if (text_content) {
            return text_content;
        }
        // Ideally, this should never happen.
        // Just for fallback in case it does.
        paste_html = copied_html_fragment.firstElementChild.innerHTML;
    }

    // turning off escaping (for now) to remove extra `/`
    TurndownService.prototype.escape = (string) => string;

    const turndownService = new TurndownService({
        emDelimiter: "*",
        codeBlockStyle: "fenced",
        headingStyle: "atx",
        br: "",
    });
    turndownService.addRule("style", {
        filter: "style",
        replacement() {
            return "";
        },
    });
    turndownService.addRule("strikethrough", {
        filter: ["del", "s", "strike"],
        replacement(content) {
            return "~~" + content + "~~";
        },
    });
    turndownService.addRule("links", {
        filter: ["a"],
        replacement(content, node) {
            assert(node instanceof HTMLAnchorElement);
            if (node.href === content) {
                // Checks for raw links without custom text.
                return content;
            }
            if (node.childNodes.length === 1 && node.firstChild!.nodeName === "IMG") {
                // ignore link's url if it only has an image
                return content;
            }
            return "[" + content + "](" + node.href + ")";
        },
    });
    turndownService.addRule("listItem", {
        // We override the original upstream implementation of this rule
        // to have a custom indent of 2 spaces for list items, instead of
        // the default 4 spaces. Everything else is the same as upstream.
        filter: "li",
        replacement(content, node) {
            content = content
                .replace(/^\n+/, "") // remove leading newlines
                .replace(/\n+$/, "\n") // replace trailing newlines with just a single one
                .replaceAll(/\n/gm, "\n  "); // custom 2 space indent
            let prefix = "* ";
            const parent = node.parentElement;
            assert(parent !== null);
            if (parent.nodeName === "OL") {
                const start = parent.getAttribute("start");
                const index = Array.prototype.indexOf.call(parent.children, node);
                prefix = (start ? Number(start) + index : index + 1) + ". ";
            }
            return prefix + content + (node.nextSibling && !content.endsWith("\n") ? "\n" : "");
        },
    });

    /*
        Below lies the the thought process behind the parsing for math blocks and inline math expressions.

        The general structure of the katex-displays i.e. math blocks is:
        <p>
            span.katex-display(start expression 1)
                span.katex
                    nested stuff we don't really care about while parsing
                        annotation(contains the expression)
            span.katex-display(start expression 2)
                (same as above)
        '
        '
        '
        </p>
        A katex-display is present for every expression that is separated by two or more newlines in md.
        We also have to adjust our markdown for empty katex-displays generated due to excessive newlines between two
        expressions.

        The trick in case of the math blocks is approving all the katex displays
        instead of just the first one.
        This helps prevent the remaining katex display texts being addressed as
        text nodes and getting appended to the end unnecessarily.
        Then in the replacement function only process the parent <p> tag's immediate children only once.
        See : https://github.com/user-attachments/files/18058052/katex-display-logic.pdf for an example.

        We make use of a set to keep track whether the parent p is already processed in both the cases.

        In case of inline math expressions, the structure is same as math blocks.
        Instead of katex-displays being the immediate children of p, we have span.katex.

        For more information:
        https://chat.zulip.org/#narrow/channel/9-issues/topic/Replying.20to.20highlighted.20text.2C.20LaTeX.20is.20not.20preserved.20.2331608/near/1991687
    */

    const processed_math_block_parents = new Set();
    turndownService.addRule("katex-math-block", {
        filter(node) {
            if (
                node.classList.contains("katex-display") &&
                !node.closest(".katex-display > .katex-display")
            ) {
                return true;
            }

            return false;
        },
        replacement(content: string, node) {
            assert(node instanceof HTMLElement);
            let math_block_markdown = "```math\n";
            const parent = node.parentElement!;
            if (processed_math_block_parents.has(parent)) {
                return "";
            }
            processed_math_block_parents.add(parent);
            let consecutive_empty_display_count = 0;
            for (const child of parent.children) {
                const annotation_element = child.querySelector(
                    '.katex-mathml annotation[encoding="application/x-tex"]',
                );
                if (annotation_element?.textContent) {
                    const katex_source = annotation_element.textContent.trim();
                    math_block_markdown += katex_source + "\n\n";
                    consecutive_empty_display_count = 0;
                } else {
                    // Handling cases where math block is selected directly without any preceding text.
                    // The initial katex display doesn't have the annotation when selection is done in this manner.
                    if (
                        child.classList.contains("katex-display") &&
                        child.querySelector("math")?.textContent !== ""
                    ) {
                        math_block_markdown += content + "\n\n";
                        continue;
                    }
                    if (consecutive_empty_display_count === 0) {
                        math_block_markdown += "\n\n\n";
                    } else {
                        math_block_markdown += "\n\n";
                    }
                    consecutive_empty_display_count += 1;
                }
            }
            // Don't add extra newline at the end
            math_block_markdown = math_block_markdown.slice(0, -1);
            return (math_block_markdown += "```");
        },
    });

    turndownService.addRule("katex-inline-math", {
        filter(node) {
            if (node.classList.contains("katex-mathml") || node.classList.contains("katex-html")) {
                // Check if this lies within a `.katex-display` which
                // is processed as a math block.
                const grand_parent = node.parentElement?.parentElement;
                if (grand_parent?.classList.contains("katex-display")) {
                    // This is already processed by the math block rule.
                    return false;
                }
                return true;
            }
            return false;
        },
        replacement(content, node: Node) {
            assert(node instanceof HTMLElement);
            if (node.classList.contains("katex-html")) {
                return "";
            }
            const annotation_element = node.querySelector(
                `annotation[encoding="application/x-tex"]`,
            );
            const katex_source = annotation_element?.textContent?.trim() ?? content;
            return `$$${katex_source}$$`;
        },
    });

    turndownService.addRule("zulipImagePreview", {
        filter(node) {
            // select image previews in Zulip messages
            return (
                node.classList.contains("message_inline_image") && node.firstChild?.nodeName === "A"
            );
        },

        replacement(content, node) {
            // We parse the copied html to then check if the generating link (which, if
            // present, always comes before the preview in the copied html) is also there.

            // If the 1st element with the same image link in the copied html
            // does not have the `message_inline_image` class, it means it is the generating
            // link, and not the preview, meaning the generating link is copied as well.
            const copied_html = new DOMParser().parseFromString(paste_html, "text/html");
            let href;
            if (
                node.firstElementChild === null ||
                (href = node.firstElementChild.getAttribute("href")) === null ||
                !copied_html
                    .querySelector("a[href='" + CSS.escape(href) + "']")
                    ?.parentElement?.classList.contains("message_inline_image")
            ) {
                // We skip previews which have their generating link copied too, to avoid
                // double pasting the same link.
                return "";
            }
            return image_to_zulip_markdown(content, node.firstElementChild);
        },
    });
    turndownService.addRule("images", {
        filter: "img",

        replacement: image_to_zulip_markdown,
    });

    // We override the original upstream implementation of this rule to make
    // several tweaks:
    // - We turn any single line code blocks into inline markdown code.
    // - We generalise the filter condition to allow a `pre` element with a
    // `code` element as its only non-empty child, which applies to Zulip code
    // blocks too.
    // - For Zulip code blocks, we extract the language of the code block (if
    // any) correctly.
    // - We don't do any conversion to code blocks if the user seems to already
    // be trying to create a codeblock (i.e. the cursor in the composebox is
    // following a "`").
    // Everything else works the same.
    turndownService.addRule("fencedCodeBlock", {
        filter(node, options) {
            let text_children;
            return (
                options.codeBlockStyle === "fenced" &&
                node.nodeName === "PRE" &&
                (text_children = [...node.childNodes].filter(
                    (child) => child.textContent !== null && child.textContent.trim() !== "",
                )).length === 1 &&
                text_children[0]?.nodeName === "CODE"
            );
        },

        replacement(content, node, options) {
            assert(node instanceof HTMLElement);
            const codeElement = [...node.children].find((child) => child.nodeName === "CODE");
            assert(codeElement !== undefined);
            const code = codeElement.textContent;
            assert(code !== null);

            // We convert single line code inside a code block to inline markdown code,
            // and the code for this is taken from upstream's `code` rule.
            if (!code.includes("\n")) {
                // If the cursor is just after a backtick, then we don't add extra backticks.
                if (
                    $textarea &&
                    $textarea.caret() !== 0 &&
                    $textarea.val()?.at($textarea.caret() - 1) === "`"
                ) {
                    return content;
                }
                if (!code) {
                    return "";
                }
                const extraSpace = /^`|^ .*?[^ ].* $|`$/.test(code) ? " " : "";

                // Pick the shortest sequence of backticks that is not found in the code
                // to be the delimiter.
                let delimiter = "`";
                const matches: string[] = code.match(/`+/gm) ?? [];
                while (matches.includes(delimiter)) {
                    delimiter = delimiter + "`";
                }

                return delimiter + extraSpace + code + extraSpace + delimiter;
            }

            const className = codeElement.getAttribute("class") ?? "";
            const language = node.parentElement?.classList.contains("zulip-code-block")
                ? (node.closest<HTMLElement>(".codehilite")?.dataset?.codeLanguage ?? "")
                : (/language-(\S+)/.exec(className) ?? [null, ""])[1];

            assert(options.fence !== undefined);
            const fenceChar = options.fence.charAt(0);
            let fenceSize = 3;
            const fenceInCodeRegex = new RegExp("^" + fenceChar + "{3,}", "gm");

            let match;
            while ((match = fenceInCodeRegex.exec(code))) {
                if (match[0].length >= fenceSize) {
                    fenceSize = match[0].length + 1;
                }
            }

            const fence = fenceChar.repeat(fenceSize);

            return (
                "\n\n" + fence + language + "\n" + code.replace(/\n$/, "") + "\n" + fence + "\n\n"
            );
        },
    });
    let markdown_text = turndownService.turndown(paste_html);

    // Checks for escaped ordered list syntax.
    markdown_text = markdown_text.replaceAll(/^(\W* {0,3})(\d+)\\\. /gm, "$1$2. ");

    // Removes newlines before the start of a list and between list elements.
    markdown_text = markdown_text.replaceAll(/\n+([*+-])/g, "\n$1");
    return markdown_text;
}

function can_paste_url_over_range($textarea: JQuery<HTMLTextAreaElement>): boolean {
    const range = $textarea.range();

    if (!range.text) {
        // No range is selected
        return false;
    }

    if (isUrl(range.text.trim())) {
        // Don't engage our URL paste logic over existing URLs
        return false;
    }

    return true;
}

export function cursor_at_markdown_link_marker($textarea: JQuery<HTMLTextAreaElement>): boolean {
    const range = $textarea.range();
    const possible_markdown_link_markers = util
        .the($textarea)
        .value.slice(range.start - 2, range.start);
    return possible_markdown_link_markers === "](";
}

export function maybe_transform_html(html: string, text: string): string {
    if (is_white_space_pre(html)) {
        // Copied content styled with `white-space: pre` is pasted as is
        // but formatted as code. We need this for content copied from
        // VS Code like sources.
        return "<pre><code>" + _.escape(text) + "</code></pre>";
    }
    return html;
}

function add_text_and_select(text: string, $textarea: JQuery<HTMLTextAreaElement>): void {
    const textarea = $textarea.get(0);
    assert(textarea instanceof HTMLTextAreaElement);
    const init_cursor_pos = textarea.selectionStart;
    insertTextIntoField(textarea, text);
    const new_cursor_pos = textarea.selectionStart;
    textarea.setSelectionRange(init_cursor_pos, new_cursor_pos);
}

export function try_stream_topic_syntax_text(text: string): string | null {
    const stream_topic = hash_util.decode_stream_topic_from_url(text);

    if (!stream_topic) {
        return null;
    }

    // Now we're sure that the URL is a valid stream topic URL.
    // But the produced #**stream>topic** syntax could be broken.

    const stream = stream_data.get_sub_by_id(stream_topic.stream_id);
    assert(stream !== undefined);
    const stream_name = stream.name;
    if (topic_link_util.will_produce_broken_stream_topic_link(stream_name)) {
        return topic_link_util.get_fallback_markdown_link(
            stream_name,
            stream_topic.topic_name,
            stream_topic.message_id,
        );
    }

    if (
        stream_topic.topic_name !== undefined &&
        topic_link_util.will_produce_broken_stream_topic_link(stream_topic.topic_name)
    ) {
        return topic_link_util.get_fallback_markdown_link(
            stream_name,
            stream_topic.topic_name,
            stream_topic.message_id,
        );
    }

    let syntax_text = "#**" + stream_name;
    if (stream_topic.topic_name !== undefined) {
        syntax_text += ">" + stream_topic.topic_name;
    }

    if (stream_topic.message_id !== undefined) {
        syntax_text += "@" + stream_topic.message_id;
    }

    syntax_text += "**";
    return syntax_text;
}

export function paste_handler(this: HTMLTextAreaElement, event: JQuery.TriggeredEvent): void {
    assert(event.originalEvent instanceof ClipboardEvent);
    const clipboardData = event.originalEvent.clipboardData;
    if (!clipboardData) {
        // On IE11, ClipboardData isn't defined.  One can instead
        // access it with `window.clipboardData`, but even that
        // doesn't support text/html, so this code path couldn't do
        // anything special anyway.  So we instead just let the
        // default paste handler run on IE11.
        return;
    }

    if (clipboardData.getData) {
        const $textarea = $(this);
        const paste_text = clipboardData.getData("text");
        let paste_html = clipboardData.getData("text/html");
        // Trim the paste_text to accommodate sloppy copying
        const trimmed_paste_text = paste_text.trim();

        // Only intervene to generate formatted links when dealing
        // with a URL and a URL-safe range selection.
        if (isUrl(trimmed_paste_text)) {
            if (cursor_at_markdown_link_marker($textarea)) {
                // When pasting a link after the link marker syntax, we want to
                // avoid inserting markdown syntax text and instead just paste
                // the raw text, possibly replacing any selection. In other words,
                // let the browser handle it.
                return;
            }
            if (can_paste_url_over_range($textarea)) {
                event.preventDefault();
                event.stopPropagation();
                const url = trimmed_paste_text;
                compose_ui.format_text($textarea, "linked", url);
                return;
            }
            if (!compose_ui.cursor_inside_code_block($textarea) && !compose_ui.shift_pressed) {
                // Try to transform the url to #**stream>topic** syntax
                // if it is a valid url.
                const syntax_text = try_stream_topic_syntax_text(trimmed_paste_text);
                if (syntax_text) {
                    event.preventDefault();
                    event.stopPropagation();
                    // To ensure you can get the actual pasted URL back via the browser
                    // undo feature, we first paste the URL in, then select it, and then
                    // replace it with the nicer markdown syntax.
                    add_text_and_select(trimmed_paste_text, $textarea);
                    compose_ui.insert_and_scroll_into_view(syntax_text + " ", $textarea);
                }
                return;
            }
        }
        // We do not paste formatted markdown when inside a code block.
        // Unlike Chrome, Firefox doesn't automatically paste plainly on using Ctrl+Shift+V,
        // hence we need to handle it ourselves, by checking if shift key is pressed, and only
        // if not, we proceed with the default formatted paste.
        if (
            !compose_ui.cursor_inside_code_block($textarea) &&
            paste_html &&
            !compose_ui.shift_pressed
        ) {
            if (is_single_image(paste_html)) {
                // If the copied content is a single image, we let upload.ts handle it.
                return;
            }
            event.preventDefault();
            event.stopPropagation();
            paste_html = maybe_transform_html(paste_html, paste_text);
            const text = paste_handler_converter(paste_html, $textarea);
            if (trimmed_paste_text !== text) {
                // Pasting formatted text is a two-step process: First
                // we paste unformatted text, then overwrite it with
                // formatted text, so that undo restores the
                // pre-formatting syntax.
                add_text_and_select(trimmed_paste_text, $textarea);
            }
            compose_ui.insert_and_scroll_into_view(text, $textarea);
        }
    }
}

export function initialize(): void {
    $<HTMLTextAreaElement>("textarea#compose-textarea").on("paste", paste_handler);
    $("body").on("paste", "textarea.message_edit_content", paste_handler);
}
