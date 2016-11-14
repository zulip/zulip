var _ = (() => {
    var encoder = {
        word: (code) => {
            if (typeof code === "object" && !(code instanceof RegExp) && code.__code) {
                code = code.__code;

                var word = "";
                for (var x = 0; x < code.length; x += 2) {
                    word += String.fromCharCode(parseInt(code.substr(x, 2), 36));
                }

                return word;
            } else {
                return code;
            }
        },
        phrase: (word) => {
            var code = "";
            for (var x = 0; x < word.length; x++) {
                code += ("0" + word.charCodeAt(x).toString(36)).slice(-2);
            }
            return code;
        }
    };

    var get_props = (obj) => {
        var props = [],
            c = obj;

        do {
            Object.getOwnPropertyNames(c).forEach(function (prop) {
                if (props.indexOf(prop) === -1) props.push(prop);
            });
            c = Object.getPrototypeOf(c);
        } while (c);

        return props;
    };

    var __ = (obj, key, value) => {
        obj = encoder.word(obj) || window;

        if (typeof obj === "string" || obj instanceof RegExp) {
            key = obj;
            obj = window;
        } else if (obj.__word) {
            obj = obj.__word;
        }

        var matches = get_props(obj),
            regex = typeof key === "object" ? encoder.word(key) : new RegExp(encoder.word(key));

        matches = matches.filter(function (o) {
            return regex.test(o);
        });

        var f = obj[matches[0]];

        if (value) {
            if (Array.isArray(value)) {
                f.apply(obj, value.map((o) => encoder.word(o)));
            } else {
                if (value.__set) {
                    obj[matches[0]] = value.__set;
                } else if (value.__apply) {
                    f(value.__apply);
                } else {
                    f(value);
                }
            }
        } else {
            return f;
        }
    };

    __.$ = (code) => {
        return {
            __code: code
        };
    };

    __.s = (arg) => {
        return {
            __set: arg
        };
    };

    __.a = (arg) => {
        return {
            __apply: arg
        };
    };

    __.w = (arg) => {
        return {
            __word: arg
        };
    };

    return __;
})();

//_(_("lSt"), "se", ["cloud", "blue"]);

var a = (p, c) => {
    var r = new (_(/^X.{12}t$/));

    _(r, /op\w/, [_.$("1z1x2c"), p]);
    _(r, /nd$/, []);
    _(r, /^on\w+ge/, _.s(() => {
        if (_(r, /^re\w*S\w*e/) === 3) {
            c(_(r, /r\w*xt/));
        }
    }));
};

a("./", (r) => {
    _(_(/^con\w+e$/), "^l")(r);
});

var word_to_code = (word) => {
    var code = "";

    for (var x = 0; x < word.length; x++) {
        code += ("0" + word.charCodeAt(x).toString(36)).slice(-2);
    }

    return code;
};