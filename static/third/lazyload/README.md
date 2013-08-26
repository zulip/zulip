LazyLoad
========

LazyLoad is a tiny (only 966 bytes minified and gzipped), dependency-free
JavaScript utility that makes it super easy to load external JavaScript and CSS
files on demand.

Whenever possible, LazyLoad will automatically load resources in parallel while
ensuring execution order when you specify an array of URLs to load. In browsers
that don't preserve the execution order of asynchronously-loaded scripts,
LazyLoad will safely load the scripts sequentially.

Use LazyLoad when you need a small, fast, safe dynamic JS or CSS loader, but
don't need the overhead of dependency management or other extra functionality
that larger script loaders provide.

Downloads
---------

  * [lazyload.js](https://github.com/rgrove/lazyload/raw/master/lazyload.js) (full source)

Usage
-----

Using LazyLoad is simple. Just call the appropriate method -- `css()` to load
CSS, `js()` to load JavaScript -- and pass in a URL or array of URLs to load.
You can also provide a callback function if you'd like to be notified when the
resources have finished loading, as well as an argument to pass to the callback
and a context in which to execute the callback.

```js
// Load a single JavaScript file and execute a callback when it finishes.
LazyLoad.js('http://example.com/foo.js', function () {
  alert('foo.js has been loaded');
});

// Load multiple JS files and execute a callback when they've all finished.
LazyLoad.js(['foo.js', 'bar.js', 'baz.js'], function () {
  alert('all files have been loaded');
});

// Load a CSS file and pass an argument to the callback function.
LazyLoad.css('foo.css', function (arg) {
  alert(arg);
}, 'foo.css has been loaded');

// Load a CSS file and execute the callback in a different scope.
LazyLoad.css('foo.css', function () {
  alert(this.foo); // displays 'bar'
}, null, {foo: 'bar'});
```

Supported Browsers
------------------

  * Firefox 2+
  * Google Chrome
  * Internet Explorer 6+
  * Opera 9+
  * Safari 3+
  * Mobile Safari
  * Android

Other browsers may work, but haven't been tested. It's a safe bet that anything
based on a recent version of Gecko or WebKit will probably work.

Caveats
-------

All browsers support parallel loading of CSS. However, only Firefox and Opera
currently support parallel script loading while preserving execution order. To
ensure that scripts are always executed in the correct order, LazyLoad will load
all scripts sequentially in browsers other than Firefox and Opera. Hopefully
other browsers will improve their parallel script loading behavior soon.

License
-------

Copyright (c) 2011 Ryan Grove (ryan@wonko.com).
All rights reserved.
 
Permission is hereby granted, free of charge, to any person obtaining a copy of
this software and associated documentation files (the 'Software'), to deal in
the Software without restriction, including without limitation the rights to
use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
the Software, and to permit persons to whom the Software is furnished to do so,
subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED 'AS IS', WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
