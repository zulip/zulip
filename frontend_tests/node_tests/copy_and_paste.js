global.stub_out_jquery();

set_global('page_params', {
    development: true,
});

var jsdom = require("jsdom");
global.document = jsdom.jsdom('<!DOCTYPE html><p>Hello world</p>');
var window = jsdom.jsdom().defaultView;
global.$ = require('jquery')(window);

zrequire('toMarkdown', 'node_modules/to-markdown/dist/to-markdown.js');
var copy_and_paste = zrequire('copy_and_paste');

(function test_paste_handler() {

    var input = '<meta http-equiv="content-type" content="text/html; charset=utf-8"><span style="color: rgb(34, 34, 34); font-family: arial, sans-serif; font-size: 12.8px; font-style: normal; font-variant-ligatures: normal; font-variant-caps: normal; font-weight: 400; letter-spacing: normal; orphans: 2; text-align: start; text-indent: 0px; text-transform: none; white-space: normal; widows: 2; word-spacing: 0px; -webkit-text-stroke-width: 0px; background-color: rgb(255, 255, 255); text-decoration-style: initial; text-decoration-color: initial;"><span> </span>love the<span> </span><b>Zulip</b><b> </b></span><b style="color: rgb(34, 34, 34); font-family: arial, sans-serif; font-size: 12.8px; font-style: normal; font-variant-ligatures: normal; font-variant-caps: normal; letter-spacing: normal; orphans: 2; text-align: start; text-indent: 0px; text-transform: none; white-space: normal; widows: 2; word-spacing: 0px; -webkit-text-stroke-width: 0px; background-color: rgb(255, 255, 255); text-decoration-style: initial; text-decoration-color: initial;">Organization</b><span style="color: rgb(34, 34, 34); font-family: arial, sans-serif; font-size: 12.8px; font-style: normal; font-variant-ligatures: normal; font-variant-caps: normal; font-weight: 400; letter-spacing: normal; orphans: 2; text-align: start; text-indent: 0px; text-transform: none; white-space: normal; widows: 2; word-spacing: 0px; -webkit-text-stroke-width: 0px; background-color: rgb(255, 255, 255); text-decoration-style: initial; text-decoration-color: initial;">.</span>';
    assert.equal(copy_and_paste.paste_handler_converter(input),
                 'love the  **Zulip****Organization**.');

    input = '<meta http-equiv="content-type" content="text/html; charset=utf-8"><span style="color: rgb(36, 41, 46); font-family: -apple-system, BlinkMacSystemFont, &quot;Segoe UI&quot;, Helvetica, Arial, sans-serif, &quot;Apple Color Emoji&quot;, &quot;Segoe UI Emoji&quot;, &quot;Segoe UI Symbol&quot;; font-size: 16px; font-style: normal; font-variant-ligatures: normal; font-variant-caps: normal; font-weight: 400; letter-spacing: normal; orphans: 2; text-align: start; text-indent: 0px; text-transform: none; white-space: normal; widows: 2; word-spacing: 0px; -webkit-text-stroke-width: 0px; background-color: rgb(255, 255, 255); text-decoration-style: initial; text-decoration-color: initial; display: inline !important; float: none;">The<span> </span></span><code style="box-sizing: border-box; font-family: SFMono-Regular, Consolas, &quot;Liberation Mono&quot;, Menlo, Courier, monospace; font-size: 13.6px; padding: 0.2em 0.4em; margin: 0px; background-color: rgba(27, 31, 35, 0.05); border-radius: 3px; color: rgb(36, 41, 46); font-style: normal; font-variant-ligatures: normal; font-variant-caps: normal; font-weight: 400; letter-spacing: normal; orphans: 2; text-align: start; text-indent: 0px; text-transform: none; white-space: normal; widows: 2; word-spacing: 0px; -webkit-text-stroke-width: 0px; text-decoration-style: initial; text-decoration-color: initial;">JSDOM</code><span style="color: rgb(36, 41, 46); font-family: -apple-system, BlinkMacSystemFont, &quot;Segoe UI&quot;, Helvetica, Arial, sans-serif, &quot;Apple Color Emoji&quot;, &quot;Segoe UI Emoji&quot;, &quot;Segoe UI Symbol&quot;; font-size: 16px; font-style: normal; font-variant-ligatures: normal; font-variant-caps: normal; font-weight: 400; letter-spacing: normal; orphans: 2; text-align: start; text-indent: 0px; text-transform: none; white-space: normal; widows: 2; word-spacing: 0px; -webkit-text-stroke-width: 0px; background-color: rgb(255, 255, 255); text-decoration-style: initial; text-decoration-color: initial; display: inline !important; float: none;"><span> </span>constructor</span>';
    assert.equal(copy_and_paste.paste_handler_converter(input),
                 'The  `JSDOM`  constructor');

    input = '<meta http-equiv="content-type" content="text/html; charset=utf-8"><a href="https://zulip.readthedocs.io/en/latest/subsystems/logging.html" target="_blank" title="https://zulip.readthedocs.io/en/latest/subsystems/logging.html" style="color: rgb(0, 136, 204); text-decoration: none; cursor: pointer; font-family: &quot;Source Sans Pro&quot;, &quot;Helvetica Neue&quot;, Helvetica, Arial, sans-serif; font-size: 14px; font-style: normal; font-variant-ligatures: normal; font-variant-caps: normal; font-weight: 400; letter-spacing: normal; orphans: 2; text-align: start; text-indent: 0px; text-transform: none; white-space: normal; widows: 2; word-spacing: 0px; -webkit-text-stroke-width: 0px; background-color: rgb(255, 255, 255);">https://zulip.readthedocs.io/en/latest/subsystems/logging.html</a>';
    assert.equal(copy_and_paste.paste_handler_converter(input),
                 'https://zulip.readthedocs.io/en/latest/subsystems/logging.html');

    input = '<meta http-equiv="content-type" content="text/html; charset=utf-8"><a class="reference external" href="https://zulip.readthedocs.io/en/latest/overview/contributing.html" style="box-sizing: border-box; color: rgb(155, 89, 182); text-decoration: none; cursor: pointer; outline: 0px; font-family: Lato, proxima-nova, &quot;Helvetica Neue&quot;, Arial, sans-serif; font-size: 16px; font-style: normal; font-variant-ligatures: normal; font-variant-caps: normal; font-weight: 400; letter-spacing: normal; orphans: 2; text-align: start; text-indent: 0px; text-transform: none; white-space: normal; widows: 2; word-spacing: 0px; -webkit-text-stroke-width: 0px; background-color: rgb(252, 252, 252);">Contributing to Zulip</a>';
    assert.equal(copy_and_paste.paste_handler_converter(input),
                 '[Contributing to Zulip](https://zulip.readthedocs.io/en/latest/overview/contributing.html)');

    input = '<meta http-equiv="content-type" content="text/html; charset=utf-8"><span style="color: rgb(0, 0, 0); font-family: &quot;Helvetica Neue&quot;, &quot;Segoe UI&quot;, Helvetica, Arial, sans-serif; font-size: 13px; font-style: normal; font-variant-ligatures: normal; font-variant-caps: normal; font-weight: 400; letter-spacing: normal; orphans: 2; text-align: start; text-indent: 0px; text-transform: none; white-space: normal; widows: 2; word-spacing: 0px; -webkit-text-stroke-width: 0px; background-color: rgb(255, 255, 255); text-decoration-style: initial; text-decoration-color: initial; display: inline !important; float: none;">1. text</span>';
    assert.equal(copy_and_paste.paste_handler_converter(input),
                 '1. text');

    input = '<meta http-equiv="content-type" content="text/html; charset=utf-8"><h1 style="box-sizing: border-box; font-size: 2em; margin-top: 0px !important; margin-right: 0px; margin-bottom: 16px; margin-left: 0px; font-weight: 600; line-height: 1.25; padding-bottom: 0.3em; border-bottom: 1px solid rgb(234, 236, 239); color: rgb(36, 41, 46); font-family: -apple-system, BlinkMacSystemFont, &quot;Segoe UI&quot;, Helvetica, Arial, sans-serif, &quot;Apple Color Emoji&quot;, &quot;Segoe UI Emoji&quot;, &quot;Segoe UI Symbol&quot;; font-style: normal; font-variant-ligatures: normal; font-variant-caps: normal; letter-spacing: normal; orphans: 2; text-align: start; text-indent: 0px; text-transform: none; white-space: normal; widows: 2; word-spacing: 0px; -webkit-text-stroke-width: 0px; text-decoration-style: initial; text-decoration-color: initial;">Zulip overview</h1>';
    assert.equal(copy_and_paste.paste_handler_converter(input),
                 'Zulip overview');

    input = '<meta http-equiv="content-type" content="text/html; charset=utf-8"><i style="box-sizing: inherit; color: rgb(0, 0, 0); font-family: Verdana, sans-serif; font-size: 15px; font-variant-ligatures: normal; font-variant-caps: normal; font-weight: 400; letter-spacing: normal; orphans: 2; text-align: start; text-indent: 0px; text-transform: none; white-space: normal; widows: 2; word-spacing: 0px; -webkit-text-stroke-width: 0px; background-color: rgb(255, 255, 255); text-decoration-style: initial; text-decoration-color: initial;">This text is italic</i>';
    assert.equal(copy_and_paste.paste_handler_converter(input),
                 '*This text is italic*');
}());
