// Run:
// > rm -rf var/webpack-cache
// and restart server to load changes to this file.

// This plugin converts properties which affect the
// vertical space occupied by an element with some
// expception like font-size into `rem`.
// We don't want to change properties affecting
// horizontal space because media queries don't
// place nice with them.

// Functions in the files inspired from
// https://github.com/cuth/postcss-pxtorem/blob/master/index.js
// which appears to have good testing for these functions.

// Not anything inside double quotes
// Not anything inside single quotes
// Not anything inside url()
// Any digit followed by px
// !singlequotes|!doublequotes|!url()|pixelunit
const pxRegex = /"[^"]+"|'[^']+'|url\([^)]+\)|var\([^)]+\)|(\d*\.?\d+)px/g;

function toFixed(number, precision) {
    const multiplier = Math.pow(10, precision + 1),
        wholeNumber = Math.floor(number * multiplier);
    return (Math.round(wholeNumber / 10) * 10) / multiplier;
}

function createPxReplace(rootValue, unitPrecision) {
    return (m, $1) => {
        if (!$1) return m;
        const pixels = parseFloat($1);
        const fixedVal = toFixed(pixels / rootValue, unitPrecision);
        return fixedVal === 0 ? "0" : fixedVal + "rem";
    };
}

const pxReplace = createPxReplace(14, 5);

module.exports = (opts = {}) => {
    opts = opts || {};

    // The properties can have just
    // single px values so they
    // are easy to convert to rem.
    const simple_transforms = [
        "font-size",
        "line-height",
        "height",
        "padding-top",
        "padding-bottom",
        "margin-top",
        "margin-bottom",
        "top",
        "bottom",
        "width", // Only changed for icon_classes.
    ];

    // We need keep height and widht same for these
    // icons, otherwise they will become distorted.
    const icon_classes = [
        ".user_circle",
        ".emoji",
        ".popover_user_presence",
        ".inline_profile_picture",
        ".icon",
        ".image-block",
    ];

    return {
        postcssPlugin: "vertical_px_to_rem",
        Once(css, {result}) {
            // const filePath = css.source.input.file;
            // if (!filePath.includes("recent_topics")) {
            //     return;
            // }
            css.walkDecls((decl) => {
                // Only convert declarations which have
                // px values.
                if (decl.value.indexOf("px") === -1) {
                    return;
                }

                // Only convert width for icons to rem.
                if (decl.prop == "width") {
                    for (const icon of icon_classes) {
                        if (decl.parent.selector && decl.parent.selector.endsWith(icon)) {
                            decl.cloneAfter({value: decl.value.replace(pxRegex, pxReplace)});
                        }
                    }
                    return;
                }

                if (simple_transforms.includes(decl.prop)) {
                    const value = decl.value.replace(pxRegex, pxReplace);
                    // Clone the converted value so that px value still
                    // remains and thus is easier for developer to debug changes.
                    decl.cloneAfter({value: value});
                } else if (["padding", "margin"].includes(decl.prop)) {
                    let value = decl.value;
                    let value_parts = value.split(" ");
                    // `padding: 10px' -> `padding: 10/14rem 10px`.
                    if (value_parts.length === 1) {
                        decl.cloneAfter({
                            value: decl.value.replace(pxRegex, pxReplace) + " " + value,
                        });
                        // `padding: 10px 10px' -> `padding: 10/14rem 10px`.
                    } else if (value_parts.length === 2 && value_parts[0].includes("px")) {
                        const value_parts_rem = value_parts.map((part) =>
                            part.replace(pxRegex, pxReplace),
                        );
                        decl.cloneAfter({value: value_parts_rem[0] + " " + value_parts[1]});
                        // `padding: 10px 10px 10px' -> `padding: 10/14rem 10px 10/14rem`.
                    } else if (
                        (value_parts.length === 3 && value_parts[0].includes("px")) ||
                        (value_parts.length === 3 && value_parts[2].includes("px"))
                    ) {
                        const value_parts_rem = value_parts.map((part) =>
                            part.replace(pxRegex, pxReplace),
                        );
                        decl.cloneAfter({
                            value:
                                value_parts_rem[0] +
                                " " +
                                value_parts[1] +
                                " " +
                                value_parts_rem[2],
                        });
                        // `padding: 10px 10px 10px 10px' -> `padding: 10/14rem 10px 10/14rem 10px`.
                    } else if (
                        (value_parts.length === 4 && value_parts[0].includes("px")) ||
                        (value_parts.length === 4 && value_parts[2].includes("px"))
                    ) {
                        const value_parts_rem = value_parts.map((part) =>
                            part.replace(pxRegex, pxReplace),
                        );
                        decl.cloneAfter({
                            value:
                                value_parts_rem[0] +
                                " " +
                                value_parts[1] +
                                " " +
                                value_parts_rem[2] +
                                " " +
                                value_parts[3],
                        });
                    }
                }
            });
        },
    };
};
module.exports.postcss = true;
