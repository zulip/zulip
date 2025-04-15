import {defineMiddleware} from "astro:middleware";
import type {Element, Root, RootContent} from "hast";
import {fromHtml} from "hast-util-from-html";
import {toHtml} from "hast-util-to-html";

function isList(node: Element): boolean {
    return node.tagName === "ol" || node.tagName === "ul";
}

// This function traverses the HTML tree and merges lists of the same
// type if they are adjacent to each other. This is kinda a hack to
// make file imports work within lists. One of our major use cases
// for file imports is to have bullet points as partials to import at
// different places in the project. But when importing the file with
// Astro, it creates its own lists. So we merge lists together if they
// have nothing but whitespace between them.
function mergeAdjacentListsOfSameType(tree: Root): Root {
    function recursiveMergeAdjacentLists(node: Element | Root): void {
        if (!node.children) {
            return;
        }

        const modifiedChildren: RootContent[] = [];
        let currentIndex = 0;

        while (currentIndex < node.children.length) {
            const currentChild = node.children[currentIndex]!;

            if (currentChild.type === "element" && isList(currentChild)) {
                const mergedList = structuredClone(currentChild);
                let lookaheadIndex = currentIndex + 1;

                while (lookaheadIndex < node.children.length) {
                    const lookaheadChild = node.children[lookaheadIndex]!;

                    if (lookaheadChild.type === "element" && isList(lookaheadChild)) {
                        if (lookaheadChild.tagName === currentChild.tagName) {
                            mergedList.children.push(...lookaheadChild.children);
                        }
                        lookaheadIndex += 1;
                    } else if (
                        lookaheadChild.type === "text" &&
                        /^\s*$/.test(lookaheadChild.value)
                    ) {
                        // Whitespace should be allowed in between lists.
                        lookaheadIndex += 1;
                    } else {
                        break;
                    }
                }

                modifiedChildren.push(mergedList);
                currentIndex = lookaheadIndex;
            } else {
                modifiedChildren.push(currentChild);
                currentIndex += 1;
            }
        }

        node.children = modifiedChildren;
        for (const child of node.children) {
            if (child.type === "element") {
                recursiveMergeAdjacentLists(child);
            }
        }
    }

    recursiveMergeAdjacentLists(tree);
    return tree;
}

export const onRequest = defineMiddleware(async (_context, next) => {
    const response = await next();
    const html = await response.text();
    const tree = fromHtml(html);
    const result = toHtml(mergeAdjacentListsOfSameType(tree));

    return new Response(result, {
        status: 200,
        headers: response.headers,
    });
});
