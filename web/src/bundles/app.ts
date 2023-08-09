import "./common";

// Import third party jQuery plugins
import "../../third/bootstrap-typeahead/typeahead";
import "../../third/bootstrap-tooltip/tooltip";
import "jquery-caret-plugin/dist/jquery.caret";
import "../../third/jquery-idle/jquery.idle";
import "spectrum-colorpicker";
import "jquery-validation";
import "flatpickr";

// Import app JS
import "../setup";
import "../reload";
import "../hotkey";
import "../notifications";
import "../server_events";
import "../templates";
import "../settings";
import "../desktop_integration";
import "../zulip_test";

// Import styles
import "tippy.js/dist/tippy.css";
import "tippy.js/themes/light-border.css";
import "../../third/bootstrap-tooltip/tooltip.css";
import "spectrum-colorpicker/spectrum.css";
import "katex/dist/katex.css";
import "flatpickr/dist/flatpickr.css";
import "flatpickr/dist/plugins/confirmDate/confirmDate.css";
import "../../styles/tooltips.css";
import "../../styles/components.css";
import "../../styles/app_components.css";
import "../../styles/rendered_markdown.css";
import "../../styles/zulip.css";
import "../../styles/message_row.css";
import "../../styles/modal.css";
import "../../styles/settings.css";
import "../../styles/image_upload_widget.css";
import "../../styles/subscriptions.css";
import "../../styles/scheduled_messages.css";
import "../../styles/drafts.css";
import "../../styles/input_pill.css";
import "../../styles/informational_overlays.css";
import "../../styles/compose.css";
import "../../styles/message_edit_history.css";
import "../../styles/reactions.css";
import "../../styles/search.css";
import "../../styles/user_circles.css";
import "../../styles/left_sidebar.css";
import "../../styles/right_sidebar.css";
import "../../styles/lightbox.css";
import "../../styles/popovers.css";
import "../../styles/recent_view.css";
import "../../styles/typing_notifications.css";
import "../../styles/hotspots.css";
import "../../styles/dark_theme.css";
import "../../styles/user_status.css";
import "../../styles/widgets.css";
import "../../styles/print.css";
import "../../styles/inbox.css";

// This should be last.
import "../ui_init";
