var T = (function () {
    var Validator = function (component) {
        var prototype = {
            values: function (opts) {
                opts = opts || {};
                var values = {};

                _.O.forEach(component._, function (node, key) {
                    if (/textarea|input|select/i.test(node.tagName) && node.type !== "submit") {
                        values[key] = node.value || node.innerText;                      
                    }

                    if (opts.clear && node.value) {
                        node.value = "";
                    }
                });

                return values;
            },
            validate: function (obj, opts) {
                obj = obj || {};

                var validation = { success: [], error: [] },
                    flags = 0;

                _.O.forEach(obj, function (o, key) {
                    if (component._[key] && typeof o === "function") {
                      var result = !!o(component._[key].value, component._[key]);
                      validation[result ? "success" : "error"].push({
                        key: key, node: component._[key] 
                      });
                      flags += result;
                    }
                });

                var error = function (callback) {
                    callback(validation);
                };

                return {
                    then: function (callback) {
                        if (flags === Object.keys(obj).length) {
                            callback(prototype.values(opts));
                        }

                        return { error: error };
                    },
                    error: error
                };
            }
        };

        return prototype;
    };

    var _ = {
        A: {
            forEach: function (arr, callback) {
                for (var x = 0; x < arr.length; x++) {
                    callback(arr[x], x);
                }
            },
            map: function (arr, callback) {
                var map = [];

                this.forEach(arr, function (o, i) {
                    map[i] = callback(o, i);
                });

                return map;
            },
            filter: function (arr, callback) {
                var filter = [];

                this.forEach(arr, function (o, i) {
                    if (callback(o, i)) filter.push(o);
                });

                return filter;
            }
        },
        O: {
            forEach: function (obj, callback) {
                for (var x in obj) {
                    if (obj.hasOwnProperty(x)) {
                        callback(obj[x], x);
                    }
                }
            }
        },
        color: {
            hex_to_array: function (hex) {
                if (hex.charAt(0) === "#") {
                    hex = hex.slice(1);
                }

                if (hex.length === 3) {
                    hex = hex[0].repeat(2) + hex[1].repeat(2) + hex[2].repeat(2);
                }

                return _.A.map(new Array(3), function (o, i) {
                    var x = hex.slice(i * 2, i * 2 + 2);
                    return parseInt(x, 16);
                });
            },
            rgb_to_array: function (rgb) {
                rgb = rgb.match(/(rgba*\()([^)]+)(\))/)[2];

                return rgb.replace(/\s+/, "").split(/,/).map(function (o) {
                    return parseInt(o, 10);
                });
            },
            array_to_rgb: function (arr) {
                return "rgb(" + arr.join(", ") + ")";
            },
            array_to_hex: function (arr) {
                var hex = "#" + arr.map(function (o) {
                    return ("0" + o.toString(16)).slice(-2);
                }).join("");

                return this.minify_hex(hex);
            },
            minify_hex: function (hex) {
                if (hex.charAt(0) === "#") {
                    hex = hex.substr(1);
                }

                if (hex[0] === hex[1] && hex[2] === hex[3] && hex[4] === hex[5]) {
                    return "#" + hex[0] + hex[2] + hex[3];
                } else {
                    return "#" + hex;
                }
            }
        }
    };

    var funcs = {
        CSS: {
            get_class_list: function () {
                var sheets = document.styleSheets;

                for (var x = 0; x < sheets.length; x++) {
                    var rules = sheets[x].rules || sheets[x].cssRules,
                        valid;

                    if (rules) {
                        valid = _.A.filter(rules, function (o) {
                            return /\.\w+--/.test(o.selectorText) && !/:/.test(o.selectorText);
                        });

                        valid = _.A.map(valid, function (o) {
                            return o.selectorText;
                        });
                    }
                }
            }
        },
        DOM: {
            set_attr: function (node, prop, val) {
                var not = ["for"],
                    boolean = ["checked"];

                if (boolean.indexOf(prop) !== -1) {
                    if (val === "true") val = true;
                    else if (val === "false") val = false;
                    else val = {};
                }

                if (val.length > 0 || typeof val === "boolean") {
                    if (not.indexOf(prop) === -1) {
                        node[prop] = val;
                    } else {
                        node.setAttribute(prop, val);
                    }
                } else {
                    if (not.indexOf(prop) === -1) {
                        node[prop] = val;
                    }
                    node.removeAttribute(prop);
                }
            },
            parent: function (node, levels) {
                for (var x = 0; x < levels; x++) {
                    if (node.parentNode) {
                        node = node.parentNode;
                    } else {
                        return false;
                    }
                }

                return node;
            },
            element: function (tag, props) {
                var elem = document.createElement(tag || "div"),
                    not = ["innerHTML", "className"];

                for (var x in props) {
                    if (x.indexOf(not) > -1) {
                        elem.setAttribute(x, props[x]);
                    } else {
                        if (x === "innerHTML" && typeof props[x] === "object") {
                            elem[x].appendChild(props[x]);
                        } else {
                            elem[x] = props[x];
                        }
                    }
                }

                return elem;
            },
            table: function (head, body, props, config) {
                var e = funcs.DOM.element;

                config = config || {};

                if (!props) {
                    props = {
                        className: "locked"
                    };
                } else {
                    props.className = "locked";
                }

                var table = e("table", props),
                    thead = e("thead"),
                    tbody = e("tbody");

                if (config.max_lines > 0) {
                    body.splice(config.max_lines);
                }

                table.appendChild(thead);
                table.appendChild(tbody);

                head.forEach(function (col) {
                    thead.appendChild(e("td", {
                        innerHTML: col
                    }));
                });

                table.structure = {};

                body.forEach(function (row, r_idx) {
                    var tr = e("tr");

                    table.structure[row[0]] = [];

                    row.forEach(function (col, c_idx) {
                        var td = e("td", {
                            innerHTML: col,
                        });

                        table.structure[row[0]].push(td);

                        td.dataset.row = r_idx;
                        td.dataset.column = c_idx;

                        if (c_idx === 1) {
                            td.contentEditable = true;
                        }

                        if (config.td_event) {
                            E(td).add(config.td_event);
                        }

                        tr.appendChild(td);
                    });

                    tbody.appendChild(tr);
                });

                return table;
            }
        },
        Array: _.A,
        Object: _.O,
        color: {
            hex_to_rgb: function (hex) {
                var arr = _.color.hex_to_array(hex);
                return _.color.array_to_rgb(arr);
            },
            rgb_to_hex: function (rgb) {
                var arr = _.color.rgb_to_array(rgb);
                return _.color.array_to_hex(arr);
            },
            to_array: function (val) {
                if (this.format(val) === "hex") {
                    return _.color.hex_to_array(val);
                } else {
                    return _.color.rgb_to_array(val);
                }
            },
            format: function (val) {
                if (val.charAt(0) === "#" || val.lenth === 6 || val.length === 3) {
                    return "hex";
                } else {
                    return "rgb";
                }
            }
        },
        isMobile: (function () {
            return (/Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent)) || window.innerWidth < 768;
        }()),
        V: Validator
    };

    return funcs;
}());
