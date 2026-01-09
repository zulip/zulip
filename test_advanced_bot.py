#!/usr/bin/env python3
"""
Comprehensive Test Bot for ADVANCED_BOTS.md features

This bot tests all advanced bot functionality:
- Widget Types: rich_embed, interactive (buttons, select_menu, modals), freeform
- Bot Commands: registration, options, dynamic autocomplete
- Interactions: button_click, select_menu, modal_submit, freeform
- Responses: public, ephemeral, private, widget replies

Run with: python test_advanced_bot.py
Then configure an outgoing webhook bot to point to http://localhost:5050/webhook
"""

from flask import Flask, request, jsonify
import json
from datetime import datetime
import logging

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Track interaction history for testing
interaction_history = []


# =============================================================================
# WIDGET EXAMPLES - Rich Embed
# =============================================================================

def create_rich_embed_basic():
    """Basic rich embed with title and description"""
    return {
        "widget_type": "rich_embed",
        "extra_data": {
            "title": "Basic Embed Test",
            "description": "This is a simple embed with just a title and description.",
            "color": 3447003  # Blue
        }
    }


def create_rich_embed_full():
    """Full-featured rich embed with all fields"""
    return {
        "widget_type": "rich_embed",
        "extra_data": {
            "title": "Complete Weather Report",
            "description": "Current conditions for **San Francisco, CA**\n\nExpect sunny skies throughout the day.",
            "url": "https://weather.example.com/sf",
            "color": 15844367,  # Gold
            "author": {
                "name": "Weather Bot",
                "icon_url": "https://cdn-icons-png.flaticon.com/512/1163/1163661.png"
            },
            "thumbnail": {
                "url": "https://cdn-icons-png.flaticon.com/512/869/869869.png"
            },
            "fields": [
                {"name": "Temperature", "value": "68°F", "inline": True},
                {"name": "Humidity", "value": "45%", "inline": True},
                {"name": "Wind", "value": "5 mph NW", "inline": True},
                {"name": "UV Index", "value": "6 (High)", "inline": True},
                {"name": "Visibility", "value": "10 miles", "inline": True},
                {"name": "Pressure", "value": "30.1 in", "inline": True},
                {"name": "Forecast", "value": "Clear skies expected for the next 3 days. Perfect weather for outdoor activities!", "inline": False}
            ],
            "image": {
                "url": "https://cdn-icons-png.flaticon.com/512/1146/1146869.png"
            },
            "footer": {
                "text": "Last updated",
                "icon_url": "https://cdn-icons-png.flaticon.com/512/2972/2972531.png"
            },
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
    }


# =============================================================================
# WIDGET EXAMPLES - Interactive (Buttons)
# =============================================================================

def create_button_widget_all_styles():
    """Interactive widget with all button styles"""
    return {
        "widget_type": "interactive",
        "extra_data": {
            "content": "**Button Style Showcase**\nClick any button to test the interaction:",
            "components": [
                {
                    "type": "action_row",
                    "components": [
                        {
                            "type": "button",
                            "label": "Primary",
                            "style": "primary",
                            "custom_id": "test_button_primary"
                        },
                        {
                            "type": "button",
                            "label": "Secondary",
                            "style": "secondary",
                            "custom_id": "test_button_secondary"
                        },
                        {
                            "type": "button",
                            "label": "Success",
                            "style": "success",
                            "custom_id": "test_button_success"
                        },
                        {
                            "type": "button",
                            "label": "Danger",
                            "style": "danger",
                            "custom_id": "test_button_danger"
                        }
                    ]
                },
                {
                    "type": "action_row",
                    "components": [
                        {
                            "type": "button",
                            "label": "Visit Example.com",
                            "style": "link",
                            "url": "https://example.com"
                        },
                        {
                            "type": "button",
                            "label": "Disabled Button",
                            "style": "secondary",
                            "custom_id": "test_disabled",
                            "disabled": True
                        }
                    ]
                }
            ]
        }
    }


def create_approval_workflow():
    """Approval workflow with approve/reject buttons"""
    return {
        "widget_type": "interactive",
        "extra_data": {
            "content": "**Approval Request #1234**\n\nRequested by: John Doe\nAmount: $500.00\nPurpose: Office supplies",
            "components": [
                {
                    "type": "action_row",
                    "components": [
                        {
                            "type": "button",
                            "label": "Approve",
                            "style": "success",
                            "custom_id": "approve_1234"
                        },
                        {
                            "type": "button",
                            "label": "Reject",
                            "style": "danger",
                            "custom_id": "reject_1234"
                        },
                        {
                            "type": "button",
                            "label": "Request More Info",
                            "style": "secondary",
                            "custom_id": "more_info_1234"
                        }
                    ]
                }
            ]
        }
    }


# =============================================================================
# WIDGET EXAMPLES - Interactive (Select Menu)
# =============================================================================

def create_select_menu_widget():
    """Interactive widget with select menus"""
    return {
        "widget_type": "interactive",
        "extra_data": {
            "content": "**Task Assignment**\nConfigure the task below:",
            "components": [
                {
                    "type": "action_row",
                    "components": [
                        {
                            "type": "select_menu",
                            "custom_id": "select_assignee",
                            "placeholder": "Select an assignee",
                            "options": [
                                {"label": "Alice", "value": "user_alice", "description": "Engineering Team Lead"},
                                {"label": "Bob", "value": "user_bob", "description": "Senior Developer"},
                                {"label": "Carol", "value": "user_carol", "description": "Product Manager"},
                                {"label": "Dave", "value": "user_dave", "description": "QA Engineer"}
                            ]
                        }
                    ]
                },
                {
                    "type": "action_row",
                    "components": [
                        {
                            "type": "select_menu",
                            "custom_id": "select_priority",
                            "placeholder": "Select priority",
                            "options": [
                                {"label": "Critical", "value": "p0", "description": "Drop everything!"},
                                {"label": "High", "value": "p1", "description": "Complete this week"},
                                {"label": "Medium", "value": "p2", "description": "Complete this sprint", "default": True},
                                {"label": "Low", "value": "p3", "description": "When you have time"}
                            ]
                        }
                    ]
                },
                {
                    "type": "action_row",
                    "components": [
                        {
                            "type": "select_menu",
                            "custom_id": "select_labels",
                            "placeholder": "Select labels (multiple)",
                            "min_values": 0,
                            "max_values": 3,
                            "options": [
                                {"label": "Bug", "value": "label_bug"},
                                {"label": "Feature", "value": "label_feature"},
                                {"label": "Documentation", "value": "label_docs"},
                                {"label": "Performance", "value": "label_perf"},
                                {"label": "Security", "value": "label_security"}
                            ]
                        }
                    ]
                }
            ]
        }
    }


# =============================================================================
# WIDGET EXAMPLES - Interactive (Modals)
# =============================================================================

def create_modal_button_widget():
    """Button that opens a modal"""
    return {
        "widget_type": "interactive",
        "extra_data": {
            "content": "**Feedback Portal**\nWe'd love to hear from you!",
            "components": [
                {
                    "type": "action_row",
                    "components": [
                        {
                            "type": "button",
                            "label": "Submit Feedback",
                            "style": "primary",
                            "custom_id": "open_feedback_modal",
                            "modal": {
                                "custom_id": "feedback_modal",
                                "title": "Submit Your Feedback",
                                "components": [
                                    {
                                        "type": "action_row",
                                        "components": [
                                            {
                                                "type": "text_input",
                                                "custom_id": "feedback_subject",
                                                "label": "Subject",
                                                "style": "short",
                                                "placeholder": "Brief summary of your feedback",
                                                "min_length": 5,
                                                "max_length": 100,
                                                "required": True
                                            }
                                        ]
                                    },
                                    {
                                        "type": "action_row",
                                        "components": [
                                            {
                                                "type": "text_input",
                                                "custom_id": "feedback_body",
                                                "label": "Your Feedback",
                                                "style": "paragraph",
                                                "placeholder": "Please provide detailed feedback...",
                                                "min_length": 20,
                                                "max_length": 2000,
                                                "required": True
                                            }
                                        ]
                                    },
                                    {
                                        "type": "action_row",
                                        "components": [
                                            {
                                                "type": "text_input",
                                                "custom_id": "feedback_email",
                                                "label": "Email (optional)",
                                                "style": "short",
                                                "placeholder": "your@email.com",
                                                "required": False
                                            }
                                        ]
                                    }
                                ]
                            }
                        },
                        {
                            "type": "button",
                            "label": "Report Bug",
                            "style": "danger",
                            "custom_id": "open_bug_modal",
                            "modal": {
                                "custom_id": "bug_report_modal",
                                "title": "Report a Bug",
                                "components": [
                                    {
                                        "type": "action_row",
                                        "components": [
                                            {
                                                "type": "text_input",
                                                "custom_id": "bug_title",
                                                "label": "Bug Title",
                                                "style": "short",
                                                "placeholder": "Short description of the bug",
                                                "required": True
                                            }
                                        ]
                                    },
                                    {
                                        "type": "action_row",
                                        "components": [
                                            {
                                                "type": "text_input",
                                                "custom_id": "bug_steps",
                                                "label": "Steps to Reproduce",
                                                "style": "paragraph",
                                                "placeholder": "1. Go to...\n2. Click on...\n3. See error...",
                                                "value": "1. \n2. \n3. ",
                                                "required": True
                                            }
                                        ]
                                    },
                                    {
                                        "type": "action_row",
                                        "components": [
                                            {
                                                "type": "text_input",
                                                "custom_id": "bug_expected",
                                                "label": "Expected Behavior",
                                                "style": "paragraph",
                                                "placeholder": "What should have happened?",
                                                "required": True
                                            }
                                        ]
                                    }
                                ]
                            }
                        }
                    ]
                }
            ]
        }
    }


# =============================================================================
# WIDGET EXAMPLES - Freeform (requires trusted bot)
# =============================================================================

def create_freeform_counter():
    """Freeform widget with interactive counter"""
    return {
        "widget_type": "freeform",
        "extra_data": {
            "html": """
                <div class="counter-widget">
                    <h3>Interactive Counter</h3>
                    <div class="counter-display">
                        <span id="count">0</span>
                    </div>
                    <div class="counter-buttons">
                        <button id="decrement" class="btn btn-minus">-</button>
                        <button id="increment" class="btn btn-plus">+</button>
                        <button id="reset" class="btn btn-reset">Reset</button>
                    </div>
                </div>
            """,
            "css": """
                .counter-widget {
                    font-family: -apple-system, BlinkMacSystemFont, sans-serif;
                    text-align: center;
                    padding: 20px;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    border-radius: 12px;
                    color: white;
                }
                .counter-display {
                    font-size: 48px;
                    font-weight: bold;
                    margin: 20px 0;
                }
                .counter-buttons {
                    display: flex;
                    gap: 10px;
                    justify-content: center;
                }
                .btn {
                    padding: 10px 20px;
                    border: none;
                    border-radius: 6px;
                    font-size: 18px;
                    cursor: pointer;
                    transition: transform 0.1s, opacity 0.1s;
                }
                .btn:hover { opacity: 0.9; transform: scale(1.05); }
                .btn:active { transform: scale(0.95); }
                .btn-plus { background: #22c55e; color: white; }
                .btn-minus { background: #ef4444; color: white; }
                .btn-reset { background: #6b7280; color: white; }
            """,
            "js": """
                let count = 0;

                function updateDisplay() {
                    container.querySelector('#count').textContent = count;
                }

                ctx.on('click', '#increment', () => {
                    count++;
                    updateDisplay();
                    ctx.post_interaction({ action: 'increment', count: count });
                });

                ctx.on('click', '#decrement', () => {
                    count--;
                    updateDisplay();
                    ctx.post_interaction({ action: 'decrement', count: count });
                });

                ctx.on('click', '#reset', () => {
                    count = 0;
                    updateDisplay();
                    ctx.post_interaction({ action: 'reset', count: count });
                });
            """
        }
    }


def create_freeform_poll():
    """Freeform widget with a poll"""
    return {
        "widget_type": "freeform",
        "extra_data": {
            "html": """
                <div class="poll-widget">
                    <h3>Quick Poll: Best Programming Language?</h3>
                    <div class="poll-options">
                        <button class="poll-option" data-option="python">
                            <span class="option-name">Python</span>
                            <span class="option-bar" style="width: 0%"></span>
                            <span class="option-count">0 votes</span>
                        </button>
                        <button class="poll-option" data-option="javascript">
                            <span class="option-name">JavaScript</span>
                            <span class="option-bar" style="width: 0%"></span>
                            <span class="option-count">0 votes</span>
                        </button>
                        <button class="poll-option" data-option="rust">
                            <span class="option-name">Rust</span>
                            <span class="option-bar" style="width: 0%"></span>
                            <span class="option-count">0 votes</span>
                        </button>
                        <button class="poll-option" data-option="go">
                            <span class="option-name">Go</span>
                            <span class="option-bar" style="width: 0%"></span>
                            <span class="option-count">0 votes</span>
                        </button>
                    </div>
                </div>
            """,
            "css": """
                .poll-widget {
                    font-family: -apple-system, BlinkMacSystemFont, sans-serif;
                    padding: 20px;
                    background: #1e293b;
                    border-radius: 12px;
                    color: white;
                }
                .poll-widget h3 { margin: 0 0 15px 0; }
                .poll-options { display: flex; flex-direction: column; gap: 10px; }
                .poll-option {
                    position: relative;
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    padding: 12px 16px;
                    background: #334155;
                    border: none;
                    border-radius: 8px;
                    color: white;
                    cursor: pointer;
                    overflow: hidden;
                    transition: transform 0.1s;
                }
                .poll-option:hover { transform: scale(1.02); }
                .option-bar {
                    position: absolute;
                    left: 0;
                    top: 0;
                    height: 100%;
                    background: #3b82f6;
                    opacity: 0.3;
                    transition: width 0.3s;
                }
                .option-name, .option-count { position: relative; z-index: 1; }
            """,
            "js": """
                const votes = { python: 0, javascript: 0, rust: 0, go: 0 };

                function updateDisplay() {
                    const total = Object.values(votes).reduce((a, b) => a + b, 0);
                    container.querySelectorAll('.poll-option').forEach(btn => {
                        const option = btn.dataset.option;
                        const count = votes[option];
                        const pct = total > 0 ? (count / total * 100) : 0;
                        btn.querySelector('.option-bar').style.width = pct + '%';
                        btn.querySelector('.option-count').textContent = count + ' vote' + (count !== 1 ? 's' : '');
                    });
                }

                ctx.on('click', '.poll-option', (e) => {
                    const option = e.currentTarget.dataset.option;
                    votes[option]++;
                    updateDisplay();
                    ctx.post_interaction({ action: 'vote', option: option, votes: votes });
                });
            """
        }
    }


# =============================================================================
# COMMAND DEFINITIONS
# =============================================================================

BOT_COMMANDS = [
    {
        "name": "testbot",
        "description": "Run bot tests",
        "options": [
            {
                "name": "test",
                "type": "string",
                "description": "Which test to run",
                "required": True,
                "choices": [
                    {"name": "Rich Embed (Basic)", "value": "embed_basic"},
                    {"name": "Rich Embed (Full)", "value": "embed_full"},
                    {"name": "Buttons (All Styles)", "value": "buttons"},
                    {"name": "Approval Workflow", "value": "approval"},
                    {"name": "Select Menus", "value": "select"},
                    {"name": "Modals", "value": "modal"},
                    {"name": "Freeform Counter", "value": "freeform_counter"},
                    {"name": "Freeform Poll", "value": "freeform_poll"},
                    {"name": "All Widgets", "value": "all"}
                ]
            }
        ]
    },
    {
        "name": "weather",
        "description": "Get weather for a location",
        "options": [
            {
                "name": "location",
                "type": "string",
                "description": "City name or ZIP code",
                "required": True
            },
            {
                "name": "units",
                "type": "string",
                "description": "Temperature units",
                "choices": [
                    {"name": "Celsius", "value": "c"},
                    {"name": "Fahrenheit", "value": "f"}
                ]
            }
        ]
    },
    {
        "name": "inventory",
        "description": "Search inventory items",
        "options": [
            {
                "name": "item",
                "type": "string",
                "description": "Item to search (supports autocomplete)",
                "required": True
            }
        ]
    },
    {
        "name": "echo",
        "description": "Echo back a message with response type",
        "options": [
            {
                "name": "message",
                "type": "string",
                "description": "Message to echo",
                "required": True
            },
            {
                "name": "type",
                "type": "string",
                "description": "Response type",
                "choices": [
                    {"name": "Public", "value": "public"},
                    {"name": "Ephemeral (only you)", "value": "ephemeral"},
                    {"name": "With Widget", "value": "widget"}
                ]
            }
        ]
    }
]

# Inventory items for autocomplete demo
INVENTORY_ITEMS = [
    {"value": "sword_iron", "label": "Iron Sword", "description": "A sturdy iron blade"},
    {"value": "sword_steel", "label": "Steel Sword", "description": "Sharp and reliable"},
    {"value": "sword_mithril", "label": "Mithril Sword", "description": "Light as a feather"},
    {"value": "shield_wooden", "label": "Wooden Shield", "description": "Basic protection"},
    {"value": "shield_iron", "label": "Iron Shield", "description": "Solid defense"},
    {"value": "shield_tower", "label": "Tower Shield", "description": "Maximum coverage"},
    {"value": "potion_health", "label": "Health Potion", "description": "Restores 50 HP"},
    {"value": "potion_mana", "label": "Mana Potion", "description": "Restores 30 MP"},
    {"value": "potion_stamina", "label": "Stamina Potion", "description": "Restores energy"},
    {"value": "armor_leather", "label": "Leather Armor", "description": "Light and flexible"},
    {"value": "armor_chain", "label": "Chain Mail", "description": "Good balance"},
    {"value": "armor_plate", "label": "Plate Armor", "description": "Heavy protection"},
]

# City database for weather autocomplete
CITIES = [
    {"value": "san_francisco", "label": "San Francisco, CA"},
    {"value": "new_york", "label": "New York, NY"},
    {"value": "los_angeles", "label": "Los Angeles, CA"},
    {"value": "chicago", "label": "Chicago, IL"},
    {"value": "houston", "label": "Houston, TX"},
    {"value": "phoenix", "label": "Phoenix, AZ"},
    {"value": "philadelphia", "label": "Philadelphia, PA"},
    {"value": "san_antonio", "label": "San Antonio, TX"},
    {"value": "san_diego", "label": "San Diego, CA"},
    {"value": "dallas", "label": "Dallas, TX"},
    {"value": "london", "label": "London, UK"},
    {"value": "paris", "label": "Paris, France"},
    {"value": "tokyo", "label": "Tokyo, Japan"},
    {"value": "sydney", "label": "Sydney, Australia"},
]


# =============================================================================
# WEBHOOK HANDLERS
# =============================================================================

@app.route('/webhook', methods=['POST'])
def webhook():
    """Main webhook endpoint for outgoing webhook bot"""
    data = request.json
    logger.info(f"Received webhook: {json.dumps(data, indent=2)}")

    request_type = data.get('type', 'message')

    if request_type == 'autocomplete':
        return handle_autocomplete(data)
    elif request_type == 'interaction':
        return handle_interaction(data)
    elif request_type == 'command_invocation':
        return handle_command_invocation(data)
    else:
        # Legacy message format - just acknowledge, no processing
        # Commands should use the invoke API, not message parsing
        logger.info("Received legacy message format - ignoring")
        return jsonify({})


def handle_autocomplete(data):
    """Handle autocomplete requests"""
    command = data.get('command', '')
    option = data.get('option', '')
    partial = data.get('partial', '').lower()

    logger.info(f"Autocomplete: command={command}, option={option}, partial={partial}")

    choices = []

    if command == 'inventory' and option == 'item':
        choices = [
            item for item in INVENTORY_ITEMS
            if partial in item['label'].lower() or partial in item['value'].lower()
        ][:10]

    elif command == 'weather' and option == 'location':
        choices = [
            city for city in CITIES
            if partial in city['label'].lower()
        ][:10]

    return jsonify({"choices": choices})


def handle_command_invocation(data):
    """Handle slash command invocations from the new invoke endpoint"""
    command = data.get('command', '')
    arguments = data.get('arguments', {})
    user = data.get('user', {})
    interaction_id = data.get('interaction_id')

    logger.info(f"Command invocation: command={command}, arguments={arguments}, interaction_id={interaction_id}")

    if command == 'testbot':
        test_type = arguments.get('test', 'all')
        return handle_testbot_invocation(test_type)

    elif command == 'weather':
        location = arguments.get('location', 'Unknown')
        units = arguments.get('units', 'f')
        return handle_weather_invocation(location, units)

    elif command == 'inventory':
        item = arguments.get('item', '')
        return handle_inventory_invocation(item)

    elif command == 'echo':
        message = arguments.get('message', 'Hello!')
        response_type = arguments.get('type', 'public')
        return handle_echo_invocation(message, response_type, user)

    else:
        return jsonify({
            "content": f"Unknown command: `/{command}`"
        })


def handle_testbot_invocation(test_type):
    """Handle /testbot command invocation"""
    # Map test types to their widget creators
    test_widgets = {
        'embed_basic': ("Rich Embed (Basic)", create_rich_embed_basic),
        'embed_full': ("Rich Embed (Full)", create_rich_embed_full),
        'buttons': ("Button Styles", create_button_widget_all_styles),
        'approval': ("Approval Workflow", create_approval_workflow),
        'select': ("Select Menus", create_select_menu_widget),
        'modal': ("Modal Forms", create_modal_button_widget),
        'freeform_counter': ("Freeform Counter", create_freeform_counter),
        'freeform_poll': ("Freeform Poll", create_freeform_poll),
    }

    # Special test types that return different response formats
    if test_type == 'ephemeral':
        # Test ephemeral response - only visible to the invoking user
        return jsonify({
            "ephemeral": True,
            "content": "**This is an ephemeral response!**\n\nOnly you can see this message. Other users in this conversation cannot see it.\n\nYou can dismiss it by clicking the X button."
        })

    if test_type == 'all':
        # List all available tests - only one widget per message is supported
        test_list = "\n".join([f"- `{key}`: {name}" for key, (name, _) in test_widgets.items()])
        return jsonify({
            "content": f"**Available Widget Tests**\n\nRun individual tests using `/testbot <test>`. Each bot response can only include one widget.\n\n{test_list}\n- `ephemeral`: Ephemeral Response (only you can see)"
        })

    if test_type not in test_widgets:
        return jsonify({
            "content": f"Unknown test type: `{test_type}`\n\nUse `/testbot all` to see available tests."
        })

    name, create_widget = test_widgets[test_type]
    widget = create_widget()

    return jsonify({
        "content": f"**{name}** widget:",
        "widget_content": json.dumps(widget)
    })


def handle_weather_invocation(location, units):
    """Handle /weather command invocation"""
    temp = 72 if units == 'f' else 22
    unit_symbol = '°F' if units == 'f' else '°C'

    return jsonify({
        "content": "",
        "widget_content": json.dumps({
            "widget_type": "rich_embed",
            "extra_data": {
                "title": f"Weather for {location}",
                "description": "Sunny with a chance of clouds",
                "color": 16776960,
                "fields": [
                    {"name": "Temperature", "value": f"{temp}{unit_symbol}", "inline": True},
                    {"name": "Humidity", "value": "45%", "inline": True},
                    {"name": "Wind", "value": "5 mph", "inline": True}
                ],
                "footer": {
                    "text": "Weather data is simulated for testing"
                }
            }
        })
    })


def handle_inventory_invocation(search):
    """Handle /inventory command invocation"""
    matching_items = [
        item for item in INVENTORY_ITEMS
        if search.lower() in item['label'].lower() or search.lower() in item['value']
    ]

    if not matching_items:
        return jsonify({
            "content": f"No items found matching `{search}`"
        })

    fields = [
        {"name": item['label'], "value": item['description'], "inline": True}
        for item in matching_items[:9]
    ]

    return jsonify({
        "content": "",
        "widget_content": json.dumps({
            "widget_type": "rich_embed",
            "extra_data": {
                "title": f"Inventory Search: {search}",
                "description": f"Found {len(matching_items)} items",
                "color": 10181046,
                "fields": fields
            }
        })
    })


def handle_echo_invocation(message, response_type, user):
    """Handle /echo command invocation"""
    if response_type == 'ephemeral':
        return jsonify({
            "ephemeral": True,
            "content": f"(Ephemeral) {message}"
        })

    if response_type == 'widget':
        return jsonify({
            "content": "",
            "widget_content": json.dumps({
                "widget_type": "rich_embed",
                "extra_data": {
                    "title": "Echo Widget",
                    "description": message,
                    "color": 3066993,
                    "author": {
                        "name": user.get('full_name', 'Unknown')
                    }
                }
            })
        })

    return jsonify({
        "content": message
    })


def handle_interaction(data):
    """Handle widget interactions"""
    interaction_type = data.get('interaction_type', '')
    custom_id = data.get('custom_id', '')
    interaction_data = data.get('data', {})
    user = data.get('user', {})

    logger.info(f"Interaction: type={interaction_type}, custom_id={custom_id}, data={interaction_data}")

    # Store for history
    interaction_history.append({
        "timestamp": datetime.utcnow().isoformat(),
        "type": interaction_type,
        "custom_id": custom_id,
        "data": interaction_data,
        "user": user
    })

    # Handle button clicks
    if interaction_type == 'button_click':
        return handle_button_click(custom_id, user)

    # Handle select menu selections
    elif interaction_type == 'select_menu':
        return handle_select_menu(custom_id, interaction_data, user)

    # Handle modal submissions
    elif interaction_type == 'modal_submit':
        return handle_modal_submit(custom_id, interaction_data, user)

    # Handle freeform interactions
    elif interaction_type == 'freeform':
        return handle_freeform(interaction_data, user)

    return jsonify({})


def handle_button_click(custom_id, user):
    """Handle button click interactions"""
    user_name = user.get('full_name', 'Unknown')

    # Test button styles
    if custom_id.startswith('test_button_'):
        style = custom_id.replace('test_button_', '')
        return jsonify({
            "ephemeral": True,
            "content": f"You clicked the **{style}** button! This is an ephemeral response (only you can see it)."
        })

    # Approval workflow
    if custom_id.startswith('approve_'):
        request_id = custom_id.replace('approve_', '')
        return jsonify({
            "content": f"Request #{request_id} has been **approved** by {user_name}!",
            "widget_content": json.dumps({
                "widget_type": "rich_embed",
                "extra_data": {
                    "title": f"Request #{request_id} - Approved",
                    "description": f"Approved by {user_name}",
                    "color": 3066993,  # Green
                    "timestamp": datetime.utcnow().isoformat() + "Z"
                }
            })
        })

    if custom_id.startswith('reject_'):
        request_id = custom_id.replace('reject_', '')
        return jsonify({
            "ephemeral": True,
            "content": f"You rejected request #{request_id}. The requester will be notified."
        })

    if custom_id.startswith('more_info_'):
        request_id = custom_id.replace('more_info_', '')
        return jsonify({
            "content": f"{user_name} requested more information for request #{request_id}."
        })

    # Default response
    return jsonify({
        "ephemeral": True,
        "content": f"Button clicked: `{custom_id}`"
    })


def handle_select_menu(custom_id, data, user):
    """Handle select menu interactions"""
    values = data.get('values', [])
    user_name = user.get('full_name', 'Unknown')

    if custom_id == 'select_assignee':
        assignee = values[0] if values else 'nobody'
        return jsonify({
            "content": f"Task assigned to **{assignee}** by {user_name}"
        })

    if custom_id == 'select_priority':
        priority = values[0] if values else 'none'
        priority_names = {'p0': 'Critical', 'p1': 'High', 'p2': 'Medium', 'p3': 'Low'}
        return jsonify({
            "ephemeral": True,
            "content": f"Priority set to **{priority_names.get(priority, priority)}**"
        })

    if custom_id == 'select_labels':
        if values:
            labels = ', '.join(values)
            return jsonify({
                "content": f"Labels applied: {labels}"
            })
        return jsonify({
            "ephemeral": True,
            "content": "No labels selected"
        })

    return jsonify({
        "ephemeral": True,
        "content": f"Selection made: {custom_id} = {values}"
    })


def handle_modal_submit(custom_id, data, user):
    """Handle modal form submissions"""
    fields = data.get('fields', {})
    user_name = user.get('full_name', 'Unknown')

    if custom_id == 'feedback_modal':
        subject = fields.get('feedback_subject', 'No subject')
        body = fields.get('feedback_body', 'No feedback')
        email = fields.get('feedback_email', 'Not provided')

        return jsonify({
            "content": f"**New Feedback Received**",
            "widget_content": json.dumps({
                "widget_type": "rich_embed",
                "extra_data": {
                    "title": subject,
                    "description": body,
                    "color": 5814783,  # Purple
                    "author": {
                        "name": user_name
                    },
                    "fields": [
                        {"name": "Contact Email", "value": email, "inline": True}
                    ],
                    "timestamp": datetime.utcnow().isoformat() + "Z"
                }
            })
        })

    if custom_id == 'bug_report_modal':
        title = fields.get('bug_title', 'No title')
        steps = fields.get('bug_steps', 'No steps')
        expected = fields.get('bug_expected', 'Not specified')

        return jsonify({
            "content": f"**Bug Report Filed**",
            "widget_content": json.dumps({
                "widget_type": "rich_embed",
                "extra_data": {
                    "title": f"Bug: {title}",
                    "color": 15158332,  # Red
                    "author": {
                        "name": f"Reported by {user_name}"
                    },
                    "fields": [
                        {"name": "Steps to Reproduce", "value": steps, "inline": False},
                        {"name": "Expected Behavior", "value": expected, "inline": False}
                    ],
                    "timestamp": datetime.utcnow().isoformat() + "Z"
                }
            })
        })

    return jsonify({
        "ephemeral": True,
        "content": f"Modal submitted: {custom_id}\nFields: {json.dumps(fields, indent=2)}"
    })


def handle_freeform(data, user):
    """Handle freeform widget interactions"""
    action = data.get('action', 'unknown')
    user_name = user.get('full_name', 'Unknown')

    if action == 'increment':
        count = data.get('count', 0)
        if count % 10 == 0 and count > 0:
            return jsonify({
                "content": f"Milestone! {user_name} reached count **{count}**!"
            })

    elif action == 'vote':
        option = data.get('option', 'unknown')
        return jsonify({
            "ephemeral": True,
            "content": f"Thanks for voting for **{option}**!"
        })

    # Silent acknowledgment for most freeform interactions
    return jsonify({})


# =============================================================================
# UTILITY ENDPOINTS
# =============================================================================

@app.route('/commands', methods=['GET'])
def get_commands():
    """Return list of commands for registration"""
    return jsonify({"commands": BOT_COMMANDS})


@app.route('/history', methods=['GET'])
def get_history():
    """Return interaction history for debugging"""
    return jsonify({"interactions": interaction_history[-50:]})


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({"status": "ok", "timestamp": datetime.utcnow().isoformat()})


@app.route('/', methods=['GET'])
def index():
    """Landing page with bot info"""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Tulip Advanced Bot Tester</title>
        <style>
            body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; max-width: 800px; margin: 50px auto; padding: 20px; }
            h1 { color: #1e293b; }
            code { background: #f1f5f9; padding: 2px 6px; border-radius: 4px; }
            pre { background: #1e293b; color: #e2e8f0; padding: 15px; border-radius: 8px; overflow-x: auto; }
            .section { margin: 30px 0; padding: 20px; background: #f8fafc; border-radius: 8px; }
            ul { line-height: 1.8; }
            .note { background: #fef3c7; border-left: 4px solid #f59e0b; padding: 12px; margin: 20px 0; }
        </style>
    </head>
    <body>
        <h1>Tulip Advanced Bot Tester</h1>
        <p>This bot tests all advanced bot features using the <strong>new command invocation API</strong>.</p>

        <div class="note">
            <strong>Setup Required:</strong> Register commands using <code>register_test_bot_commands.py</code>
            before using slash commands in the UI.
        </div>

        <div class="section">
            <h2>Webhook Endpoint</h2>
            <pre>POST http://localhost:5050/webhook</pre>
        </div>

        <div class="section">
            <h2>Registered Commands (via Command Composer UI)</h2>
            <ul>
                <li><code>/testbot</code> - Test widget types (select from dropdown)</li>
                <li><code>/weather</code> - Weather with location autocomplete</li>
                <li><code>/inventory</code> - Inventory search with autocomplete</li>
                <li><code>/echo</code> - Test response types (public, ephemeral, widget)</li>
            </ul>
        </div>

        <div class="section">
            <h2>Widget Types Tested</h2>
            <ul>
                <li><strong>Rich Embed</strong> - Basic and full-featured embeds</li>
                <li><strong>Interactive</strong> - Buttons, Select Menus, Modals</li>
                <li><strong>Freeform</strong> - Custom HTML/CSS/JS widgets</li>
                <li><strong>Command Invocation</strong> - Slash command display widget</li>
            </ul>
        </div>

        <div class="section">
            <h2>Webhook Request Types Handled</h2>
            <ul>
                <li><code>command_invocation</code> - Slash command executed via invoke API</li>
                <li><code>autocomplete</code> - Dynamic option suggestions</li>
                <li><code>interaction</code> - Button clicks, select menus, modal submits</li>
            </ul>
        </div>

        <div class="section">
            <h2>API Endpoints</h2>
            <ul>
                <li><code>GET /commands</code> - List commands for registration</li>
                <li><code>GET /history</code> - View interaction history</li>
                <li><code>GET /health</code> - Health check</li>
            </ul>
        </div>
    </body>
    </html>
    """


if __name__ == '__main__':
    print("=" * 60)
    print("Tulip Advanced Bot Tester")
    print("=" * 60)
    print()
    print("Webhook URL: http://localhost:5050/webhook")
    print()
    print("SETUP:")
    print("  1. Create an outgoing webhook bot pointing to this URL")
    print("  2. Run: python register_test_bot_commands.py --bot-email <email> --api-key <key>")
    print("  3. Use /testbot, /weather, /inventory, /echo via command composer")
    print()
    print("Features tested:")
    print("  - Command invocation via new invoke API")
    print("  - Dynamic autocomplete for command options")
    print("  - Rich Embed widgets (basic and full)")
    print("  - Interactive widgets (buttons, select menus, modals)")
    print("  - Freeform widgets (custom HTML/CSS/JS)")
    print("  - Response types (public, ephemeral, widget replies)")
    print("  - Widget interactions (button clicks, selections, form submits)")
    print()
    print("=" * 60)

    app.run(host='0.0.0.0', port=5050, debug=True)
