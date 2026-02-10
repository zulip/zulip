import "./common.ts";

// Import third party jQuery plugins
import "jquery-caret-plugin/dist/jquery.caret";
import "../../third/jquery-idle/jquery.idle.js";
import "jquery-validation";

// Import app JS
import "../setup.ts";
import "../reload.ts";
import "../templates.ts";
import "../zulip_test.ts";
import "../inputs.ts";

// Import styles
import "tippy.js/dist/tippy.css";
// Adds color inheritance to the borders when using the default CSS Arrow.
// https://atomiks.github.io/tippyjs/v6/themes/#arrow-border
import "tippy.js/dist/border.css";
import "katex/dist/katex.css";
import "flatpickr/dist/flatpickr.css";
import "flatpickr/dist/plugins/confirmDate/confirmDate.css";
import "../../third/bootstrap/css/bootstrap.app.css";
import "../../third/bootstrap/css/bootstrap-btn.css";
import "../../styles/typeahead.css";
import "../../styles/app_variables.css";
import "../../styles/tooltips.css";
import "../../styles/buttons.css";
import "../../styles/inputs.css";
import "../../styles/banners.css";
import "../../styles/components.css";
import "../../styles/app_components.css";
import "../../styles/rendered_markdown.css";
import "../../styles/zulip.css";
import "../../styles/message_view_header.css";
import "../../styles/message_header.css";
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
import "../../styles/dark_theme.css";
import "../../styles/user_status.css";
import "../../styles/widgets.css";
import "../../styles/print.css";
import "../../styles/inbox.css";
import "../../styles/color_picker.css";
import "../../styles/animate.css";
import "@uppy/core/css/style.min.css";
import "@uppy/image-editor/css/style.min.css";

// This should be last.
import "../ui_init.js";
