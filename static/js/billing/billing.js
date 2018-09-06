$(function () {
    var stripe_key = $("#payment-method").data("key");
    var handler = StripeCheckout.configure({ // eslint-disable-line no-undef
        key: stripe_key,
        image: '/static/images/logo/zulip-icon-128x128.png',
        locale: 'auto',
        token: function (stripe_token) {
            var csrf_token = $("#payment-method").data("csrf");
            loading.make_indicator($('#updating_card_indicator'),
                                   {text: 'Updating card. Please wait ...', abs_positioned: true});
            $("#payment-section").hide();
            $("#loading-section").show();
            $.post({
                url: "/json/billing/sources/change",
                data: {
                    stripe_token: JSON.stringify(stripe_token.id),
                    csrfmiddlewaretoken: csrf_token,
                },
                success: function () {
                    $("#loading-section").hide();
                    $("#card-updated-message").show();
                    location.reload();
                },
                error: function (xhr) {
                    $("#loading-section").hide();
                    $('#error-message-box').show().text(JSON.parse(xhr.responseText).msg);
                },
            });
        },
    });

    $('#update-card-button').on('click', function (e) {
        var email = $("#payment-method").data("email");
        handler.open({
            name: 'Zulip',
            zipCode: true,
            billingAddress: true,
            panelLabel: "Update card",
            email: email,
            label: "Update card",
            allowRememberMe: false,
        });
        e.preventDefault();
    });

    $('#billing-tabs a').click(function (e) {
        e.preventDefault();
        $(this).tab('show');
    });
});
