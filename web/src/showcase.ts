/* eslint-disable @typescript-eslint/no-explicit-any */
import "./showcase_mock";

import * as hbs_bridge from "./hbs_bridge.ts";
import * as pure_dom from "./pure_dom.ts";
import * as poll_widget from "./poll_widget.ts";

// Bypass JQuery type resolution for the showcase environment
const $: any = (window as any).$;

/**
 * INITIALIZE: Called by ui_init.js
 * This sets up the Alice & Bob side-by-side multi-user simulation.
 */
export function initialize(): void {
    // 1. STOP THE ROUTER: Clear the hash so Zulip doesn't try to open #inbox
    window.location.hash = "";

    // 2. NUKE THE UI: Hide everything that isn't your demo
    $("body").children().hide();
    
    // 3. CREATE A CLEAN CONTAINER: Don't use #app, create a fresh one
    const $showcase = $('<div id="gsoc-showcase"></div>').appendTo("body");
    
    $showcase.css({
        "position": "fixed",
        "top": "0",
        "left": "0",
        "width": "100vw",
        "height": "100vh",
        "z-index": "2147483647", // Maximum possible z-index
        "background": "#f0f2f5",
        "display": "flex",
        "padding": "20px",
        "gap": "20px",
        "box-sizing": "border-box",
        "font-family": "sans-serif"
    });

    // 4. Build the side-by-side UI
    $showcase.html(`
        <div id="alice-view" style="flex: 1; border: 4px solid #007bff; background: white; padding: 20px; border-radius: 12px; box-shadow: 0 10px 25px rgba(0,0,0,0.1); overflow-y: auto;">
            <h1 style="color: #007bff; margin-top: 0; border-bottom: 2px solid #eee; padding-bottom: 10px;">Alice (User 1)</h1>
            <div class="widget-content"></div>
        </div>
        <div id="bob-view" style="flex: 1; border: 4px solid #28a745; background: white; padding: 20px; border-radius: 12px; box-shadow: 0 10px 25px rgba(0,0,0,0.1); overflow-y: auto;">
            <h1 style="color: #28a745; margin-top: 0; border-bottom: 2px solid #eee; padding-bottom: 10px;">Bob (User 2)</h1>
            <div class="widget-content"></div>
        </div>
    `);

    // 5. Inject DOM Fragments
    const alice_dom = (pure_dom.poll_widget() as any).to_dom();
    const bob_dom = (pure_dom.poll_widget() as any).to_dom();

    $("#alice-view .widget-content").append(alice_dom);
    $("#bob-view .widget-content").append(bob_dom);

    // 6. Setup the Virtual Server logic
    const virtual_server = {
        clients: [] as ((events: any[]) => void)[],
        broadcast(data: any) {
            
            // FIX: Use ID 9 (Desdemona/Current User) instead of 101
            // Zulip's people.ts knows who User 9 is.
            const event = { 
                sender_id: 9, 
                data: data 
            };

            for (const client_inbound of this.clients) {
                client_inbound([event]);
            }
        }
    };

    const setup_user = (selector: string) => {
        const inbound = (poll_widget as any).activate({
            $elem: $(`${selector} .poll-widget`),
            callback: (data: any) => virtual_server.broadcast(data),
            message: { id: 1 } as any,
            extra_data: {} as any,
        });
        virtual_server.clients.push(inbound);
    };

    setup_user("#alice-view");
    setup_user("#bob-view");
}