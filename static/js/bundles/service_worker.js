import {clientsClaim} from "workbox-core";
import {ExpirationPlugin} from "workbox-expiration";
import {registerRoute} from "workbox-routing";
import {CacheFirst} from "workbox-strategies";

// eslint-disable-next-line no-unused-expressions
self.__WB_MANIFEST;
self.__WB_DISABLE_DEV_LOGS = true;

// Note: A SW is considered updated if it's byte-different to the one the browser already has.

// The updated SW is in waiting state after it is successfully installed.
// And the current SW doesn't relinquish control over the clients even after a reload.
// Thus we kick out the current active SW and skip the waiting phase to activate it.
//
// This can be applied as we do not preache our versioned URLs.
self.skipWaiting();

// The following case applies to when a SW is installed for the first time or gets updated.
// If the page loads without the SW, then neither will its subresources.
// Thus to handle the events from the first time we take claim of the clients
// when the SW activates.
//
// Note: For hard reload the page loads before the SW even if a SW is activated.
clientsClaim();

const CACHE_VERSION = "-v1";

class S3SupportPlugin {
    requestWillFetch({request}) {
        // When CORS is not enabled, the requests received
        // from the S3 backend server have the type "opaque".
        // This causes the browser to add significant padding
        // to each response.
        // To overcome this we need trigger a no-cors request.
        const new_request = new Request(request.url, {mode: "cors"});
        return new_request;
    }

    cacheWillUpdate({response}) {
        if (response.ok && response.redirected) {
            // Service worker caching is required only when
            // the server is using an S3 upload backend.
            // Thus we cache only for responses where the
            // request has been redirected.
            return response;
        }
        return null;
    }
}

const match_user_uploads = ({url, request}) => {
    if (
        request.destination === "image" &&
        (url.pathname === "/thumbnail" || url.pathname.startsWith("/user_uploads"))
    ) {
        return true;
    }
    return false;
};

registerRoute(
    match_user_uploads,
    new CacheFirst({
        cacheName: "user-uploads" + CACHE_VERSION,
        plugins: [
            new S3SupportPlugin(),
            new ExpirationPlugin({
                maxEntries: 500,
                maxAgeSeconds: 30 * 24 * 60 * 60,
                purgeOnQuotaError: true,
            }),
        ],
    }),
);
