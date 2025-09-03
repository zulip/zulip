import {show_loading_indicator, hide_loading_indicator} from './loading';

// Around line where messages are fetched
export function get_messages(...) {
    let loading_indicator = null;
    
    // Show loading indicator with slight delay to avoid flickering
    const loading_timer = setTimeout(() => {
        loading_indicator = show_loading_indicator();
    }, 300);

    try {
        // Existing fetch code here...
        const response = await fetch(...);
        
        // Hide loading indicator
        clearTimeout(loading_timer);
        if (loading_indicator) {
            hide_loading_indicator(loading_indicator);
        }
        
        return response;
    } catch (error) {
        clearTimeout(loading_timer);
        if (loading_indicator) {
            hide_loading_indicator(loading_indicator);
        }
        throw error;
    }
}