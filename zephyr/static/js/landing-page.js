function populate_signup_form_placeholders() {
    var candidates = [
        {name: "Wolfgang A. Mozart", email: "w.a.mozart@magicflute.com", company: "Salzburg Court", count: "10", product: "harpsichords"},
        {name: "Alexander Hamilton", email: "alex1755@treas.gov", company: "US Treasury", count: "25", product: "ink and quill"},
        {name: "Thomas Jefferson", email: "tommyboy129@state.gov", company: "Department of State", count: "120", product: "carrier pigeon"},
        {name: "Ben Franklin", email: "bigben19281@poorrichards.com", company: "Poor Richard's Almanack", count: "38", product: "kite and key"},
        {name: "Alexander Bell", email: "ahoy@bell.com", company: "Bell Telephone Company", count: "24", product: "telephone"},
        {name: "Marie Curie", email: "m.curie@ens.fr", company: "École Normale Supérieure", count: "4", product: "pen & paper"},
        {name: "Alexandrina Victoria", email: "vicky@buckingham.co.uk", company: "House of Hanover", count: "81", product: "diplomats"},
        {name: "Mary Cassatt", email: "luvimpressionism@cassatt.com", company: "Cassatt Studios", count: "18", product: "oil on canvas"},
        {name: "Sophie Germain", email: "sophie@mathrulz.com", company: "Paris Academy of Sciences", count: "34", product: "smoke signals"},
        {name: "Eleanor Roosevelt", email: "elly@un.int", company: "United Nations", count: "193", product: "radio"}
    ];
    var candidate = candidates[Math.floor(Math.random() * candidates.length)];
    $("#name").attr('placeholder', candidate.name);
    $("#email").attr('placeholder', candidate.email);
    $("#company").attr('placeholder', candidate.company);
    $("#count").attr('placeholder', candidate.count);
    $("#product").attr('placeholder', candidate.product);
}

$(function () {
    $(".letter-form").ajaxForm({
        dataType: 'json', // This seems to be ignored. We still get back an xhr.
        beforeSubmit: function (arr, form, options) {
            $(".alert").hide();
            var has_email = false;
            $.each(arr, function (idx, elt) {
                if (elt.name === 'email' && elt.value.length) {
                    has_email = true;
                }
            });
            if (!has_email) {
                $("#error-missing-email").show();
                return false;
            }
            $("#beta-signup").attr('disabled', 'disabled').text("Sending...");
        },
        success: function (resp, statusText, xhr, form) {
            $("#success").show();
        },
        error: function (xhr, error_type, xhn) {
            $("#error").show();
        },
        complete: function (xhr, statusText) {
            $("#beta-signup").removeAttr('disabled').text("Sign up");
        }
    });

    populate_signup_form_placeholders();
});
