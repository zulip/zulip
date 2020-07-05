const postcss = require('postcss');
const postcssrc = require('postcss-load-config');

const ctx = { parser: true, map: false, file: {
    extname: 'scss',
    basename: 'index.scss', // any name is fine.
    dirname: './',
}};

const dedent = (str) => {
    str = str.replace(/^\n/, "");
    const match = str.match(/^\s+/);
    return match ? str.replace(new RegExp("^" + match[0], "gm"), "") : str;
};

const assert_conversion = async (input, expected, ctx) => {
    const { plugins, options } = postcssrc.sync(ctx);
    options.from = ctx.basename;
    const output = await postcss(plugins).process(input, options);
    assert.equal(output.css, expected);
};

run_test('Add media query to night-mode', async () => {
    // We only apply this rule to specific files; manually set the name;
    ctx.file = {
        basename: 'night_mode.scss',
    };

    const input = `
        body.night-mode {
            a {
                color: dark;
            }
        }`;

    // The final CSS has some weird indentation, we don't care about it.
    const expected = `
        body.night-mode a {
                color: dark;
            }


        @media (prefers-color-scheme: dark) {
            body.color-scheme-automatic a {
                color: dark;
            }
        }`;

    await assert_conversion(dedent(input), dedent(expected), ctx);
});

run_test('Import dark theme for flatpickr', async () => {
    ctx.file = {
        extname: 'css',
        basename: 'dark.css',
        dirname: 'flatpickr/dist/themes',
    };

    const input = `
        a {
            color: dark;
        }`;

    // We should both wrap the initial CSS in night-mode class and
    // add the media query for prefers-color-scheme.
    const expected = `
        body.night-mode a {
            color: dark;
        }


        @media (prefers-color-scheme: dark) {
            body.color-scheme-automatic a {
            color: dark;
            }
        }`;

    await assert_conversion(dedent(input), dedent(expected), ctx);
});
