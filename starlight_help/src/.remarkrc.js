// We are using remarkLintRulesLintRecommended and
// remarkPresentLintMarkdownStyleGuide as our starting set of rules.
// None of the rules were giving an error on the starting set, but some
// rules were giving lots of warnings on the generated mdx. They are
// set to false in this file, we can add them back later as and when
// required.

/**
 * @import {Preset} from 'unified'
 */

import remarkFrontmatter from "remark-frontmatter";
import remarkLintFencedCodeFlag from "remark-lint-fenced-code-flag";
import remarkLintFileExtension from "remark-lint-file-extension";
import remarkLintFinalDefinition from "remark-lint-final-definition";
import remarkLintHeadingIncrement from "remark-lint-heading-increment";
import remarkLintListItemIndent from "remark-lint-list-item-indent";
import remarkLintListItemSpacing from "remark-lint-list-item-spacing";
import remarkLintMaximumHeadingLength from "remark-lint-maximum-heading-length";
import remarkLintMaximumLineLength from "remark-lint-maximum-line-length";
import remarkLintNoDuplicateDefinitions from "remark-lint-no-duplicate-definitions";
import remarkLintNoDuplicateHeadings from "remark-lint-no-duplicate-headings";
import remarkLintNoFileNameIrregularCharacters from "remark-lint-no-file-name-irregular-characters";
import remarkLintNoFileNameMixedCase from "remark-lint-no-file-name-mixed-case";
import remarkLintNoUnusedDefinitions from "remark-lint-no-unused-definitions";
import remarkLintUnorderedListMarkerStyle from "remark-lint-unordered-list-marker-style";
import remarkPresentLintMarkdownStyleGuide from "remark-preset-lint-markdown-style-guide";
import remarkLintRulesLintRecommended from "remark-preset-lint-recommended";
import remarkStringify from "remark-stringify";

const remarkLintRules = {
    plugins: [
        remarkLintRulesLintRecommended,
        remarkPresentLintMarkdownStyleGuide,
        [remarkLintFinalDefinition, false],
        [remarkLintListItemSpacing, false],
        [remarkLintFileExtension, ["mdx"]],
        [remarkLintNoUnusedDefinitions, false],
        [remarkLintMaximumLineLength, false],
        [remarkLintListItemIndent, false],
        [remarkLintFencedCodeFlag, false],
        [remarkLintNoFileNameIrregularCharacters, false],
        [remarkLintNoFileNameMixedCase, false],
        [remarkLintMaximumHeadingLength, false],
        [remarkLintNoDuplicateHeadings, false],
        [remarkLintHeadingIncrement, false],
        [remarkLintNoDuplicateDefinitions, false],
        [remarkLintUnorderedListMarkerStyle, "*"],
    ],
};

/** @type {Preset} */
const config = {
    plugins: [
        [remarkFrontmatter, ["yaml"]],
        remarkLintRules,
        // The format step was converting our ordered list items to have
        // incremental numbering instead of using 1. for every list item. This
        // was not because of any remark-lint rule, but because of
        // remark-stringify which auto increments any lists it processes. We
        // followed the recommended fix from
        // https://github.com/remarkjs/remark-lint/blob/ae2f941d88551d0a1103e586495dec0f55469720/packages/remark-lint-ordered-list-marker-value/readme.md?plain=1#L185
        [remarkStringify, {incrementListMarker: false}],
    ],
};

export default config;
