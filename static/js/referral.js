var referral = (function () {

var exports = {};

exports.update_state = function (granted, used) {
    if (granted <= 0) {
        $("#share-the-love").hide();
        return;
    }

    $("#invite-hearts").empty();
    var i;
    for (i = 0; i < used; i++) {
        $("#invite-hearts").append($('<i class="icon-vector-heart"> </i>'));
    }

    var invites_left = Math.max(0, granted - used);
    for (i = 0; i < invites_left; i++) {
        $("#invite-hearts").append($('<i class="icon-vector-heart-empty"> </i>'));
    }
    $(".invite-count").text(invites_left);
    if (invites_left === 1) {
        $(".invite-count-is-plural").hide();
    } else {
        $(".invite-count-is-plural").show();
    }

    if (invites_left > 0) {
        $(".still-have-invites").show();
        $(".no-more-invites").hide();
    } else {
        $(".still-have-invites").hide();
        $(".no-more-invites").show();
    }
    $("#share-the-love").show();
};

function show_and_fade_elem(elem) {
    elem.stop();
    elem.css({opacity: 100});
    elem.show().delay(4000).fadeOut(1000);
}

$(function () {
    $("#referral-form").validate({
        errorClass: 'text-error',
        submitHandler: function () {
            $.ajax({
                type: "POST",
                url: "/json/refer_friend",
                dataType: "json",
                data: { email: $("#referral-form input").val() },
                success: function () {
                    show_and_fade_elem($("#tell-a-friend-success"));
                    $("#referral-form input").val('');
                },
                error: function () {
                    show_and_fade_elem($("#tell-a-friend-error"));
                }
            });
        }
    });

    exports.update_state(page_params.referrals.granted, page_params.referrals.used);
});

return exports;
}());
