set_global('document', 'document-stub');
set_global('$', global.make_zjquery());

var boy_code = '1f466';
var girl_code = '1f467';

set_global('emoji_codes', {
    emoji_catalog: {
        People: [
            boy_code,
            girl_code,
        ],
    },
});

set_global('emoji', {
    emojis: [
        {
            emoji_name: 'boy',
            codepoint: boy_code,
        },
        {
            emoji_name: 'girl',
            codepoint: girl_code,
        },
    ],
    realm_emojis:  {
        custom1: {
            emoji_url: '/custom1',
        },
    },
});

var ep = require('js/emoji_picker.js');

var handlers = {};

(function () {
    $(document).on = function (event, selector, f) {
        if (event === 'input' && selector === '.emoji-popover-filter') {
            handlers.filter_emojis = f;
        }
    };

    ep.register_click_handlers();
}());


(function verify_catalog_data() {
    // The catalog gets created as part of module loading.

    var catalog = ep.get_complete_catalog();

    // console.info(catalog[0].emojis);

    assert.deepEqual(
        catalog,
        [
            {
                name: 'People',
                icon: 'fa-smile-o',
                emojis: [
                    {
                        name: 'boy',
                        is_realm_emoji: false,
                        css_class: boy_code,
                        has_reacted: false,
                    },
                    {
                        name: 'girl',
                        is_realm_emoji: false,
                        css_class: girl_code,
                        has_reacted: false,
                    },
                ],
            },
            null,
            null,
            null,
            null,
            null,
            null,
            {
                name: 'Custom',
                icon: 'fa-thumbs-o-up',
                emojis: [
                    {
                        name: 'custom1',
                        is_realm_emoji: true,
                        url: '/custom1',
                        has_reacted: false,
                    },
                ],
            },
        ]
    );
}());

(function test_filtering() {
    $(".emoji-search-results-container").is = function (selector) {
        assert.equal(selector, ':visible');
        return true;
    };

    // TODO: Fix how we filter emojis so it's easier to test.
    // handlers.filter_emojis();
}());
