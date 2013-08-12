var referral = (function () {

var exports = {};

var placeholder_invitees = ['guglielmo@marconi.com',
                            'heinrich@hertz.com',
                            'nikola@tesla.com',
                            'samuel@morse.com',
                            'claude@shannon.com',
                            'thomas@edison.com',
                            'hedy@lamarr.com',
                            'grace@hopper.com',
                            'martha@coston.com',
                            'ada@lovelace.com',
                            'hanna@hammarstrom.com',
                            'hertha@ayrton.com'
                           ];

var last_granted;
var last_used;
var ever_had_invites = false;
exports.update_state = function (granted, used) {
    if (last_granted === granted && last_used === used) {
        return;
    }

    last_granted = granted;
    last_used = used;

    if (granted <= 0) {
        $("#share-the-love").hide();
    } else {
        $("#referral-form input").attr('placeholder', _.shuffle(placeholder_invitees).pop());
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

    ui.resize_page_components();
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
            $.ajax({
                type: "POST",
                url: "/json/refer_friend",
                dataType: "json",
                data: { email: $("#referral-form input").val() },
                error: function () {
                    // We ignore errors from the server because
                    // they're unlikely and we'll get an email either
                    // way
                }
            });

            show_and_fade_elem($("#tell-a-friend-success"));
            $("#referral-form input").val('');
            exports.update_state(last_granted, last_used + 1);
        },
        success: function () {
            ui.resize_page_components();
        },
        showErrors: function () {
            this.defaultShowErrors();
            ui.resize_page_components();
        }
    });

    $("#referral-form input").on('blur', function (e) {
        if ($("#referral-form input").val() === '') {
            validator.resetForm();
            ui.resize_page_components();
        }
    });

    exports.update_state(page_params.referrals.granted, page_params.referrals.used);
});

return exports;
}());
