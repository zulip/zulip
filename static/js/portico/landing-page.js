import fuzzysearch from 'fuzzysearch';
import blueslip from './../blueslip';

const ELECTRON_APP_VERSION = "1.2.0-beta";
const ELECTRON_APP_URL_LINUX = "https://github.com/zulip/zulip-electron/releases/download/v" + ELECTRON_APP_VERSION + "/Zulip-" + ELECTRON_APP_VERSION + "-x86_64.AppImage";
const ELECTRON_APP_URL_MAC = "https://github.com/zulip/zulip-electron/releases/download/v" + ELECTRON_APP_VERSION + "/Zulip-" + ELECTRON_APP_VERSION + ".dmg";
const ELECTRON_APP_URL_WINDOWS = "https://github.com/zulip/zulip-electron/releases/download/v" + ELECTRON_APP_VERSION + "/Zulip-Web-Setup-" + ELECTRON_APP_VERSION + ".exe";

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

var detectPath = function (pathname) {
    var match = (pathname || window.location.pathname).match(/(\/\w+)?\/(.+)\//);
    if (match !== null) {
        return match[2];
    }
};

// these are events that are only to run on the integrations page.
// check if the page location is integrations.
var integration_events = function () {
    var integrations = $('.integration-lozenges').children().toArray();
    var scroll_top = 0;

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

    function adjust_font_sizing() {
        $('.integration-lozenge').toArray().forEach(function (integration) {
            var $integration_name = $(integration).find('.integration-name');
            var $integration_category = $(integration).find('.integration-category');

            // if the text has wrapped to two lines, decrease font-size
            if ($integration_name.height() > 30) {
                $integration_name.css('font-size', '1em');
                if ($integration_name.height() > 30) {
                     $integration_name.css('font-size', '.95em');
                }
            }

            if ($integration_category.height() > 30) {
                $integration_category.css('font-size', '.8em');
                if ($integration_category.height() > 30) {
                    $integration_category.css('font-size', '.75em');
                }
            }
        });
    }

    adjust_font_sizing();
    $(window).resize(adjust_font_sizing);

    var $lozenge_icon;
    var currentblock;
    var instructionbox = $("#integration-instruction-block");
    var hashes = $('.integration-instructions').map(function () {
        return this.id || null;
    }).get();

    var show_integration = function (hash) {
        // the version of the hash without the leading "#".
        var _hash = hash.replace(/^#/, "");
        var integration_name = _hash;

        $.get({
            url: '/integrations/doc/' + integration_name,
            dataType: 'html',
            success: function (doc) {
                $('#' + integration_name + '.integration-instructions .help-content').html(doc);
            },
            error: function (err) {
                blueslip.error("Integration documentation for '" + integration_name + "' not found.", err);
            },
        });

        // clear out the integrations instructions that may exist in the instruction
        // block from a previous hash.
        $("#integration-instruction-block .integration-instructions")
            .appendTo("#integration-instructions-group");

        if (hashes.indexOf(_hash) > -1) {
            $lozenge_icon = $(".integration-lozenges .integration-lozenge.integration-" + _hash).clone(true);
            currentblock = $(hash);
            instructionbox.hide().children(".integration-lozenge").replaceWith($lozenge_icon);
            instructionbox.append($lozenge_icon);

            $(".inner-content").removeClass("show");
            setTimeout(function () {
                instructionbox.hide();
                $(".integration-categories-dropdown").css('display', 'none');
                $(".integrations .catalog").addClass('hide');
                $(".extra, #integration-main-text, #integration-search").css("display", "none");

                instructionbox.append(currentblock);
                instructionbox.show();
                $("#integration-list-link").css("display", "block");

                $(".inner-content").addClass("show");
            }, 300);

            $("html, body").animate({ scrollTop: 0 }, 200);
        }
    };

    function update_hash() {
        var hash = window.location.hash;

        if (hash && hash !== '#' && hash !== '#hubot-integrations') {
            scroll_top = $("body").scrollTop();
            show_integration(window.location.hash);
        } else if (currentblock && $lozenge_icon) {
            $(".inner-content").removeClass("show");
            setTimeout(function () {
                $("#integration-list-link").css("display", "none");
                $(".extra, #integration-main-text, #integration-search").show();
                instructionbox.hide();
                $lozenge_icon.remove();
                currentblock.appendTo("#integration-instructions-group");

                $(".inner-content").addClass("show");
                $(".integration-categories-dropdown").css('display', '');
                $(".integrations .catalog").removeClass('hide');

                $('html, body').animate({ scrollTop: scroll_top }, 0);
            }, 300);
        } else {
            $(".inner-content").addClass("show");
            $(".integration-categories-dropdown").removeClass('hide');
            $(".integrations .catalog").removeClass('hide');
        }

        adjust_font_sizing();
    }

    window.onhashchange = update_hash;
    update_hash();

    // this needs to happen because when you link to "#" it will scroll to the
    // top of the page.
    $("#integration-list-link").click(function (e) {
        var scroll_height = $("body").scrollTop();
        window.location.hash = "#";
        $("body").scrollTop(scroll_height);

        e.preventDefault();
    });

    $('#integration-search input[type="text"]').keypress(function (e) {
        if (e.which === 13 && e.target.value !== '') {
            for (var i = 0; i < integrations.length; i += 1) {
                var integration = $(integrations[i]).find('.integration-lozenge');

                if ($(integration).css('display') !== 'none') {
                    $(integration).closest('a')[0].click();
                    break;
                }
            }
        }
    });

    $(window).scroll(function () {
         if (document.body.scrollTop > 330) {
             $('.integration-categories-sidebar').addClass('sticky');
         } else {
             $('.integration-categories-sidebar').removeClass('sticky');
        }
    });
};


function integration_search() {
    var integrations = $('.integration-lozenges').children().toArray();
    var current_category = 'All';
    var current_query = '';

    function update_categories() {
        $('.integration-category').removeClass('selected');
        $('[data-category="' + current_category + '"]').addClass('selected');
    }

    var update_integrations = _.debounce(function () {
        integrations.forEach(function (integration) {
            var $integration = $(integration).find('.integration-lozenge');
            var $integration_category = $integration.find('.integration-category');

            if (current_category !== 'All') {
                $integration_category.css('display', 'none');
                $integration.addClass('without-category');
            } else {
                $integration_category.css('display', '');
                $integration.removeClass('without-category');
            }

            if (!$integration.hasClass('integration-create-your-own')) {
                var display =
                    fuzzysearch(current_query, $integration.data('name').toLowerCase()) &&
                    ($integration.data('categories').indexOf(current_category) !== -1 ||
                     current_category === 'All');

                if (display) {
                    $integration.css('display', 'inline-block');
                } else {
                    $integration.css('display', 'none');
                }
            }
        });
    }, 50);

    function change_category(category) {
        $('.integration-lozenges').css('opacity', 0);

        current_category = category;
        update_categories();
        update_integrations();

        $('.integration-lozenges').animate(
            { opacity: 1 },
            { duration: 400 }
        );
    }

    function run_search(query) {
        current_query = query.toLowerCase();
        update_integrations();
    }

    $('.integrations .integration-category').on('click', function (e) {
        var category = $(e.target).data('category');

        if (category !== current_category) {
            change_category(category);
        }
    });

    $(".integrations .searchbar input[type='text']").on('input', function (e) {
        run_search(e.target.value);
    });
}


var hello_events = function () {
    var counter = 0;
    $(window).scroll(function () {
        if (counter % 2 === 0) {
            $(".screen.hero-screen .message-feed").css("transform", "translateY(-" + $(this).scrollTop() / 5 + "px)");
        }
        counter += 1;
    });

    $(".footer").addClass("hello");
};

var apps_events = function () {
    var version;
    var info = {
        windows: {
            image: "/static/images/landing-page/microsoft.png",
            alt: "Windows",
            description: "Zulip for Windows is even better than Zulip on the web, with a cleaner look, tray integration, native notifications, and support for multiple Zulip accounts.",
            link: ELECTRON_APP_URL_WINDOWS,
        },
        mac: {
            image: "/static/images/landing-page/macbook.png",
            alt: "MacOS",
            description: "Zulip on MacOS is even better than Zulip on the web, with a cleaner look, tray integration, native notifications, and support for multiple Zulip accounts.",
            link: ELECTRON_APP_URL_MAC,
        },
        android: {
            image: "/static/images/app-screenshots/zulip-android.png",
            alt: "Android",
            description: "Zulip's native Android app makes it easy to keep up while on the go.",
            link: "https://play.google.com/store/apps/details?id=com.zulip.android",
        },
        ios: {
            image: "/static/images/app-screenshots/zulip-iphone-rough.png",
            alt: "iOS",
            description: "Zulip's native iOS app makes it easy to keep up while on the go.",
            link: "https://itunes.apple.com/us/app/zulip/id1203036395",
        },
        linux: {
            image: "/static/images/landing-page/ubuntu.png",
            alt: "Linux",
            description: "Zulip on the Linux desktop is even better than Zulip on the web, with a cleaner look, tray integration, native notifications, and support for multiple Zulip accounts.",
            link: ELECTRON_APP_URL_LINUX,
        },
    };

    var nav_version = {
        Win: "windows",
        MacIntel: "mac",
        Linux: "linux",
        iP: "ios",
    };

    // if the hash is not a valid section, then identify it.
    version = window.location.hash.replace(/^#/, "");

    if (info[version]) {
        window.location.hash = version;
    } else {
        for (var x in nav_version) {
            if (navigator.platform.indexOf(x) !== -1) {
                window.location.hash = nav_version[x];
                version = nav_version[x];
                break;
            }
        }

        if (!version || !info[version]) {
            version = "mac";
        }

        window.location.hash = version;
    }

    var update_version = function (version) {
        var version_info = info[version];
        $(".info .platform").text(version_info.alt);
        $(".info .description").text(version_info.description);
        $(".info .link").attr("href", version_info.link);
        $(".image img").attr("src", version_info.image);
    };


    window.onhashchange = function () {
        update_version(window.location.hash.substr(1));
    };

    update_version(version);

    $(".apps > .icon").click(function () {
        $("body").animate({ scrollTop: 0 }, 200);
    });
};

var events = function () {
    ScrollTo();

    $("a").click(function (e) {
        // if the pathname is different than what we are already on, run the
        // custom transition function.
        if (window.location.pathname !== this.pathname && !this.hasAttribute("download") &&
            !/no-action/.test(this.className)) {
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


        if ($e.is("nav ul .exit")) {
            $("nav ul").removeClass("show");
        }
    });

    $(".hamburger").click(function () {
        $("nav ul").addClass("show");
    });

    if (detectPath() === "apps") {
        apps_events();
    }

    if (detectPath() === "integrations") {
        integration_events();
        integration_search();
    }

    if (detectPath() === "hello") {
        hello_events();
    }

    $('.integration-categories-dropdown .dropdown-toggle').click(function () {
        var $dropdown_list = $('.integration-categories-dropdown .dropdown-list');
        $dropdown_list.toggle();

        var $dropdown_icon = $('.integration-categories-dropdown i');
        if ($dropdown_list.css('display') === 'none') {
            $dropdown_icon
                .removeClass('icon-vector-angle-down')
                .addClass('icon-vector-angle-right');
        } else {
            $dropdown_icon
                .removeClass('icon-vector-angle-right')
                .addClass('icon-vector-angle-down');
        }
    });
};


// run this callback when the page is determined to have loaded.
var load = function () {
    // show the .portico-landing when the document is loaded.
    setTimeout(function () {
        $(".portico-landing").addClass("show");
    }, 200);

    // display the `x-grad` element a second after load so that the slide up
    // transition on the .portico-landing is nice and smooth.
    setTimeout(function () {
        $("x-grad").addClass("show");
    }, 1000);

    // Set up events / categories / search
    events();
};

if (document.readyState === "complete") {
    load();
} else {
    $(document).ready(load);
}
