$(function () {
    $('.portico-header a .logout').on('click', function () {
        $('#logout_form').submit();
        return false;
    });

    $("body").click(function (e) {
        var $this = $(e.target);

        if ($this.is(".dropdown .header-realm-icon") && !$(".dropdown").hasClass("show")) {
            $(".dropdown").addClass("show");
        } else if (!$this.is(".dropdown ul") && $this.closest(".dropdown ul").length === 0) {
            $(".dropdown").removeClass("show");
        }
    });
});
