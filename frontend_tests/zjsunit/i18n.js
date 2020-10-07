"use strict";

exports.t = function (str, context) {
    // HAPPY PATH: most translations are a simple string:
    if (context === undefined) {
        return "translated: " + str;
    }

    /*
    context will be an ordinary JS object like this:

        {minutes: minutes.toString()}

    This supports use cases like the following:

        i18n.t("__minutes__ min to edit", {minutes: minutes.toString()})

    We have to munge in the context here.
    */
    const keyword_regex = /__(- )?(\w)+__/g;
    const keys_in_str = str.match(keyword_regex) || [];
    const substitutions = keys_in_str.map((key) => {
        let prefix_length;
        if (key.startsWith("__- ")) {
            prefix_length = 4;
        } else {
            prefix_length = 2;
        }
        return {
            keyword: key.slice(prefix_length, -2),
            prefix: key.slice(0, prefix_length),
            suffix: key.slice(-2, key.length),
        };
    });

    for (const item of substitutions) {
        str = str.replace(item.prefix + item.keyword + item.suffix, context[item.keyword]);
    }

    return "translated: " + str;
};
