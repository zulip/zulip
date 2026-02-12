/**
 * mdast AST transforms for Zulip-specific inline syntax.
 *
 * These transforms run between `fromMarkdown` (micromark parse) and `toHast`
 * (HTML AST generation) in the unified processor pipeline. They detect
 * patterns that micromark parsed as standard markdown (e.g., `@` followed
 * by `**bold**` for mentions) and replace them with custom Zulip node types.
 */

import type {Parents, PhrasingContent, Root} from "mdast";
import {findAndReplace} from "mdast-util-find-and-replace";
import type {FindAndReplaceTuple} from "mdast-util-find-and-replace";

import type {MarkdownHelpers} from "./markdown.ts";

// ---- Custom mdast node types ------------------------------------------------
// Node type strings follow mdast convention (camelCase); field names follow
// Zulip convention (snake_case).  These types aren't registered in mdast's
// PhrasingContentMap, so type assertions are needed at the boundaries where
// custom nodes enter the standard mdast tree.

export type ZulipUserMention = {
    type: "zulipUserMention";
    user_id: number;
    display_name: string;
    silent: boolean;
    wildcard?: string;
};

export type ZulipGroupMention = {
    type: "zulipGroupMention";
    group_id: number;
    display_name: string;
    silent: boolean;
};

export type ZulipStreamLink = {
    type: "zulipStreamLink";
    stream_id: number;
    stream_name: string;
    href: string;
};

export type ZulipStreamTopicLink = {
    type: "zulipStreamTopicLink";
    stream_id: number;
    stream_name: string;
    topic: string;
    href: string;
};

export type ZulipStreamTopicMessageLink = {
    type: "zulipStreamTopicMessageLink";
    stream_name: string;
    topic: string;
    href: string;
};

export type ZulipEmoji = {
    type: "zulipEmoji";
    emoji_name: string;
    emoji_url?: string;
    codepoint?: string;
};

export type ZulipUnicodeEmoji = {
    type: "zulipUnicodeEmoji";
    original_text: string;
};

export type ZulipTimestamp = {
    type: "zulipTimestamp";
    time_string: string;
};

export type ZulipInlineMath = {
    type: "zulipInlineMath";
    tex: string;
    full_match: string;
};

export type ZulipDisplayMath = {
    type: "zulipDisplayMath";
    tex: string;
};

export type ZulipSpoilerHeader = {
    type: "zulipSpoilerHeader";
    children: PhrasingContent[];
};

export type ZulipSpoiler = {
    type: "zulipSpoiler";
    // First child is always zulipSpoilerHeader (possibly empty),
    // remaining children are the parsed body content. This structure
    // ensures transforms (findAndReplace, walk_tree) walk into both
    // header and body content.
    children: {type: string}[];
};

// ---- Display math: ~~~math code fences → custom nodes ----------------------
// Micromark parses ~~~math blocks as code fences. This transform replaces
// them with zulipDisplayMath nodes rendered by the hast handler.

export function transform_display_math(tree: Root): void {
    walk_tree(tree, (node, ancestors) => {
        if (node.type !== "code" || !("lang" in node)) {
            return;
        }
        // eslint-disable-next-line @typescript-eslint/consistent-type-assertions
        const code_node = node as {type: string; lang: string | null; value: string};
        if (code_node.lang !== "math") {
            return;
        }
        const parent = ancestors.at(-1);
        if (parent && "children" in parent) {
            // eslint-disable-next-line @typescript-eslint/consistent-type-assertions
            const siblings = (parent as {children: {type: string}[]}).children;
            const idx = siblings.indexOf(node);
            if (idx !== -1) {
                siblings[idx] = as_phrasing({
                    type: "zulipDisplayMath",
                    tex: code_node.value,
                });
            }
        }
    });
}

// ---- Spoilers: ~~~spoiler code fences → custom nodes -----------------------
// Micromark parses ~~~spoiler blocks as code fences with lang="spoiler" and
// meta containing the header text. This transform replaces them with
// zulipSpoiler nodes whose body is recursively parsed as markdown.

export function transform_spoilers(tree: Root, parse_content: (content: string) => Root): void {
    walk_tree(tree, (node, ancestors) => {
        if (node.type !== "code" || !("lang" in node)) {
            return;
        }
        // eslint-disable-next-line @typescript-eslint/consistent-type-assertions
        const code_node = node as {
            type: string;
            lang: string | null;
            meta: string | null;
            value: string;
        };
        if (code_node.lang !== "spoiler") {
            return;
        }
        const parent = ancestors.at(-1);
        if (!parent || !("children" in parent)) {
            return;
        }
        // eslint-disable-next-line @typescript-eslint/consistent-type-assertions
        const siblings = (parent as {children: {type: string}[]}).children;
        const idx = siblings.indexOf(node);
        if (idx === -1) {
            return;
        }

        // Parse header as inline content
        const header_text = code_node.meta ?? "";
        let header_children: PhrasingContent[] = [];
        if (header_text) {
            const header_tree = parse_content(header_text);
            const first = header_tree.children[0];
            if (first && "children" in first) {
                // eslint-disable-next-line @typescript-eslint/consistent-type-assertions
                header_children = (first as {children: PhrasingContent[]}).children;
            }
        }

        // Parse body as block content (recursive — handles nested math/spoilers)
        const body_tree = parse_content(code_node.value);

        const spoiler_header: ZulipSpoilerHeader = {
            type: "zulipSpoilerHeader",
            children: header_children,
        };
        const spoiler: ZulipSpoiler = {
            type: "zulipSpoiler",
            children: [spoiler_header, ...body_tree.children],
        };
        siblings[idx] = spoiler;
    });
}

// ---- Disable underscore emphasis -------------------------------------------
// Zulip only allows * for emphasis/strong, not _. This transform checks the
// source character at the node's start offset and unwraps nodes triggered by _.

export function disable_underscore_emphasis(tree: Root, source: string): void {
    walk_tree(tree, (node, ancestors) => {
        if (node.type !== "emphasis" && node.type !== "strong") {
            return;
        }
        // eslint-disable-next-line @typescript-eslint/consistent-type-assertions
        const em_node = node as {
            type: string;
            position?: {start: {offset?: number}};
            children: PhrasingContent[];
        };
        const offset = em_node.position?.start.offset;
        if (offset === undefined || source.charAt(offset) !== "_") {
            return;
        }
        const marker = node.type === "strong" ? "__" : "_";
        const replacement: PhrasingContent[] = [
            {type: "text", value: marker},
            ...em_node.children,
            {type: "text", value: marker},
        ];
        const parent = ancestors.at(-1);
        if (parent && "children" in parent) {
            // eslint-disable-next-line @typescript-eslint/consistent-type-assertions
            const siblings = (parent as {children: PhrasingContent[]}).children;
            // eslint-disable-next-line @typescript-eslint/consistent-type-assertions
            const idx = siblings.indexOf(node as PhrasingContent);
            if (idx !== -1) {
                siblings.splice(idx, 1, ...replacement);
            }
        }
    });
}

// ---- Shared sibling-pattern detection ---------------------------------------
// Mentions (@**name**, @*group*) and stream links (#**channel**) are all
// parsed by micromark as a prefix character in a text node followed by a
// strong or emphasis sibling.  This helper extracts the shared iteration
// logic so each transform only needs to supply a list of matchers.

type SiblingMatcher = {
    sibling_type: "strong" | "emphasis";
    prefix_regex: RegExp;
    resolve: (content: string, prefix_match: RegExpExecArray) => PhrasingContent | undefined;
};

function transform_sibling_patterns(tree: Root, matchers: SiblingMatcher[]): void {
    function walk(node: Parents): void {
        const children: PhrasingContent[] = [];
        let i = 0;

        while (i < node.children.length) {
            const child = node.children[i]!;
            const next = node.children[i + 1];
            let matched = false;

            if (child.type === "text" && next) {
                for (const matcher of matchers) {
                    if (next.type !== matcher.sibling_type) {
                        continue;
                    }
                    const prefix_match = matcher.prefix_regex.exec(child.value);
                    if (
                        prefix_match &&
                        next.children.length === 1 &&
                        next.children[0]!.type === "text"
                    ) {
                        const content = next.children[0].value;
                        const result = matcher.resolve(content, prefix_match);
                        if (result) {
                            const prefix = prefix_match[1]!;
                            if (prefix) {
                                children.push({type: "text", value: prefix});
                            }
                            children.push(result);
                            i += 2;
                            matched = true;
                            break;
                        }
                    }
                }
            }

            if (!matched) {
                // eslint-disable-next-line @typescript-eslint/consistent-type-assertions
                children.push(child as PhrasingContent);
                i += 1;
            }
        }

        // eslint-disable-next-line @typescript-eslint/consistent-type-assertions
        (node as {children: PhrasingContent[]}).children = children;

        for (const child of node.children) {
            if ("children" in child) {
                // eslint-disable-next-line @typescript-eslint/consistent-type-assertions
                walk(child as Parents);
            }
        }
    }

    walk(tree);
}

// ---- User & wildcard mentions: @**name**, @_**name** -----------------------

const WILDCARD_MENTIONS = new Set(["all", "everyone", "stream", "channel", "topic"]);

const STREAM_WILDCARD_MENTIONS = new Set(["all", "everyone", "stream", "channel"]);

function resolve_user_mention(
    mention_text: string,
    silent: boolean,
    helpers: MarkdownHelpers,
): ZulipUserMention | undefined {
    if (WILDCARD_MENTIONS.has(mention_text)) {
        return {
            type: "zulipUserMention",
            user_id: 0,
            display_name: mention_text,
            silent,
            wildcard: mention_text,
        };
    }

    let full_name: string | undefined;
    let user_id: number | undefined;

    // Check for @**name|id** or @**|id** syntax
    const id_regex = /^(.+)?\|(\d+)$/;
    const match = id_regex.exec(mention_text);

    if (match) {
        full_name = match[1];
        user_id = Number.parseInt(match[2]!, 10);

        if (full_name === undefined) {
            // @**|id** syntax
            if (!helpers.is_valid_user_id(user_id)) {
                user_id = undefined;
            } else {
                full_name = helpers.get_actual_name_from_user_id(user_id);
            }
        } else {
            // @**name|id** syntax
            if (!helpers.is_valid_full_name_and_user_id(full_name, user_id)) {
                user_id = undefined;
                full_name = undefined;
            }
        }
    }

    if (user_id === undefined) {
        full_name = mention_text;
        user_id = helpers.get_user_id_from_name(full_name);
    }

    if (user_id === undefined) {
        return undefined;
    }

    const display_name = helpers.get_actual_name_from_user_id(user_id) ?? full_name!;
    return {
        type: "zulipUserMention",
        user_id,
        display_name,
        silent,
    };
}

// Zulip custom AST nodes are structurally valid as PhrasingContent (leaf
// nodes with a `type` discriminant) but aren't in mdast's type registry.
// This helper bridges the type gap at the boundary.
// eslint-disable-next-line @typescript-eslint/consistent-type-assertions
const as_phrasing = (node: unknown): PhrasingContent => node as PhrasingContent;

// Walk all descendant nodes, including custom Zulip node types that aren't
// in mdast's type registry.  Unlike unist-util-visit-parents, this avoids
// InclusiveDescendant type inference that produces `never` for unregistered
// node types.
function walk_tree(
    tree: Root,
    visitor: (node: {type: string}, ancestors: {type: string}[]) => void,
): void {
    function recurse(node: {type: string}, ancestors: {type: string}[]): void {
        visitor(node, ancestors);
        if ("children" in node) {
            // eslint-disable-next-line @typescript-eslint/consistent-type-assertions
            const children = (node as {children: {type: string}[]}).children;
            const next_ancestors = [...ancestors, node];
            for (const child of children) {
                recurse(child, next_ancestors);
            }
        }
    }
    recurse(tree, []);
}

export function transform_mentions(tree: Root, helpers: MarkdownHelpers): void {
    transform_sibling_patterns(tree, [
        {
            sibling_type: "strong",
            prefix_regex: /^([\s\S]*?)(@_?)$/,
            resolve(content, prefix_match) {
                const silent = prefix_match[2] === "@_";
                return as_phrasing(resolve_user_mention(content, silent, helpers));
            },
        },
        {
            sibling_type: "emphasis",
            prefix_regex: /^([\s\S]*?)(@_?)$/,
            resolve(content, prefix_match) {
                const silent = prefix_match[2] === "@_";
                const group = helpers.get_user_group_from_name(content);
                if (group === undefined) {
                    return undefined;
                }
                const node: ZulipGroupMention = {
                    type: "zulipGroupMention",
                    group_id: group.id,
                    display_name: group.name,
                    silent,
                };
                return as_phrasing(node);
            },
        },
    ]);
}

// ---- Stream/topic links: #**channel**, #**channel>topic** ------------------

export function transform_stream_links(tree: Root, helpers: MarkdownHelpers): void {
    transform_sibling_patterns(tree, [
        {
            sibling_type: "strong",
            prefix_regex: /^([\s\S]*?)#$/,
            resolve(content) {
                return as_phrasing(resolve_stream_link(content, helpers));
            },
        },
    ]);
}

function resolve_stream_link(
    link_text: string,
    helpers: MarkdownHelpers,
): ZulipStreamLink | ZulipStreamTopicLink | ZulipStreamTopicMessageLink | undefined {
    const topic_sep_index = link_text.indexOf(">");

    if (topic_sep_index === -1) {
        // Simple stream link: #**channel**
        const stream = helpers.get_stream_by_name(link_text);
        if (stream === undefined) {
            return undefined;
        }
        const href = "/" + helpers.stream_hash(stream.stream_id);
        return {
            type: "zulipStreamLink",
            stream_id: stream.stream_id,
            stream_name: stream.name,
            href,
        };
    }

    const stream_name = link_text.slice(0, topic_sep_index);
    const topic_part = link_text.slice(topic_sep_index + 1);

    const stream = helpers.get_stream_by_name(stream_name);
    if (stream === undefined) {
        return undefined;
    }

    // Check for message link: topic@messageId
    const message_match = /^(.*)@(\d+)$/.exec(topic_part);
    if (message_match) {
        const topic = message_match[1]!;
        const message_id = Number.parseInt(message_match[2]!, 10);
        const href =
            helpers.stream_topic_hash(stream.stream_id, topic) + "/near/" + String(message_id);
        return {
            type: "zulipStreamTopicMessageLink",
            stream_name: stream.name,
            topic,
            href,
        };
    }

    // Regular topic link: #**channel>topic**
    const topic = topic_part;
    const href = helpers.stream_topic_hash(stream.stream_id, topic);
    return {
        type: "zulipStreamTopicLink",
        stream_id: stream.stream_id,
        stream_name: stream.name,
        topic,
        href,
    };
}

// ---- Link transforms: fragment rewriting and empty text fallback -----------
// Mirrors backend logic from rewrite_local_links_to_relative() and
// zulip_specific_link_changes() in zerver/lib/markdown/__init__.py.

export function transform_links(tree: Root, helpers: MarkdownHelpers): void {
    const realm_url = helpers.realm_url;
    if (!realm_url) {
        return;
    }
    const realm_url_prefix = realm_url + "/";

    walk_tree(tree, (node, ancestors) => {
        if (node.type !== "link" || !("url" in node)) {
            return;
        }
        // eslint-disable-next-line @typescript-eslint/consistent-type-assertions
        const link = node as {type: string; url: string; children: PhrasingContent[]};

        // Rewrite local links to be relative (strip realm_url prefix)
        if (
            link.url.startsWith(realm_url_prefix + "#") ||
            link.url.startsWith(realm_url_prefix + "user_uploads/")
        ) {
            link.url = link.url.slice(realm_url_prefix.length);
        }

        // Empty link text fallback: [](url) → display the URL as text
        const has_text = link.children.some(
            (child) => child.type !== "text" || child.value.trim() !== "",
        );
        if (!has_text) {
            link.children = [{type: "text", value: link.url}];
        }

        // Prevent further transforms from splitting the link text
        // (not strictly needed here, but matches backend behavior)
        void ancestors;
    });
}

// ---- Inline math: $$...$$ --------------------------------------------------

export function transform_inline_math(tree: Root): void {
    // We use findAndReplace rather than micromark-extension-math because
    // Zulip uses $$...$$ for inline math, while that extension uses $...$
    // for inline and $$...$$ for display math.
    //
    // - First char: not newline, underscore, or dollar (prevents $$_$$ matching)
    // - Rest: either escaped dollar (\$) or any non-newline, non-dollar char
    // - Negative lookahead prevents matching $$$
    // eslint-disable-next-line @typescript-eslint/consistent-type-assertions
    const pattern = [
        /\$\$([^\n_$](\\\$|[^\n$])*)\$\$(?!\$)/g,
        (match: string, tex: string) =>
            as_phrasing({type: "zulipInlineMath", tex, full_match: match}),
    ] as FindAndReplaceTuple;
    findAndReplace(tree, [pattern]);
}

// ---- Emoji: :name: and unicode emoji ----------------------------------------

// Unicode emoji regex - matches emoji sequences.
// Adapted from the regex in the legacy processor.
const UNICODE_EMOJI_REGEX =
    /(\p{RI}\p{RI}|\p{Emoji}(?:\p{Emoji_Modifier}|\u{FE0F}\u{20E3}?|[\u{E0020}-\u{E007E}]+\u{E007F})?(?:\u{200D}(?:\p{RI}\p{RI}|\p{Emoji}(?:\p{Emoji_Modifier}|\u{FE0F}\u{20E3}?|[\u{E0020}-\u{E007E}]+\u{E007F})?))*)/gu;

// Named emoji pattern: :emoji_name:
const NAMED_EMOJI_REGEX = /:([A-Za-z0-9_+-]+?):/g;

// Non-presentation emoji (digits, arrows, keycaps) should not be converted
// to emoji spans. This matches the check in handleUnicodeEmoji().
const NON_PRESENTATION_EMOJI_REGEX = /^\P{Emoji_Presentation}\u20E3?$/u;

export function transform_emoji(tree: Root, helpers: MarkdownHelpers): void {
    // eslint-disable-next-line @typescript-eslint/consistent-type-assertions
    const patterns = [
        [
            NAMED_EMOJI_REGEX,
            (_match: string, emoji_name: string): PhrasingContent | false => {
                const emoji_url = helpers.get_realm_emoji_url(emoji_name);
                if (emoji_url) {
                    return as_phrasing({type: "zulipEmoji", emoji_name, emoji_url});
                }
                const codepoint = helpers.get_emoji_codepoint(emoji_name);
                if (codepoint) {
                    return as_phrasing({type: "zulipEmoji", emoji_name, codepoint});
                }
                return false;
            },
        ],
        [
            UNICODE_EMOJI_REGEX,
            (match: string): PhrasingContent | false => {
                // Skip non-presentation emoji (digits, arrows, keycaps)
                // to avoid splitting text nodes and to match legacy behavior.
                if (NON_PRESENTATION_EMOJI_REGEX.test(match)) {
                    return false;
                }
                return as_phrasing({type: "zulipUnicodeEmoji", original_text: match});
            },
        ],
    ] as FindAndReplaceTuple[];
    findAndReplace(tree, patterns);
}

// ---- Timestamps: <time:...> ------------------------------------------------

export function transform_timestamps(tree: Root): void {
    // Most <time:...> inputs contain spaces, so micromark treats them as
    // literal text (not autolinks). Use findAndReplace on text nodes.
    // eslint-disable-next-line @typescript-eslint/consistent-type-assertions
    const pattern = [
        /<time:([^<>]+)>/g,
        (_match: string, time_string: string) => as_phrasing({type: "zulipTimestamp", time_string}),
    ] as FindAndReplaceTuple;
    findAndReplace(tree, [pattern]);

    // Also handle autolink timestamps (e.g., <time:2024-01-01> without spaces,
    // which micromark parses as link nodes with url starting with "time:").
    walk_tree(tree, (node, ancestors) => {
        if (node.type !== "link" || !("url" in node) || typeof node.url !== "string") {
            return;
        }
        if (!node.url.startsWith("time:")) {
            return;
        }

        const parent = ancestors.at(-1);
        if (parent && "children" in parent) {
            // eslint-disable-next-line @typescript-eslint/consistent-type-assertions
            const siblings = (parent as {children: {type: string}[]}).children;
            const idx = siblings.indexOf(node);
            if (idx !== -1) {
                siblings[idx] = as_phrasing({
                    type: "zulipTimestamp",
                    time_string: node.url.slice(5),
                });
            }
        }
    });
}

// ---- Linkifiers: realm-configured regex patterns ----------------------------

export function transform_linkifiers(tree: Root, helpers: MarkdownHelpers): void {
    const linkifier_map = helpers.get_linkifier_map();
    const replacements: FindAndReplaceTuple[] = [];

    for (const [pattern, {url_template, group_number_to_name}] of linkifier_map.entries()) {
        // Use a global version of the original pattern for findAndReplace.
        // The legacy processor wraps patterns with /(?<=^|\s)PATTERN(?!\w)/
        // for word-boundary matching; we'll address that in a follow-up.
        const global_pattern = new RegExp(pattern.source, "g");

        // eslint-disable-next-line @typescript-eslint/consistent-type-assertions
        const tuple = [
            global_pattern,
            (match: string, ...groups: string[]): PhrasingContent => {
                const template_context = Object.fromEntries(
                    groups
                        .slice(0, Object.keys(group_number_to_name).length)
                        .map((matched_group, i) => [group_number_to_name[i + 1]!, matched_group]),
                );
                const link_url = url_template.expand(template_context);

                return {
                    type: "link",
                    url: link_url,
                    title: link_url,
                    children: [{type: "text", value: match}],
                };
            },
        ] as FindAndReplaceTuple;
        replacements.push(tuple);
    }

    if (replacements.length > 0) {
        findAndReplace(tree, replacements);
    }
}

// ---- Silence mentions in blockquotes ----------------------------------------

function is_zulip_user_mention(node: {type: string}): node is ZulipUserMention {
    return node.type === "zulipUserMention";
}

function is_zulip_group_mention(node: {type: string}): node is ZulipGroupMention {
    return node.type === "zulipGroupMention";
}

export function silence_mentions_in_blockquotes(tree: Root): void {
    walk_tree(tree, (node, ancestors) => {
        if (is_zulip_user_mention(node) || is_zulip_group_mention(node)) {
            const in_blockquote = ancestors.some((ancestor) => ancestor.type === "blockquote");
            if (in_blockquote) {
                node.silent = true;
            }
        }
    });
}

// ---- Extract mention flags --------------------------------------------------

export type MentionFlags = {
    mentioned: boolean;
    mentioned_group: boolean;
    mentioned_stream_wildcard: boolean;
    mentioned_topic_wildcard: boolean;
};

export function extract_flags(tree: Root, helpers: MarkdownHelpers): MentionFlags {
    const flags: MentionFlags = {
        mentioned: false,
        mentioned_group: false,
        mentioned_stream_wildcard: false,
        mentioned_topic_wildcard: false,
    };

    walk_tree(tree, (node) => {
        if (is_zulip_user_mention(node)) {
            if (node.silent) {
                return;
            }
            if (node.wildcard) {
                if (STREAM_WILDCARD_MENTIONS.has(node.wildcard)) {
                    flags.mentioned_stream_wildcard = true;
                } else if (node.wildcard === "topic") {
                    flags.mentioned_topic_wildcard = true;
                }
            } else if (node.user_id === helpers.my_user_id()) {
                flags.mentioned = true;
            }
        } else if (is_zulip_group_mention(node)) {
            if (node.silent) {
                return;
            }
            if (helpers.is_member_of_user_group(node.group_id, helpers.my_user_id())) {
                flags.mentioned_group = true;
            }
        }
    });

    return flags;
}
