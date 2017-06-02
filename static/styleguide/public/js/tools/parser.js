var CSSParser = function (stylesheet) {
    var base = {},
        generic = [],
        failures = [];

    var prototype;

    var funcs = {
        add_selector_prefix: function (sel) {
            return sel.split(/\s*,\s*/).map(function (o) {
                if (o.match("body")) {
                    return o.replace("body", ".styleguide-preview");
                } else {
                    return ".styleguide-preview " + o;
                }
            }).join(", ");
        },
        add: function (base_sel, value, namespace) {
            if (base_sel === false) {
                if (generic.indexOf(value) === -1) {
                    generic.push(value);
                }
            } else {
                if (!base[base_sel]) {
                    base[base_sel] = [{ namespace: namespace, value: value }];
                } else {
                    if (base[base_sel].indexOf(value) === -1) {
                        // add namespace to here...
                        base[base_sel].push({ namespace: namespace, value: value });
                    }
                }
            }
        },
        parse_selector: function (sel) {
            var matches = sel.match(/(\.|#|\[|\s+|[\w-_])[^#.[ ]+/g);

            var obj = {
                modifier: matches.pop(),
                base: matches.join("")
            };

            return obj;
        },
        validator: function (sel) {
            if (sel.split(/\s*,\s*/).length > 1) {
                sel.split(/\s*,\s*/).forEach(function (o) {
                    funcs.validator(o);
                });

                return;
            }

            var components = sel.split(/\s+/),
                flag = null,
                error = "",
                last = components[components.length - 1];

            if (last.indexOf("#") > last.indexOf(".")) {
                flag = false;
                error = prototype._.INVALID_ID_SELECTOR;
            } else if (/:/.test(sel)) {
                flag = false;
                error = prototype._.NO_UNGROUND_STATES;
            } else if (components.length === 1) {
                if (/\./.test(components[0])) {
                    flag = true;
                } else {
                    flag = false;
                    error = prototype._.NO_MODIFIER;
                }
            }

            if (flag === true) {
                var result = funcs.parse_selector(sel);

                if (!base[result.base]) {
                    base[result.base] = [];
                }

                base[result.base].push(result.modifier);
            } else {
                failures.push(sel);
            }
        },
        _validator: function (sel) {
            var arr = [];

            if (!sel) {
                return;
            }

            (sel.match(/([\w-_]*\.[\w-_]+)+/g) || []).forEach(function (m) {
                var classes = m.split(/\./);

                var obj = {
                    modifier: "." + classes.pop(),
                    base: classes.join(".") || false,
                    namespace: null
                };

                if (obj.base) {
                    obj.namespace = sel.substr(0, sel.indexOf(obj.base + obj.modifier) - 1);
                }

                funcs.add(obj.base, obj.modifier, obj.namespace);
            });

            return this;
        }
    };

    var iterate_rules = function (sheet, rules) {
        var bases = Object.keys(base);

        T.Array.forEach(rules || [], function (o, i) {
            prototype.selector.parse(o.selectorText);
            if (o.selectorText) {
                var text = o.cssText,
                    selector = o.selectorText;

                sheet.deleteRule(i);
                if (o.cssText) {
                    var sel = text.replace(selector, funcs.add_selector_prefix(selector));

                    sheet.insertRule(sel, i);
                }
            } else if (o.cssRules) {
                iterate_rules(o, o.cssRules);
            }
        });
    };

    prototype = {
        selector: {
            parse: funcs._validator
        },
        _: {
            // the modifier doesn't exist (eg. it's just "button", not "button.hide").
            NO_MODIFIER: 1,
            // if the last element in the selector is an ID it shouldn't be included
            // because only one of it should exist.
            INVALID_ID_SELECTOR: 2,
            // if a selector has :focus, :active, :hover, :visited, etc. it isn't in
            // its "ground state" and shouldn't be included.
            NO_UNGROUND_STATES: 3
        },
        get: function () {
            return {
                base: base,
                generic: generic
            };
        },
        add: function (link) {
            var sheet = link.sheet,
                rules = sheet.rules || sheet.cssRules;

            if (rules) {
                iterate_rules(sheet, rules);
            }
        }
    };

    T.Array.forEach(stylesheet ? [stylesheet] : document.styleSheets, function (stylesheet, i) {
      var owner = stylesheet.ownerNode;
      if (owner.classList.contains("audit") && !owner.disabled) {
        var rules = stylesheet.rules || stylesheet.cssRules;

        if (rules) {
          iterate_rules(stylesheet, rules);
        }
      }
    });

    return prototype;
};
