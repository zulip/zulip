We use the handlebars library to render HTML inside the browser.

Handlebars templates actually get compiled into JS functions that
in turn get called via a runtime library.

We install handlebars as a node module, and then we copy the runtime
to the static directory and add some copyright info.  The former files
reside in `node_modules/handlebars`.

In our installation we call `./tools/compile-handlebars-templates`
to build the file `static/templates/compiled.js`.  (Then in staging/prod,
that file also gets minified.)  For the runtime, in dev mode we serve
it from the static/third directory, and in prod we minify from the
static/third directory.

There are also some node unit tests that use handlebars, and all the
code that they use comes directly from `node_modules/handlebars`,
including the runtime.
