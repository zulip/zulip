// @ts-check

// We are using remarkLintRulesLintRecommended and
// remarkPresentLintMarkdownStyleGuide as our starting set of rules.
// None of the rules were giving an error on the starting set, but some
// rules were giving lots of warnings on the generated mdx. They are
// set to false in this file, we can add them back later as and when
// required.

/**
 * @import {Root} from "mdast"
 * @import {Preset, Processor} from "unified"
 */

import {toMarkdown} from "mdast-util-to-markdown";
import remarkFrontmatter from "remark-frontmatter";
import remarkGfm from "remark-gfm";
import remarkLintFencedCodeFlag from "remark-lint-fenced-code-flag";
import remarkLintFileExtension from "remark-lint-file-extension";
import remarkLintFinalDefinition from "remark-lint-final-definition";
import remarkLintHeadingIncrement from "remark-lint-heading-increment";
import remarkLintListItemSpacing from "remark-lint-list-item-spacing";
import remarkLintMaximumHeadingLength from "remark-lint-maximum-heading-length";
import remarkLintMaximumLineLength from "remark-lint-maximum-line-length";
import remarkLintNoDuplicateHeadings from "remark-lint-no-duplicate-headings";
import remarkLintNoFileNameIrregularCharacters from "remark-lint-no-file-name-irregular-characters";
import remarkLintNoFileNameMixedCase from "remark-lint-no-file-name-mixed-case";
import remarkLintNoUnusedDefinitions from "remark-lint-no-unused-definitions";
import remarkLintUnorderedListMarkerStyle from "remark-lint-unordered-list-marker-style";
import remarkMdx from "remark-mdx";
import remarkPresetLintMarkdownStyleGuide from "remark-preset-lint-markdown-style-guide";
import remarkPresetLintRecommended from "remark-preset-lint-recommended";
import remarkStringify from "remark-stringify";
import {lintRule} from "unified-lint-rule";

const stringifyOptions = {
    // Number all list items as 1, for compatibility with
    // remark-lint-ordered-list-marker-value.
    incrementListMarker: false,
};

/**
 * Make sure the linter fails if files need to be reformatted.  (The other rules
 * catch some but not all formatting issues, so this is needed to be sure we
 * don't silently ignore changes that would be made with --fix.)
 *
 * @this {Processor}
 * @param {...unknown} args
 */
function remarkLintNeedsReformatting(...args) {
    const settings = this.data("settings");
    if (
        settings === undefined ||
        !("checkReformatting" in settings) ||
        !settings.checkReformatting
    ) {
        return undefined;
    }
    return lintRule(
        "needs-reformatting",
        /** @param {Root} tree */
        (tree, file) => {
            const formatted = toMarkdown(tree, {
                ...settings,
                ...stringifyOptions,
                extensions: this.data("toMarkdownExtensions") || [],
            });
            if (formatted !== file.value) {
                file.message("Would be reformatted");
            }
        },
    )(...args);
}

/** @type {Preset} */
const remarkLintRules = {
    plugins: [
        remarkPresetLintMarkdownStyleGuide,
        remarkPresetLintRecommended,
        [remarkLintFinalDefinition, false],
        [remarkLintListItemSpacing, false],
        [remarkLintFileExtension, ["mdx"]],
        [remarkLintNoUnusedDefinitions, false],
        [remarkLintMaximumLineLength, false],
        [remarkLintFencedCodeFlag, false],
        [remarkLintNoFileNameIrregularCharacters, false],
        [remarkLintNoFileNameMixedCase, false],
        [remarkLintMaximumHeadingLength, false],
        [remarkLintNoDuplicateHeadings, false],
        [remarkLintHeadingIncrement, false],
        [remarkLintUnorderedListMarkerStyle, "*"],
        remarkLintNeedsReformatting,
    ],
};

/** @type {Preset} */
const config = {
    plugins: [
        remarkGfm,
        remarkMdx,
        [remarkFrontmatter, ["yaml"]],
        remarkLintRules,
        [remarkStringify, stringifyOptions],
    ],
};

export default config;
