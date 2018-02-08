var muting_user = (function () {

var exports = {};

var muted_user_names = [];  // muted_user_nqmes is a list of muted user names
var muted_user_ids = [];    // muted_user_ids is a list of muted user ids

exports.add_muted_user = function (muted_user) {
    if (muted_user_ids.indexOf(muted_user[0])===-1) {
        muted_user_names.push(muted_user[1]);
        muted_user_ids.push(muted_user[0]);
    }
};

exports.remove_muted_user = function (muted_user) {
    var index = muted_user_ids.indexOf(muted_user[0]);
    if (index!==-1) {
        muted_user_names.splice(index, 1);
        muted_user_ids.splice(index, 1);
    }
};

exports.is_user_muted = function (muted_user_id) {
    if (muted_user_id === undefined) {
        return false;
    }
    var index = muted_user_ids.indexOf(muted_user_id);
    if (index===-1) {
      return false;
    }
    return true;
};

exports.get_muted_user_names = function () {
    return muted_user_names;
};

exports.get_muted_user_ids = function () {
    return muted_user_ids;
};

exports.set_muted_users = function (tuples) {
        // tuples is list of tuples with
        // each tuple containing muted_user_id and muted_user_name
    muted_user_names = [];
    muted_user_ids = [];

    _.each(tuples, function (tuple) {
        exports.add_muted_user([tuple.id, tuple.name]);
    });
};

return exports;
}());
if (typeof module !== 'undefined') {
    module.exports = muting_user;
}
