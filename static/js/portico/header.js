$(function () {
    $('.portico-header a .logout').on('click', function () {
        $('#logout_form').submit();
        return false;
    });

    $("body").click(function (e) {
        var $this = $(e.target);

        if ($this.is(".dropdown") || $this.closest(".dropdown").length) {
            $(".dropdown").addClass("show");
        } else {
            $(".dropdown").removeClass("show");
        }
    });
});
