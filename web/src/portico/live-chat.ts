import {ChatWidget} from "@papercups-io/chat-widget";
import React from "react";
import ReactDOM from "react-dom";

const widget = React.createElement(ChatWidget, {
    token: "a303bb5b-453b-4140-864b-4ced5883e9e2",
    inbox: "2e9c196e-5e94-4a65-8715-2f849cab35cb",
    title: "Welcome to Zulip",
    subtitle: "Ask us anything in the chat window below 😊",
    primaryColor: "#1890ff",
    newMessagePlaceholder: "Start typing...",
    showAgentAvailability: false,
    agentAvailableText: "We're online right now!",
    agentUnavailableText: "We're away at the moment.",
    requireEmailUpfront: false,
    iconVariant: "outlined",
    baseUrl: "http://localhost:4000",
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
