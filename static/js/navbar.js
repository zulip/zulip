var navbar = (function () {
var exports = {};

exports.display_user_avatar = function () {
    var avatar_url = page_params.avatar_url;
    var template = templates.render("user_avatar", {avatar_url: avatar_url});
    var $avatar = $("#user-avatar");

    $avatar.append(template);
};

$(function () {
    exports.display_user_avatar();
});

return exports;

}());
