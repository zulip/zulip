import * as topic_settings from "./topic_settings";
import type {SeverTopicSettings} from "./topic_settings";

export function handle_topic_settings_updates(topic_setting_event: SeverTopicSettings): void {
    topic_settings.set_topic_setting(topic_setting_event);
}
