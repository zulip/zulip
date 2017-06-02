var events = function (meta) {
    // jQuery random events to make magic happen.
    (function () {
        $("#sidebar").on("click", ".ind-sidebar-component", function () {
            $('#main').animate({
                scrollTop: "+=" + ($(".component[data-name='" + this.dataset.name + "']").offset().top - 20)
            }, 500);

            $(".ind-sidebar-component").removeClass("selected");

            $(this).addClass("selected");
        });

        $("nav").click(function (e) {
            if (!T.isMobile && !$(e.target).is(".menu-burger")) {
                $("#main").animate({
                    scrollTop: 0
                }, 500);
            }
        });

        $("#main").scroll(function () {
            meta.ui.note.hide();
        });

        $("nav .menu-burger").click(function () {
            $("#sidebar").toggleClass("show");
            $(".components").toggleClass("dark");
        });

        $(".components").click(function () {
            $("#sidebar").removeClass("show");
            $(".components").removeClass("dark");
        });

        window.onbeforeunload = function () {
          $("#main").scrollTop();
          storage.set({ scrollTop: $("#main").scrollTop() - 20 });
        };
    }());
};