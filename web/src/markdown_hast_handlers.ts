/**
 * Custom hast handlers for Zulip mdast node types.
 *
 * Each handler converts a custom Zulip mdast node into a hast "raw" node
 * containing HTML that exactly matches the output of the legacy processor.
 * This reuses the existing HTML-generating functions from markdown.ts to
 * ensure parity.
 */

import katex from "katex";
import _ from "lodash";
import type {Parents} from "mdast";
import type {Handler, Handlers, State} from "mdast-util-to-hast";

import {
    handleStream,
    handleStreamTopic,
    handleStreamTopicMessage,
    handleTex,
    handleTimestamp,
    handleUnicodeEmoji,
    make_emoji_span,
} from "./markdown.ts";
import type {MarkdownHelpers} from "./markdown.ts";
import type {
    ZulipDisplayMath,
    ZulipEmoji,
    ZulipGroupMention,
    ZulipInlineMath,
    ZulipSpoiler,
    ZulipStreamLink,
    ZulipStreamTopicLink,
    ZulipStreamTopicMessageLink,
    ZulipTimestamp,
    ZulipUnicodeEmoji,
    ZulipUserMention,
} from "./markdown_zulip_transforms.ts";

type RawHastNode = {type: "raw"; value: string};

function raw(html: string): RawHastNode {
    return {type: "raw", value: html};
}

function mention_display_text(name: string, silent: boolean): string {
    return silent ? name : "@" + name;
}

export function create_zulip_hast_handlers(helpers: MarkdownHelpers): Handlers {
    const handlers: Record<string, Handler> = {
        zulipUserMention(
            _state: State,
            node: ZulipUserMention,
            _parent: Parents | undefined,
        ): RawHastNode {
            if (node.wildcard) {
                if (node.wildcard === "topic") {
                    const classes = node.silent ? "topic-mention silent" : "topic-mention";
                    return raw(
                        `<span class="${classes}">${_.escape(mention_display_text(node.display_name, node.silent))}</span>`,
                    );
                }
                // Stream wildcard mention (all, everyone, stream, channel)
                const classes = node.silent
                    ? "user-mention channel-wildcard-mention silent"
                    : "user-mention channel-wildcard-mention";
                return raw(
                    `<span class="${classes}" data-user-id="*">${_.escape(mention_display_text(node.display_name, node.silent))}</span>`,
                );
            }

            // Regular user mention
            const classes = node.silent ? "user-mention silent" : "user-mention";
            return raw(
                `<span class="${classes}" data-user-id="${_.escape(String(node.user_id))}">${_.escape(mention_display_text(node.display_name, node.silent))}</span>`,
            );
        },

        zulipGroupMention(
            _state: State,
            node: ZulipGroupMention,
            _parent: Parents | undefined,
        ): RawHastNode {
            const classes = node.silent ? "user-group-mention silent" : "user-group-mention";
            return raw(
                `<span class="${classes}" data-user-group-id="${_.escape(String(node.group_id))}">${_.escape(mention_display_text(node.display_name, node.silent))}</span>`,
            );
        },

        // Stream/topic/message link handlers delegate to the legacy
        // handleStream/handleStreamTopic/handleStreamTopicMessage functions
        // via adapter callbacks that feed pre-resolved data back through
        // their expected interfaces.

        zulipStreamLink(
            _state: State,
            node: ZulipStreamLink,
            _parent: Parents | undefined,
        ): RawHastNode {
            const html = handleStream({
                stream_name: node.stream_name,
                get_stream_by_name: () => ({stream_id: node.stream_id, name: node.stream_name}),
                stream_hash: () => node.href.slice(1), // Remove leading /
            });
            return raw(html!);
        },

        zulipStreamTopicLink(
            _state: State,
            node: ZulipStreamTopicLink,
            _parent: Parents | undefined,
        ): RawHastNode {
            const html = handleStreamTopic({
                stream_name: node.stream_name,
                topic: node.topic,
                get_stream_by_name: () => ({stream_id: node.stream_id, name: node.stream_name}),
                stream_topic_hash: () => node.href,
            });
            return raw(html!);
        },

        zulipStreamTopicMessageLink(
            _state: State,
            node: ZulipStreamTopicMessageLink,
            _parent: Parents | undefined,
        ): RawHastNode {
            const near_idx = node.href.lastIndexOf("/near/");
            const base_href = node.href.slice(0, near_idx);
            const message_id = Number.parseInt(node.href.slice(near_idx + 6), 10);

            const html = handleStreamTopicMessage({
                stream_name: node.stream_name,
                topic: node.topic,
                message_id,
                get_stream_by_name: () => ({stream_id: 0, name: node.stream_name}),
                stream_topic_hash: () => base_href,
            });
            return raw(html!);
        },

        zulipEmoji(_state: State, node: ZulipEmoji, _parent: Parents | undefined): RawHastNode {
            const alt_text = ":" + node.emoji_name + ":";
            const title = node.emoji_name.replaceAll("_", " ");
            if (node.emoji_url) {
                return raw(
                    `<img alt="${_.escape(alt_text)}" class="emoji" src="${_.escape(node.emoji_url)}" title="${_.escape(title)}">`,
                );
            }
            if (node.codepoint) {
                return raw(make_emoji_span(node.codepoint, title, alt_text));
            }
            return raw(_.escape(alt_text));
        },

        zulipUnicodeEmoji(
            _state: State,
            node: ZulipUnicodeEmoji,
            _parent: Parents | undefined,
        ): RawHastNode {
            return raw(handleUnicodeEmoji(node.original_text, helpers.get_emoji_name));
        },

        zulipTimestamp(
            _state: State,
            node: ZulipTimestamp,
            _parent: Parents | undefined,
        ): RawHastNode {
            return raw(handleTimestamp(node.time_string));
        },

        zulipInlineMath(
            _state: State,
            node: ZulipInlineMath,
            _parent: Parents | undefined,
        ): RawHastNode {
            return raw(handleTex(node.tex, node.full_match));
        },

        zulipDisplayMath(
            _state: State,
            node: ZulipDisplayMath,
            _parent: Parents | undefined,
        ): RawHastNode {
            try {
                return raw("<p>" + katex.renderToString(node.tex, {displayMode: true}) + "</p>");
            } catch {
                return raw('<p><span class="tex-error">' + _.escape(node.tex) + "</span></p>");
            }
        },

        zulipSpoiler(state: State, node: ZulipSpoiler, _parent: Parents | undefined) {
            // First child is zulipSpoilerHeader, rest is body content
            const header_node = node.children[0];
            const body_nodes = node.children.slice(1);

            // Convert header to hast (wrap phrasing content in a <p>)
            const header_children: ReturnType<typeof state.all> = [];
            // eslint-disable-next-line @typescript-eslint/consistent-type-assertions
            const header_phrasing = (header_node as {children?: unknown[]})?.children ?? [];
            if (header_phrasing.length > 0) {
                // eslint-disable-next-line @typescript-eslint/consistent-type-assertions
                const header_parent = {
                    type: "paragraph",
                    children: header_phrasing,
                } as Parents;
                const header_p = state.one(header_parent, undefined);
                if (header_p) {
                    if (Array.isArray(header_p)) {
                        header_children.push(...header_p);
                    } else {
                        header_children.push(header_p);
                    }
                }
            }

            // Convert body block content to hast
            // eslint-disable-next-line @typescript-eslint/consistent-type-assertions
            const body_parent = {type: "root", children: body_nodes} as Parents;
            const body_children = state.all(body_parent);

            return {
                type: "element" as const,
                tagName: "div",
                properties: {className: ["spoiler-block"]},
                children: [
                    {
                        type: "element" as const,
                        tagName: "div",
                        properties: {className: ["spoiler-header"]},
                        children: [
                            ...(header_children.length > 0
                                ? [
                                      {type: "text" as const, value: "\n"},
                                      ...header_children,
                                      {type: "text" as const, value: "\n"},
                                  ]
                                : [{type: "text" as const, value: "\n"}]),
                        ],
                    },
                    {
                        type: "element" as const,
                        tagName: "div",
                        properties: {className: ["spoiler-content"], ariaHidden: "true"},
                        children: [
                            {type: "text" as const, value: "\n"},
                            ...body_children,
                            {type: "text" as const, value: "\n"},
                        ],
                    },
                ],
            };
        },
    };

    // eslint-disable-next-line @typescript-eslint/consistent-type-assertions
    return handlers as unknown as Handlers;
}
