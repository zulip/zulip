import fuzzysearch from 'fuzzysearch';
import blueslip from './../blueslip';

const ELECTRON_APP_VERSION = "1.2.0-beta";
const ELECTRON_APP_URL_LINUX = "https://github.com/zulip/zulip-electron/releases/download/v" + ELECTRON_APP_VERSION + "/Zulip-" + ELECTRON_APP_VERSION + "-x86_64.AppImage";
const ELECTRON_APP_URL_MAC = "https://github.com/zulip/zulip-electron/releases/download/v" + ELECTRON_APP_VERSION + "/Zulip-" + ELECTRON_APP_VERSION + ".dmg";
const ELECTRON_APP_URL_WINDOWS = "https://github.com/zulip/zulip-electron/releases/download/v" + ELECTRON_APP_VERSION + "/Zulip-Web-Setup-" + ELECTRON_APP_VERSION + ".exe";

// these constants are populated immediately with data from the DOM on page load
// name -> display name
var INTEGRATIONS = {};
var CATEGORIES = {};

function load_data() {
    $('.integration-lozenge').toArray().forEach(function (integration) {
        var name = $(integration).data('name');
        var display_name = $(integration).find('.integration-name').text().trim();

        if (display_name && name) {
            INTEGRATIONS[name] = display_name;
        }
    });

    $('.integration-category').toArray().forEach(function (category) {
        var name = $(category).data('category');
        var display_name = $(category).text().trim();

        if (display_name && name) {
            CATEGORIES[name] = display_name;
        }
    });
}

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

function path_parts() {
    return window.location.pathname.split('/').filter(function (chunk) {
        return chunk !== '';
    });
}

var INITIAL_STATE = {
    category: 'all',
    integration: null,
    query: '',
};

var state = Object.assign({}, INITIAL_STATE);

function update_path() {
    var next_path;
    if (state.integration) {
        next_path = $('.integration-lozenge[data-name="' + state.integration + '"]')
            .closest('a').attr('href');
    } else if (state.category) {
        next_path = $('.integration-category[data-category="' + state.category + '"]')
            .closest('a').attr('href');
    } else {
        next_path = '/';
    }

    window.history.pushState(state, '', next_path);
}

function update_categories() {
    $('.integration-lozenges').css('opacity', 0);

    $('.integration-category').removeClass('selected');
    $('[data-category="' + state.category + '"]').addClass('selected');

    var $dropdown_label = $('.integration-categories-dropdown .dropdown-category-label');
    var $dropdown_icon = $('.integration-categories-dropdown i');
    if (state.category === INITIAL_STATE.category) {
        $dropdown_label.text(i18n.t('Filter by category'));
    } else {
        $dropdown_label.text(CATEGORIES[state.category]);
        $dropdown_icon
            .removeClass('icon-vector-angle-right')
            .addClass('icon-vector-angle-down');
    }

    $('.integration-lozenges').animate(
        { opacity: 1 },
        { duration: 400 }
    );
}

var update_integrations = _.debounce(function () {
    var max_scrollY = window.scrollY;

    var integrations = $('.integration-lozenges').children().toArray();
    integrations.forEach(function (integration) {
        var $integration = $(integration).find('.integration-lozenge');
        var $integration_category = $integration.find('.integration-category');

        if (state.category !== 'all') {
            $integration_category.css('display', 'none');
            $integration.addClass('without-category');
        } else {
            $integration_category.css('display', '');
            $integration.removeClass('without-category');
        }

        if (!$integration.hasClass('integration-create-your-own')) {
            var display =
                fuzzysearch(state.query, $integration.data('name').toLowerCase()) &&
                ($integration.data('categories').indexOf(CATEGORIES[state.category]) !== -1 ||
                 state.category === 'all');

            if (display) {
                $integration.css('display', 'inline-block');
            } else {
                $integration.css('display', 'none');
            }
        }

        document.body.scrollTop = Math.min(window.scrollY, max_scrollY);
    });
}, 50);

function hide_catalog_show_integration() {
    var $lozenge_icon = $(".integration-lozenge.integration-" + state.integration).clone(false);
    $lozenge_icon.removeClass('legacy');

    var categories = $('.integration-' + state.integration).data('categories')
        .slice(1, -1)
        .split(',')
        .map(function (category) {
            return category.trim().slice(1, -1);
        });

    function show_integration(doc) {
        $('#integration-instructions-group .name').text(INTEGRATIONS[state.integration]);
        $('#integration-instructions-group .categories .integration-category').remove();
        categories.forEach(function (category) {
            var link;
            Object.keys(CATEGORIES).forEach(function (name) {
                if (CATEGORIES[name] === category) {
                    link = name;
                }
            });
            var category_el = $('<a></a>')
                .attr('href', '/integrations/' + link)
                .append('<h3 class="integration-category"></h3>');
            category_el.find('.integration-category')
                .attr('data-category', link)
                .text(category);
            $('#integration-instructions-group .categories').append(category_el);
        });
        $('#integration-instructions-group').css({
            opacity: 0,
            display: 'block',
        });
        $('.integration-instructions').css('display', 'none');
        $('#' + state.integration + '.integration-instructions .help-content').html(doc);
        $('#integration-instruction-block .integration-lozenge').remove();
        $("#integration-instruction-block")
            .append($lozenge_icon)
            .css('display', 'block');
        $('.integration-instructions#' + state.integration).css('display', 'block');
        $("#integration-list-link").css('display', 'block');

        $("html, body").animate(
            { scrollTop: 0 },
            { duration: 200 }
        );
        $('#integration-instructions-group').animate(
            { opacity: 1 },
            { duration: 300 }
        );
    }

    function hide_catalog(doc) {
        $(".integration-categories-dropdown").css('display', 'none');
        $(".integrations .catalog").addClass('hide');
        $(".extra, #integration-main-text, #integration-search").css("display", "none");

        show_integration(doc);
    }

    $.get({
        url: '/integrations/doc-html/' + state.integration,
        dataType: 'html',
        success: hide_catalog,
        error: function (err) {
            blueslip.error("Integration documentation for '" + state.integration + "' not found.", err);
        },
    });
}

function hide_integration_show_catalog() {
    function show_catalog() {
        $("html, body").animate(
            { scrollTop: 0 },
            { duration: 200 }
        );

        $(".integration-categories-dropdown").css('display', '');
        $(".integrations .catalog").removeClass('hide');
        $(".extra, #integration-main-text, #integration-search").css("display", "block");
    }

    function hide_integration() {
        $('#integration-instruction-block').css('display', 'none');
        $('#integration-instructions-group').css('display', 'none');
        $('.inner-content').css({ padding: '' });
        $("#integration-instruction-block .integration-lozenge").remove();
        show_catalog();
    }

    hide_integration();
}

function get_state_from_path() {
    var result = Object.assign({}, INITIAL_STATE);
    result.query = state.query;

    var parts = path_parts();
    if (parts[1] === 'doc' && INTEGRATIONS[parts[2]]) {
        result.integration = parts[2];
    } else if (CATEGORIES[parts[1]]) {
        result.category = parts[1];
    }

    return result;
}

function render(next_state) {
    var previous_state = Object.assign({}, state);
    state = next_state;

    if (previous_state.integration !== next_state.integration) {
        if (next_state.integration !== null) {
            hide_catalog_show_integration();
        } else {
            hide_integration_show_catalog();
        }
    }

    if (previous_state.category !== next_state.category) {
        update_categories();
        update_integrations();
    }

    if (previous_state.query !== next_state.query) {
        update_integrations();
    }
}

function dispatch(action, payload) {
    switch (action) {
        case 'CHANGE_CATEGORY':
            render(Object.assign({}, state, {
                category: payload.category,
            }));
            update_path();
            break;

        case 'SHOW_INTEGRATION':
            render(Object.assign({}, state, {
                integration: payload.integration,
            }));
            update_path();
            break;

        case 'HIDE_INTEGRATION':
            render(Object.assign({}, state, {
                integration: null,
            }));
            update_path();
            break;

        case 'SHOW_CATEGORY':
            render(Object.assign({}, state, {
                integration: null,
                category: payload.category,
            }));
            update_path();
            break;

        case 'UPDATE_QUERY':
            render(Object.assign({}, state, {
                query: payload.query,
            }));
            break;

        case 'LOAD_PATH':
            render(get_state_from_path());
            break;

        default:
            blueslip.error('Invalid action dispatched on /integrations.');
            break;
    }
}

var integration_events = function () {
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

    $('#integration-search input[type="text"]').keypress(function (e) {
        var integrations = $('.integration-lozenges').children().toArray();
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

    $('.integration-categories-dropdown .dropdown-toggle').click(function () {
        var $dropdown_list = $('.integration-categories-dropdown .dropdown-list');
        $dropdown_list.toggle();

        if ($dropdown_list.css('display') === 'none' &&
            state.category === INITIAL_STATE.category) {
            $('.integration-categories-dropdown i')
                .removeClass('icon-vector-angle-down')
                .addClass('icon-vector-angle-right');
        } else {
            $('.integration-categories-dropdown i')
                .removeClass('icon-vector-angle-right')
                .addClass('icon-vector-angle-down');
        }
    });

    $('.integration-instruction-block').on('click', 'a .integration-category', function (e) {
        var category = $(e.target).data('category');
        dispatch('SHOW_CATEGORY', { category: category });
        return false;
    });

    $('.integrations a .integration-category').on('click', function (e) {
        var category = $(e.target).data('category');
        dispatch('CHANGE_CATEGORY', { category: category });
        return false;
    });

    $('.integrations a .integration-lozenge').on('click', function (e) {
        if (!$(e.target).closest('.integration-lozenge').hasClass('integration-create-your-own')) {
            var integration = $(e.target).closest('.integration-lozenge').data('name');
            dispatch('SHOW_INTEGRATION', { integration: integration });
            return false;
        }
    });

    $('a#integration-list-link span, a#integration-list-link i').on('click', function () {
        dispatch('HIDE_INTEGRATION');
        return false;
    });

    $(".integrations .searchbar input[type='text']").on('input', function (e) {
        dispatch('UPDATE_QUERY', { query : e.target.value.toLowerCase() });
    });

    $(window).scroll(function () {
        if (document.body.scrollTop > 330) {
            $('.integration-categories-sidebar').addClass('sticky');
        } else {
             $('.integration-categories-sidebar').removeClass('sticky');
        }
    });

    $(window).on('resize', function () {
        adjust_font_sizing();
    });

    $(window).on('popstate', function () {
        if (window.location.pathname.startsWith('/integrations')) {
            dispatch('LOAD_PATH');
        } else {
            window.location = window.location.href;
        }
    });
};

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

    var version;

    function get_version_from_path() {
        var result;
        var parts = path_parts();

        Object.keys(info).forEach(function (version) {
            if (parts.includes(version)) {
                result = version;
            }
        });

        // display Mac app by default
        result = result || 'mac';
        return result;
    }

    function get_path_from_version() {
        return '/apps/' + version;
    }

    function update_path() {
        var next_path = get_path_from_version();
        history.pushState(version, '', next_path);
    }

    var update_page = function () {
        var version_info = info[version];
        $(".info .platform").text(version_info.alt);
        $(".info .description").text(version_info.description);
        $(".info .link").attr("href", version_info.link);
        $(".image img").attr("src", version_info.image);
    };

    $(window).on('popstate', function () {
        version = get_version_from_path();
        update_page();
        $("body").animate({ scrollTop: 0 }, 200);
    });

    $(".apps a .icon").click(function (e) {
        var next_version = $(e.target).closest('a')
            .attr('href')
            .replace('/apps/', '');
        version = next_version;

        update_path();
        update_page();
        $("body").animate({ scrollTop: 0 }, 200);

        return false;
    });

    // init
    version = get_version_from_path();
    history.replaceState(version, '', get_path_from_version());
    update_page();
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

    if (path_parts().includes("apps")) {
        apps_events();
    }

    if (path_parts().includes('integrations')) {
        integration_events();
        load_data();
        dispatch('LOAD_PATH');
    }

    if (path_parts().includes('hello')) {
        hello_events();
    }
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
