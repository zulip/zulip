var i18n = {};

i18n.t = function (str, context) {
    // We are currently assuming that we will receive context in form of a Dict
    // of key value pairs and string will be having substitution for keywords
    // like these "__keyword__".
    if (context === undefined) {
        return 'translated: ' + str;
    }
    var keyword_regex = /__(\w)+__/g;
    var keys_in_str = str.match(keyword_regex);
    var keywords = _.map(keys_in_str, function (key) {
        return key.slice(2, key.length - 2);
    });
    _.each(keywords, function (keyword) {
        str = str.replace('__' + keyword + '__', context[keyword]);
    });
    return 'translated: ' + str;
};

i18n.ensure_i18n = function (f) { f(); };

module.exports = i18n;
