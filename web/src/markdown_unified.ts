import {toHtml} from "hast-util-to-html";
import {fromMarkdown} from "mdast-util-from-markdown";
import {gfmStrikethroughFromMarkdown} from "mdast-util-gfm-strikethrough";
import {gfmTableFromMarkdown} from "mdast-util-gfm-table";
import {newlineToBreak} from "mdast-util-newline-to-break";
import {toHast} from "mdast-util-to-hast";
import {gfmStrikethrough} from "micromark-extension-gfm-strikethrough";
import {gfmTable} from "micromark-extension-gfm-table";

import type {MarkdownHelpers} from "./markdown.ts";
import {translate_emoticons_to_names} from "./markdown.ts";
import type {MarkdownProcessor} from "./markdown_processor.ts";

/**
 * Encode `>` as `&gt;` in text content. hast-util-to-html only encodes
 * `<` and `&` in text nodes (per HTML spec, `>` is valid in text). But
 * the Zulip backend encodes `>` for safety. This post-processes the
 * serialized HTML: `>` inside HTML tags stays as-is, `>` in text
 * becomes `&gt;`.
 */
function encode_gt_in_text(html: string): string {
    let result = "";
    let in_tag = false;
    for (const char of html) {
        if (char === "<") {
            in_tag = true;
            result += char;
        } else if (char === ">" && in_tag) {
            in_tag = false;
            result += char;
        } else if (char === ">") {
            result += "&gt;";
        } else {
            result += char;
        }
    }
    return result;
}

// Micromark extensions shared between top-level and recursive parsing.
const micromark_extensions = [
    gfmTable(),
    gfmStrikethrough(),
    // Disable all HTML parsing so user-authored <b>, <script>, etc.
    // become text nodes (auto-escaped by toHtml). Our own generated
    // HTML uses custom mdast node types + hast "raw" nodes instead.
    // Autolinks (<http://...>) use a separate construct, unaffected.
    {disable: {null: ["htmlText", "htmlFlow"]}},
];
const mdast_extensions = [gfmTableFromMarkdown(), gfmStrikethroughFromMarkdown()];

/**
 * Skeleton unified/mdast processor for Zulip markdown.
 *
 * This is the initial scaffolding for the migration from marked.js to
 * the unified/mdast ecosystem. It currently handles standard CommonMark
 * + GFM tables/strikethrough. Zulip-specific extensions (mentions,
 * emoji, stream links, etc.) will be added in subsequent commits.
 */
export function create_unified_processor(): MarkdownProcessor {
    return {
        process(raw_content: string, helper_config: MarkdownHelpers) {
            let content = raw_content;

            // Emoticon translation (same as legacy path)
            if (helper_config.should_translate_emoticons()) {
                content = translate_emoticons_to_names({
                    src: content,
                    get_emoticon_translations: helper_config.get_emoticon_translations,
                });
            }

            // Our Python-Markdown processor appends two \n\n to input
            content = content + "\n\n";

            // Parse markdown to mdast
            const mdast = fromMarkdown(content, {
                extensions: micromark_extensions,
                mdastExtensions: mdast_extensions,
            });

            // Soft newlines → <br> tags
            newlineToBreak(mdast);

            // Convert mdast to hast (HTML AST)
            const hast = toHast(mdast);

            // Serialize hast to HTML string
            const html = encode_gt_in_text(
                toHtml(hast, {
                    allowDangerousCharacters: true,
                    allowDangerousHtml: true,
                    characterReferences: {useNamedReferences: true},
                }),
            );

            // Flags are not yet computed by this processor
            const flags = ["read"];

            return {content: html.trim(), flags};
        },
    };
}
