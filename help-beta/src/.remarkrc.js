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
import remarkLintOrderedListMarkerValue from "remark-lint-ordered-list-marker-value";
import remarkLintUnorderedListMarkerStyle from "remark-lint-unordered-list-marker-style";
import remarkPresentLintMarkdownStyleGuide from "remark-preset-lint-markdown-style-guide";
import remarkLintRulesLintRecommended from "remark-preset-lint-recommended";

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
        [remarkLintOrderedListMarkerValue, false],
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
    plugins: [[remarkFrontmatter, ["yaml"]], remarkLintRules],
};

export default config;
