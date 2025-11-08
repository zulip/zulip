import assert from "node:assert";

import {defineRouteMiddleware} from "@astrojs/starlight/route-data";
import type {Paragraph} from "mdast";
import {toString} from "mdast-util-to-string";
import {remark} from "remark";
import remarkMdx from "remark-mdx";
import {visit} from "unist-util-visit";

function extractFirstParagraph(content: string): string | undefined {
    const tree = remark().use(remarkMdx).parse(content);

    let firstParagraph: string | undefined;

    visit(tree, "paragraph", (node: Paragraph) => {
        if (!firstParagraph) {
            // We need to convert the node to string so that links, emphasis, etc.
            // are converted to plain text.
            firstParagraph = toString(node);
            firstParagraph = firstParagraph.replaceAll(/\s+/g, " ").trim();
        }
    });

    return firstParagraph;
}

export const onRequest = defineRouteMiddleware((context) => {
    assert.ok(typeof context.locals.starlightRoute.entry.body === "string");
    context.locals.starlightRoute.head.push({
        tag: "meta",
        attrs: {
            name: "description",
            content: extractFirstParagraph(context.locals.starlightRoute.entry.body),
        },
    });

    const canonicalUrl = `https://zulip.com/help/${context.locals.starlightRoute.id}`;
    const existingCanonicalTag = context.locals.starlightRoute.head.find(
        (item) => item.tag === "link" && item.attrs?.rel === "canonical",
    );

    if (existingCanonicalTag) {
        existingCanonicalTag.attrs!.href = canonicalUrl;
    } else {
        // Starlight already has the canonical tag by default and this might
        // never get executed in practice. But it feels like a nice-to-have
        // if any upstream changes happen in starlight and that behaviour
        // changes.
        context.locals.starlightRoute.head.push({
            tag: "link",
            attrs: {
                rel: "canonical",
                href: canonicalUrl,
            },
        });
    }
});
