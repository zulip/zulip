exports.t = function (str, context) {
    // We are currently assuming that we will receive context in form of a Dict
    // of key value pairs and string will be having substitution for keywords
    // like these "__keyword__".
    if (context === undefined) {
        return 'translated: ' + str;
    }
    var keyword_regex = /__(- )?(\w)+__/g;
    var keys_in_str = str.match(keyword_regex);
    var substitutions = _.map(keys_in_str, function (key) {
        var prefix_length;
        if (key.startsWith("__- ")) {
            prefix_length = 4;
        } else {
            prefix_length = 2;
        }
        return {
            keyword: key.slice(prefix_length, key.length - 2),
            prefix: key.slice(0, prefix_length),
            suffix: key.slice(key.length - 2, key.length),
        };
    });
    _.each(substitutions, function (item) {
        str = str.replace(item.prefix + item.keyword + item.suffix,
                          context[item.keyword]);
    });
    return 'translated: ' + str;
};
