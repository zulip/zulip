var muting_user = (function () {

var exports = {};

var muted_user_names = new Array();  //muted_user_nqmes is a list of muted user names
var muted_user_ids = new Array();    //muted_user_ids is a list of muted user ids

exports.add_muted_user = function (muted_user) {
    if($.inArray(muted_user[0], muted_user_ids)==-1)
	muted_user_names.push(muted_user[1]);
	muted_user_ids.push(muted_user[0]);
};

exports.remove_muted_user = function (muted_user) {
    var index=$.inArray(muted_user[0], muted_user_ids);
    if (index!=-1) {
        muted_user_names.splice(index, 1);
	muted_user_ids.splice(index, 1);
    }
};

exports.is_user_muted = function (muted_user_id) {
    var index=$.inArray(muted_user_id, muted_user_ids);
    if (index==-1) {
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

exports.set_muted_users = function (tuples) { //tuples is list of tuples with each tuple containing muted_user_id and muted_user_name
    muted_users = new Array();

    _.each(tuples, function (tuple) {
        exports.add_muted_user([tuple[0],tuple[1]]);
    });
};

return exports;
}());
if (typeof module !== 'undefined') {
    module.exports = muting_user;
}
