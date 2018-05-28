var schema = (function () {

var exports = {};

/*

These runtime schema validators are defensive and
should always succeed, so we don't necessarily want
to translate these.  These are very similar to server
side validators in zerver/lib/validator.py.

*/

exports.check_string = function (var_name, val) {
    if (!_.isString(val)) {
        return var_name + ' is not a string';
    }
};

exports.check_record = function (var_name, val, fields) {
    if (!_.isObject(val)) {
        return var_name + ' is not a record';
    }

    var field_results = _.map(fields, function (f, field_name) {
        if (val[field_name] === undefined) {
            return field_name + ' is missing';
        }
        return f(field_name, val[field_name]);
    });

    var msg = _.filter(field_results).sort().join(', ');

    if (msg) {
        return 'in ' + var_name + ' ' + msg;
    }
};

exports.check_array = function (var_name, val, checker) {
    if (!_.isArray(val)) {
        return var_name + ' is not an array';
    }

    var msg;

    _.find(val, function (item) {
        var res = checker('item', item);

        if (res) {
            msg = res;
            return msg;
        }
    });

    if (msg) {
        return 'in ' + var_name + ' we found an item where ' + msg;
    }
};

return exports;

}());
if (typeof module !== 'undefined') {
    module.exports = schema;
}

window.schema = schema;
