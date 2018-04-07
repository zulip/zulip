/**
 * bugdown_assert.js
 *
 * Used to determine whether two Markdown HTML strings are semantically
 * equivalent. Differs from the naive string-comparison approach in that
 * differently typed but equivalent HTML fragments, such as '<p>&quot;</p>'
 * and '<p>\"</p>', and '<span attr1="a" attr2="b"></span>' and
 * '<span attr2="a" attr1="b"></span>', are still considered equal.
 *
 * The exported method equal() serves as a drop-in replacement for
 * assert.equal().  Likewise, the exported method notEqual() replaces
 * assert.notEqual().
 *
 * There is a default _output_formatter used to create the
 * AssertionError error message; this function can be overriden using
 * the exported setFormatter() function below.
 *
 * The HTML passed to the _output_formatter is not the original HTML, but
 * rather a serialized version of a DOM element generated from the original
 * HTML.  This makes it easier to spot relevant differences.
 */

const jsdom = require('jsdom');
const _ = require('underscore');

const mdiff = require('./mdiff.js');

// Module-level global instance of MarkdownComparer, initialized when needed
let _markdownComparerInstance = null;

class MarkdownComparer {
    constructor(output_formatter) {
        this._output_formatter = output_formatter || function (actual, expected) {
            return ["Actual and expected output do not match.",
                    actual,
                    "!=",
                    expected,
                ].join('\n');
        };
        this._document = jsdom.jsdom();
    }

    setFormatter(output_formatter) {
        this._output_formatter = output_formatter || this._output_formatter;
    }

    _htmlToElement(html, id) {
        const template = this._document.createElement('template');
        const id_node = this._document.createAttribute('id');
        id_node.value = id;
        template.setAttributeNode(id_node);
        template.innerHTML = html;
        return template;
    }

    _haveEqualContents(node1, node2) {
        if (node1.content.childNodes.length !== node2.content.childNodes.length) {
            return false;
        }
        return _.reduce(
            _.zip(node1.content.childNodes, node2.content.childNodes),
            (prev, nodePair) => { return prev && nodePair[0].isEqualNode(nodePair[1]); },
            true
        );
    }

    _reorderAttributes(node) {
        // Sorts every attribute in every element by name.  Ensures consistent diff HTML output

        const attributeList = [];
        _.forEach(node.attributes, (attr) => {
            attributeList.push(attr);
        });

        // If put in above forEach loop, causes issues (possible nodes.attribute invalidation?)
        attributeList.forEach((attr) => {node.removeAttribute(attr.name);});

        attributeList.sort((a, b) => {
            const name_a = a.name;
            const name_b = b.name;
            if (name_a < name_b) {
                return -1;
            } else if (name_a > name_b) {
                return 1;
            }
            return 0;
        });

        // Put them back in, in order
        attributeList.forEach((attribute) => {
            node.setAttribute(attribute.name, attribute.value);
        });

        if (node.hasChildNodes()) {
            _.forEach(node.children, (childNode) => {
                this._reorderAttributes(childNode);
            });
        }
        if (node.content && node.content.hasChildNodes()) {
            _.forEach(node.content.children, (childNode) => {
                this._reorderAttributes(childNode);
            });
        }
        return node;
    }

    _compare(actual_markdown, expected_markdown) {
        const ID_ACTUAL = "0";
        const ID_EXPECTED = "1";

        const element_actual = this._htmlToElement(actual_markdown, ID_ACTUAL);
        const element_expected = this._htmlToElement(expected_markdown, ID_EXPECTED);

        let are_equivalent = false;
        let html = {};

        are_equivalent = this._haveEqualContents(element_actual, element_expected);
        if (!are_equivalent) {
            html = {
                actual : this._reorderAttributes(element_actual).innerHTML,
                expected : this._reorderAttributes(element_expected).innerHTML,
            };
        }

        element_actual.remove();
        element_expected.remove();

        return { are_equivalent, html };
    }

    assertEqual(actual, expected, message) {
        const comparison_results = this._compare(actual, expected);

        message = message || '';
        message += '\n';

        if (comparison_results.are_equivalent === false) {
            throw new assert.AssertionError({
                message : message + this._output_formatter(
                    comparison_results.html.actual,
                    comparison_results.html.expected
                ),
            });
        }
    }

    assertNotEqual(actual, expected, message) {
        const comparison_results = this._compare(actual, expected);

        message = message || '';
        message += '\n';

        if (comparison_results.are_equivalent) {
            throw new assert.AssertionError({
                message : message + [
                    "actual and expected output produce semantially identical HTML",
                    actual,
                    "==",
                    expected,
                ].join('\n'),
            });
        }
    }
}

function returnComparer() {
    if (!_markdownComparerInstance) {
        _markdownComparerInstance = new MarkdownComparer((actual, expected) => {
            return [
                "Actual and expected output do not match.  Showing diff",
                mdiff.diff_strings(actual, expected),
            ].join('\n');
        });
    }
    return _markdownComparerInstance;
}

module.exports = {
    equal(expected, actual, message) {
        returnComparer().assertEqual(actual, expected, message);
    },

    notEqual(expected, actual, message) {
        returnComparer().assertNotEqual(actual, expected, message);
    },

    setFormatter(output_formatter) {
        returnComparer().setFormatter(output_formatter);
    },
};
