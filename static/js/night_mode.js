var night_mode = (function () {

var exports = {};

var create_stylesheet = function () {
    var stylesheet = document.createElement('style');
    stylesheet.type = "text/css";
    stylesheet.classList.add("night-mode-stylesheet");
    // disable the stylesheet by default in case the user isn't running night mode.
    stylesheet.disabled = true;

    return stylesheet;
};

// this transforms an object into CSS. The top level keys of the object are
// the CSS selectors and the second level keys are attributes which should have
// valid CSS values.
//
// EXAMPLE:
//
// {
//     h1: {                       // h1 {
//         color: "red",           //     color: red;
//     },                          // }
//     p: {                        // p {
//         "font-size": "1em",     //     font-size: 1em;
//         "line-spacing": 1.2,    //     line-spacing: 1.2;
//     },                          // }
// }
//
// All CSS selectors are supported, everything from `h1` to
// complex selectors like `.night:not(.test)::after`.
var object_to_css = function (object) {
    var css = "";

    // for each CSS selector.
    for (var selector in object) {
        // ensure the object properties are its own and not ones injected into
        // the Object.prototype.
        if (object.hasOwnProperty(selector)) {
            // create the `h1 {` line...
            css += selector + " {";
            // and for each of the properties of the selector...
            for (var attr in object[selector]) {
                if (object[selector].hasOwnProperty(attr)) {
                    // add the attribute and its value like `attr: value;`.
                    css += "\n\t" + attr + ": " + object[selector][attr] + ";";
                }
            }
            css += "\n}\n";
        }
    }

    // trim the excess newline.
    return css.trim();
};

(function () {
    // the object to be converted to CSS.
    // this should ONLY be used if there is no obvious way to perform this action
    // by prefixing the selector with `body.night-mode`.
    var css_skeleton = {
        "a:hover": {
            color: "#65c0ed",
        },
    };

    // create a stylesheet that can be appended to the <head>.
    var stylesheet = create_stylesheet();
    // convert to CSS.
    var css = object_to_css(css_skeleton);

    if (stylesheet.styleSheet) {
        stylesheet.styleSheet.cssText = css;
    } else {
        stylesheet.appendChild(document.createTextNode(css));
    }

    // append the stylesheet.
    (document.head || document.getElementsByTagName('head')[0]).appendChild(stylesheet);

    exports.enable = function () {
        // we can also query for this in the DOM with the
        // `.night-mode-stylesheet` class.
        stylesheet.disabled = false;
        $("body").addClass("night-mode");
    };

    exports.disable = function () {
        stylesheet.disabled = true;
        $("body").removeClass("night-mode");
    };
}());

return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = night_mode;
}
