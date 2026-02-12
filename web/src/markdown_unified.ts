import {toHtml} from "hast-util-to-html";
import type {Root} from "mdast";
import {fromMarkdown} from "mdast-util-from-markdown";
import {gfmAutolinkLiteralFromMarkdown} from "mdast-util-gfm-autolink-literal";
import {gfmStrikethroughFromMarkdown} from "mdast-util-gfm-strikethrough";
import {gfmTableFromMarkdown} from "mdast-util-gfm-table";
import {newlineToBreak} from "mdast-util-newline-to-break";
import {toHast} from "mdast-util-to-hast";
import {gfmAutolinkLiteral} from "micromark-extension-gfm-autolink-literal";
import {gfmStrikethrough} from "micromark-extension-gfm-strikethrough";
import {gfmTable} from "micromark-extension-gfm-table";

import type {MarkdownHelpers} from "./markdown.ts";
import {translate_emoticons_to_names} from "./markdown.ts";
import {preprocess_fenced_blocks} from "./markdown_fenced_blocks.ts";
import {create_zulip_hast_handlers} from "./markdown_hast_handlers.ts";
import type {MarkdownProcessor} from "./markdown_processor.ts";
import {
    disable_underscore_emphasis,
    extract_flags,
    silence_mentions_in_blockquotes,
    transform_display_math,
    transform_emoji,
    transform_inline_math,
    transform_linkifiers,
    transform_mentions,
    transform_spoilers,
    transform_stream_links,
    transform_timestamps,
} from "./markdown_zulip_transforms.ts";

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
    gfmAutolinkLiteral(),
    // Disable all HTML parsing so user-authored <b>, <script>, etc.
    // become text nodes (auto-escaped by toHtml). Our own generated
    // HTML uses custom mdast node types + hast "raw" nodes instead.
    // Autolinks (<http://...>) use a separate construct, unaffected.
    {disable: {null: ["htmlText", "htmlFlow"]}},
];
const mdast_extensions = [
    gfmAutolinkLiteralFromMarkdown(),
    gfmTableFromMarkdown(),
    gfmStrikethroughFromMarkdown(),
];

/**
 * Parse markdown content into an mdast tree with structural transforms
 * applied. Used both at the top level and recursively for spoiler body
 * content. Each parse level runs its own newlineToBreak and
 * disable_underscore_emphasis since those depend on source positions
 * that are relative to each parse context.
 */
function parse_to_mdast(content: string): Root {
    const preprocessed = preprocess_fenced_blocks(content);
    const source = preprocessed + "\n\n";
    const mdast = fromMarkdown(source, {
        extensions: micromark_extensions,
        mdastExtensions: mdast_extensions,
    });

    // Transform code fences with lang=math/spoiler into custom nodes.
    // These must run before other transforms so the code hast handler
    // doesn't try to syntax-highlight them.
    transform_display_math(mdast);

    // Soft newlines → <br> tags
    newlineToBreak(mdast);

    // Disable _emphasis_ and __strong__ (only * triggers emphasis).
    // Must use the source string from this parse context since it
    // checks character offsets in the source.
    disable_underscore_emphasis(mdast, source);

    // Spoiler bodies are parsed recursively via parse_to_mdast,
    // so each level gets its own newlineToBreak and underscore disable.
    transform_spoilers(mdast, parse_to_mdast);

    return mdast;
}

/**
 * Unified/mdast processor for Zulip markdown.
 *
 * Handles CommonMark + GFM tables/strikethrough, plus all Zulip-specific
 * inline syntax via AST transforms:
 * - User/group mentions (@**name**, @*group*)
 * - Stream/topic links (#**channel**, #**channel>topic**)
 * - Emoji (:name: and unicode)
 * - Inline/display math ($$...$$ and ~~~math)
 * - Timestamps (<time:...>)
 * - Linkifiers (realm-configured regex patterns)
 * - Spoilers (~~~spoiler)
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

            // Parse markdown to mdast (includes fenced block preprocessing,
            // display math, spoiler, newline-to-break, and underscore
            // emphasis transforms — each applied recursively to spoiler bodies)
            const mdast = parse_to_mdast(content);

            // AST transforms for Zulip inline extensions.
            // Order matters: mentions/streams use sibling-pattern detection,
            // so they run first. Timestamps and math run before emoji because
            // the unicode emoji regex matches digits, which would split text
            // nodes and prevent later patterns from matching.
            // These transforms walk the entire tree, including spoiler bodies
            // that were spliced in by transform_spoilers.
            transform_mentions(mdast, helper_config);
            transform_stream_links(mdast, helper_config);
            transform_timestamps(mdast);
            transform_inline_math(mdast);
            transform_linkifiers(mdast, helper_config);
            transform_emoji(mdast, helper_config);
            silence_mentions_in_blockquotes(mdast);

            const mention_flags = extract_flags(mdast, helper_config);

            // Convert mdast to hast with custom handlers for Zulip nodes
            const handlers = create_zulip_hast_handlers(helper_config);
            const hast = toHast(mdast, {handlers, allowDangerousHtml: true});

            // Serialize hast to HTML string
            const html = encode_gt_in_text(
                toHtml(hast, {
                    allowDangerousCharacters: true,
                    allowDangerousHtml: true,
                    characterReferences: {useNamedReferences: true},
                }),
            );

            // Compute flags from mention analysis
            const flags = ["read"];
            if (mention_flags.mentioned || mention_flags.mentioned_group) {
                flags.push("mentioned");
            }
            if (mention_flags.mentioned_stream_wildcard) {
                flags.push("stream_wildcard_mentioned");
            }
            if (mention_flags.mentioned_topic_wildcard) {
                flags.push("topic_wildcard_mentioned");
            }

            return {content: html.trim(), flags};
        },
    };
}
