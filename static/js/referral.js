var referral = (function () {

var exports = {};

var placeholder_invitees = ['nikola.tesla@example.com',
                            'sam.morse@example.com',
                            'c.shannon@example.com',
                            'hedy.lamarr@example.com',
                            'grace.hopper@example.com',
                            'ada.lovelace@example.com'];

var last_granted;
var last_used;
var ever_had_invites = false;
exports.update_state = function (granted, used) {
    if (last_granted === granted && last_used === used) {
        return;
    }

    last_granted = granted;
    last_used = used;

    if (granted <= 0 || !page_params.share_the_love) {
        $("#share-the-love").hide();
    } else {
        $("#referral-form input").attr('placeholder', _.shuffle(placeholder_invitees).pop());
        $("#invite-hearts").empty();
        var i;
        for (i = 0; i < used; i += 1) {
            $("#invite-hearts").append($('<i class="icon-vector-heart"> </i>'));
        }

        var invites_left = Math.max(0, granted - used);
        for (i = 0; i < invites_left; i += 1) {
            $("#invite-hearts").append($('<i class="icon-vector-heart-empty"> </i>'));
        }

        var invites_left_text = i18n.t('__count__ invite remaining', {count: invites_left});
        $(".invite-count").text(invites_left_text);

        if (invites_left > 0) {
            ever_had_invites = true;
            $(".still-have-invites").show();
            $(".no-more-invites").hide();
        } else {
            $(".still-have-invites").hide();
            $("#referral-form input").blur();
            if (ever_had_invites) {
                $(".no-more-invites").show();
            }
        }

        if (used > 0) {
            $("#encouraging-invite-message").hide();
        }

        $("#share-the-love").show();
    }

    resize.resize_page_components();
};

function show_and_fade_elem(elem) {
    elem.stop();
    elem.css({opacity: 100});
    elem.show().delay(4000).fadeOut(1000, ui.resize_page_components);
}

$(function () {
    var validator = $("#referral-form").validate({
        errorClass: 'text-error',
        submitHandler: function () {
            channel.post({
                url: "/json/refer_friend",
                data: { email: $("#referral-form input").val() },
                error: function () {
                    // We ignore errors from the server because
                    // they're unlikely and we'll get an email either
                    // way
                },
            });

            show_and_fade_elem($("#tell-a-friend-success"));
            $("#referral-form input").val('');
            exports.update_state(last_granted, last_used + 1);
        },
        success: function () {
            resize.resize_page_components();
        },
        showErrors: function () {
            this.defaultShowErrors();
            resize.resize_page_components();
        },
    });

    $("#referral-form input").on('blur', function () {
        if ($("#referral-form input").val() === '') {
            validator.resetForm();
            resize.resize_page_components();
        }
    });

    $("#referral-form").on("click", function (e) {
        e.stopPropagation();
    });

    $("#share-the-love-expand-collapse").click(function (e) {
        $("#share-the-love-contents").toggle();
        $("#share-the-love-expand-collapse .toggle").toggleClass('icon-vector-caret-right icon-vector-caret-down');
        resize.resize_page_components();
        e.stopPropagation();
    });

    exports.update_state(page_params.referrals.granted, page_params.referrals.used);
});

return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = referral;
}
