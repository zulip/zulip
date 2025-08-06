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
});
