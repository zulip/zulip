var cacheName = "{{ version }}";
{{ files | safe }}; // eslint-disable-line

// add globals specific to sw (fetch is not sw specific)
// but will be avalible in browsers that support sw's
/* global fetch, addEventListener, skipWaiting */

addEventListener('install', function(event) {
  // skip the waiting time for new service worker
  // to be installed install it as soon as possible (after reload)
  // since new versions are not pushed very often and once pushed
  // we don't want any delay on user side.
  // and in production it should reflect changes as
  // soon as possible rather than when users closes all tab (default behavior)
  skipWaiting();

  // whenever a version is bumped new files will be added
  // and when reload happens new files are served from the
  // cache
  event.waitUntil(
    caches.open(cacheName)
    .then(function (cache) {
      cache.addAll(cacheFiles);
    })
    .catch(function( error) {
      // this occurs if file cannot be fetched or
      // when new changes are made we need to log out
      // the error so we know whats going on
      console.error(error);
    })
  );
});

// this function is called when servieWorker is activated
// and it removes the old cache so it serves up new fresh files
function removeOldCache(cacheList) {
  return Promise.all(cacheList.map(function (cache) {
    if (cache !== cacheName) {
      caches.delete(cache);
    }
  }));
}

addEventListener('activate', function (event) {
  event.waitUntil(
    caches.keys()
    .then(removeOldCache)
  );
});


// this handler is called when the webapp makes a
// request to backend, in this function we check if we already
// have the files in cache if so we we serve up the cached file,
// and request is not made to backend, else we make a request from here
addEventListener('fetch', function (event) {
  event.respondWith(
    caches.match(event.request)
    .then(function (response) {
      response = response || fetch(event.request);
      return response;
    })
  );
});
