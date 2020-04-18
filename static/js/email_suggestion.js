/* eslint-disable */
const email = jQuery('#email');
const hint = jQuery('#hint');
(function ($) {
    email.on('keydown', function (e) {
        if (e.which === 13) {
            e.preventDefault();
        }
    });
    let suggestions;
    email.on('blur', function () {
        hint.css('display', 'none').empty();
        $(this).mailcheck({
            suggested: function (element, suggestion) {
                if (!hint.html()) {
                    let string = "Suggested email: ";
                    alert("There seems to be mistyped email address. Have a look at it again.");
                    suggestion = suggestion.address + "@" + suggestion.domain ;
                    hint.text(string + suggestion).fadeIn(150);
                    suggestions = suggestion;
                } else {
                    jQuery(".address").text(suggestion.address);
                    jQuery(".domain").text(suggestion.domain);
                }
            },
        });
    });
    hint.on('click', function () {
        email.val(suggestions);
        hint.fadeOut(200, function () {
            $(this).empty();
        });
        return false;
    });
}(jQuery));
