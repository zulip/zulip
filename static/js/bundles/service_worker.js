import {clientsClaim} from "workbox-core";
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

class CacheRedirectPlugin {
    cacheWillUpdate({request, response, event, state}) {
        // HACK to not update cache API.
        return null;
    }

    handlerWillRespond({request, response, event, state}) {
        // Need to iterate to access headers properties.
        const old_headers = {};
        for(const header of response.headers){
            old_headers[header[0]] = header[1];
        }
        const new_response = new Response(response.body, {
            status: response.status,
            statusText: response.statusText,
            headers: new Headers ({
                ...old_headers,
                "Cache-Control": "public, immutable",
            })
        });
        Object.defineProperty(new_response, "url", { value: response.url });

        return new_response;
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
        plugins: [
            new CacheRedirectPlugin(),
        ],
    }),
);
