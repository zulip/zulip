import {ChatWidget} from "@papercups-io/chat-widget";
import React from "react";
import ReactDOM from "react-dom";

const widget = React.createElement(ChatWidget, {
    token: "b0868b6e-6677-4db9-badd-2d0368c68f74",
    inbox: "acbbc142-7792-4b0e-b157-1e02389ffb3a",
    title: "Chat with the Zulip team",
    subtitle: "How can we help you?",
    primaryColor: "#5f5ffc",
    greeting: "Hello! What's on your mind?",
    awayMessage: "Please leave a message, and we'll get back to you when we're back online.",
    newMessagePlaceholder: "Start typing...",
    showAgentAvailability: true,
    agentAvailableText: "We're online right now!",
    agentUnavailableText: "We're away at the moment.",
    requireEmailUpfront: false,
    iconVariant: "outlined",
    baseUrl: "https://app.papercups.io",
    // Optionally include data about your customer here to identify them
    // customer: {
    //     name: __CUSTOMER__.name,
    //     email: __CUSTOMER__.email,
    //     external_id: __CUSTOMER__.id,
    //     metadata: {
    //         plan: "premium"
    //     }
    // }
});

ReactDOM.render(widget, document.querySelector("#PapercupsChatWidget"));
