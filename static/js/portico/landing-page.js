// this will either smooth scroll to an anchor where the `name`
// is the same as the `scroll-to` reference, or to a px height
// (as specified like `scroll-to='0px'`).
var ScrollTo = function () {
    $("[scroll-to]").click(function () {
        var sel = $(this).attr("scroll-to");

        // if the `scroll-to` is a parse-able pixel value like `50px`,
        // then use that as the scrollTop, else assume it is a selector name
        // and find the `offsetTop`.
        var top = /\dpx/.test(sel) ?
                parseInt(sel, 10) :
                $("[name='" + sel + "']").offset().top;

        $("body").animate({ scrollTop: top + "px" }, 300);
    });
};

// these are events that are only to run on the integrations page.
// check if the page location is integrations.
var integration_events = function () {
    $("a.title")
        .addClass("show-integral")
        .prepend($("<span class='integral'>∫</span>"))
        .hover(function () {
            $(".integral").css("display", "inline");
            var width = $(".integral").width();
            $("a.title").css("left", -1 * width);
        },
        function () {
            $(".integral").css("display", "none");
                $("a.title").css("left", 0);
            }
        );

    var $lozenge_icon;
    var currentblock;
    var instructionbox = $("#integration-instruction-block");
    var hashes = $('.integration-instructions').map(function () {
        return this.id || null;
    }).get();


    var show_integration = function (hash) {
        // the version of the hash without the leading "#".
        var _hash = hash.replace(/^#/, "");

        if (hashes.indexOf(_hash) > -1) {
            $lozenge_icon = $(".integration-lozenges .integration-lozenge.integration-" + _hash).clone(true);
            currentblock = $(hash);
            instructionbox.children(".integration-lozenge").replaceWith($lozenge_icon);
            instructionbox.append($lozenge_icon, currentblock);

            $(".inner-content").removeClass("show");
            setTimeout(function () {
                instructionbox.hide();
                $(".integration-lozenges").addClass("hide");
                $(".portico-page-header.extra, .portico-large-text.extra, #integration-main-text").hide();

                instructionbox.append(currentblock);
                instructionbox.show();
                $("#integration-list-link").css("display", "block");

                $(".inner-content").addClass("show");
            }, 300);
            window.scrollTo(0,0);
        }
    };

    function update_hash() {
        var hash = document.location.hash;

        if (hash && hash !== '#hubot-integrations') {
            show_integration(window.location.hash);
        } else if (currentblock && $lozenge_icon) {
            $(".inner-content").removeClass("show");
            setTimeout(function () {
                $("#integration-list-link").css("display", "none");
                $(".integration-lozenges").removeClass("hide");
                $(".portico-page-header.extra, .portico-large-text.extra, #integration-main-text").show();
                instructionbox.hide();
                $lozenge_icon.remove();
                currentblock.appendTo("#integration-instructions-group");
                $(".inner-content").addClass("show");
                $('html, body').animate({scrollTop: ($(hash).offset() || { top: 0 }).top}, 'slow');
            }, 300);
        } else {
            $(".inner-content").addClass("show");
        }
    }

    window.onhashchange = update_hash;
    update_hash();
};

var events = function () {
    ScrollTo();

    $("a").click(function (e) {
        // if the pathname is different than what we are already on, run the
        // custom transition function.
        if (window.location.pathname !== this.pathname && !this.hasAttribute("download")) {
            e.preventDefault();
            $(".portico-landing").removeClass("show");
            setTimeout(function () {
                window.location.href = $(this).attr("href");
            }.bind(this), 500);
        }
    });

    // get the location url like `zulipchat.com/features/`, cut off the trailing
    // `/` and then split by `/` to get ["zulipchat.com", "features"], then
    // pop the last element to get the current section (eg. `features`).
    var location = window.location.pathname.replace(/\/#*$/, "").split(/\//).pop();

    $("[on-page='" + location + "']").addClass("active");

    $("body").click(function (e) {
        var $e = $(e.target);

        var should_close = !$e.is("ul, #hamburger") && $e.closest("ul, #hamburger").length === 0;

        // this means that it is in mobile sidebar mode.
        if ($("nav ul").height() === window.innerHeight && should_close) {
            $("nav ul").removeClass("show");
        }
    });

    $("#hamburger").click(function () {
        $("nav ul").addClass("show");
    });

    $(window).scroll(function () {
        if ($(document.activeElement).is(".price-box")) {
            document.activeElement.blur();
        }
    });

    (function () {
        var $pricing_overlay = $(".pricing-overlay");
        var $inline_overlay = $(".pricing-model:not(.pricing-overlay)");
        var $pricing_container = $(".pricing-overlay .pricing-container");
        var $info_box = $(".info-box");

        var $original;
        var $clone;
        var height;

        var calculate_position = {
            initial: function (top, left) {
                return ["transform", "translateX(" + (left - 50) + "px) translateY(" + (top - 50) + "px)"];
            },
            final: function (height) {
                return ["transform", "translateX(0px) translateY(" + (window.innerHeight - 100 - height) / 2 + "px)"];
            },
        };

        var reset = function () {
            $info_box.removeClass("show").css("transform", "translateY(300px)");
            $pricing_overlay.removeClass("active");
            $inline_overlay.removeClass("stick");
            if ($clone) {
                setTimeout(function () {
                    $clone.remove();
                }, 300);
            }
        };

        $("body").on("focus", ".price-box", function (e) {
            $original = $(e.target);
            var offset = $original.offset();
            height = $original.height();

            var top = offset.top - $("body").scrollTop() + 2;
            var left = offset.left + 2;

            if ($clone) {
                $clone.remove();
            }

            $clone = $original.blur().clone(true);
            // set the CSS initial position to match the inline position.

            var initial_position = calculate_position.initial(top, left);
            $clone.css.apply($clone, initial_position);
            $pricing_container.prepend($clone);

            // add an active class to make the overlay appear.
            $pricing_overlay.addClass("active");
            // add a stick class to the inline pricing model to make the :hover
            // transform stick.
            $inline_overlay.addClass("stick");
            // remove any old pricing information and append the clone.


            setTimeout(function () {
                $clone.css.apply($clone, calculate_position.final(height));
                setTimeout(function () {
                    $info_box.addClass("show");
                    $info_box.css({
                        transform: "translateY(" + (window.innerHeight - 100 - height) / 2 + "px)",
                        height: height + "px",
                    });
                }, 300);
            }, 300);
        });

        $(window).resize(function () {
            if ($pricing_overlay.hasClass("active")) {
                $clone.css.apply($clone, calculate_position.final(height));
                $info_box.css("transform", "translateY(" + (window.innerHeight - 100 - height) / 2 + "px)");
            }
        });

        $pricing_overlay.click(function (e) {
            if ($(e.target).is(".pricing-container, .pricing-overlay")) {
                reset();
            }
        });
    }());

    (function () {
        var $last = $(".details-box").eq(0).addClass("show");
        var $li = $("ul.sidebar li");
        var version;

        var nav_version = {
            Win: "windows",
            MacIntel: "mac",
            Linux: "linux",
            iP: "ios",
        };

        for (var x in nav_version) {
            if (navigator.platform.indexOf(x) !== -1) {
                $('li[data-name="' + nav_version[x] + '"]').click();
                version = nav_version[x];
                break;
            }
        }

        var switch_to_tab = function (elem) {
            var target = $(elem).data("name");
            var $el = $(".details-box[data-name='" + target + "']");

            // $li is a semi-global variable from the closure above.
            $li.removeClass("active");
            $(elem).addClass("active");

            $last.removeClass("show");
            $el.addClass("show");

            $last = $el;
        };

        // this is for the sidebar on the /apps/ page to trigger the correct info box.
        $li.click(function () {
            window.location.hash = $(this).data("name");
        });

        if (window.location.pathname === "/apps/") {
            var hash = function () {
                return window.location.hash.replace(/^#/, "");
            };

            switch_to_tab($("ul.sidebar li[data-name='" + (hash() || version || "windows") + "']"));

            window.onhashchange = function () {
                switch_to_tab($("ul.sidebar li[data-name='" + hash() + "']"));
            };
        }
    }());

    if (/\/integrations\/*/.test(window.location.pathname)) {
        integration_events();
    }
};

// run this callback when the page is determined to have loaded.
var load = function () {
    // show the .portico-landing when the document is loaded.
    setTimeout(function () {
        $(".portico-landing").addClass("show");
    }, 200);

    (function () {
        // switch the hero images once every 4 seconds.
        setInterval(function () {
            $("x-grad").toggleClass("orange-grad blue-grad");
        }, 4000);
    }());

    // display the `x-grad` element a second after load so that the slide up
    // transition on the .portico-landing is nice and smooth.
    setTimeout(function () {
        $("x-grad").addClass("show");
    }, 1000);

    // Set events.
    events();
};

if (document.readyState === "complete") {
    load();
} else {
    $(document).ready(load);
}
