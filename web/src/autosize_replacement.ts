// Native textarea autosize implementation
// Replaces the archived autosize library with a native implementation

type AutosizeElement = HTMLTextAreaElement | JQuery<HTMLTextAreaElement>;

interface AutosizeInstance {
    textarea: HTMLTextAreaElement;
    mirror: HTMLDivElement;
    destroy: () => void;
    inputListener: (e: Event) => void;
    scrollListener: (e: Event) => void;
    resizeObserver?: ResizeObserver;
}

const instances = new Map<HTMLTextAreaElement, AutosizeInstance>();

// Create a hidden mirror element for measuring text content
function createMirror(textarea: HTMLTextAreaElement): HTMLDivElement {
    const mirror = document.createElement('div');
    
    // Copy relevant styles from the textarea to the mirror
    updateMirrorStyles(textarea, mirror);
    
    document.body.appendChild(mirror);
    return mirror;
}

// Update the mirror's styles to match the textarea
function updateMirrorStyles(textarea: HTMLTextAreaElement, mirror: HTMLDivElement): void {
    const styles = window.getComputedStyle(textarea);
    mirror.style.position = 'absolute';
    mirror.style.visibility = 'hidden';
    mirror.style.top = '-9999px';
    mirror.style.left = '-9999px';
    mirror.style.zIndex = '-1';
    mirror.style.whiteSpace = styles.whiteSpace || 'pre-wrap';
    mirror.style.wordWrap = styles.wordWrap || 'break-word';
    mirror.style.overflowWrap = styles.overflowWrap || 'break-word';
    mirror.style.width = styles.width;
    mirror.style.font = styles.font;
    mirror.style.fontSize = styles.fontSize;
    mirror.style.fontFamily = styles.fontFamily;
    mirror.style.fontWeight = styles.fontWeight;
    mirror.style.fontStyle = styles.fontStyle;
    mirror.style.letterSpacing = styles.letterSpacing;
    mirror.style.textTransform = styles.textTransform;
    mirror.style.padding = styles.padding;
    mirror.style.border = styles.border;
    mirror.style.boxSizing = styles.boxSizing;
    mirror.style.lineHeight = styles.lineHeight;
    mirror.style.paddingTop = styles.paddingTop;
    mirror.style.paddingRight = styles.paddingRight;
    mirror.style.paddingBottom = styles.paddingBottom;
    mirror.style.paddingLeft = styles.paddingLeft;
    mirror.style.borderTopWidth = styles.borderTopWidth;
    mirror.style.borderRightWidth = styles.borderRightWidth;
    mirror.style.borderBottomWidth = styles.borderBottomWidth;
    mirror.style.borderLeftWidth = styles.borderLeftWidth;
}

function adjustTextareaHeight(textarea: HTMLTextAreaElement, mirror: HTMLDivElement): void {
    // Get current value and ensure it's a string
    const value = textarea.value || textarea.placeholder || ' ';
    
    // Update mirror content with the current value
    // Preserve line breaks and spaces
    mirror.textContent = value + ' '; // Add space to ensure minimum height
    
    // Update the textarea's height to match the mirror's scrollHeight
    const height = mirror.scrollHeight;
    textarea.style.height = height + 'px';
    
    // Trigger custom event when resized - compatible with jQuery event system
    $(textarea).trigger('autosize:resized');
}

function setupTextarea(textarea: HTMLTextAreaElement): AutosizeInstance {
    if (instances.has(textarea)) {
        return instances.get(textarea)!;
    }
    
    const mirror = createMirror(textarea);
    const instance: AutosizeInstance = {
        textarea,
        mirror,
        destroy: () => {
            if (mirror.parentNode) {
                mirror.parentNode.removeChild(mirror);
            }
            textarea.removeEventListener('input', instance.inputListener);
            textarea.removeEventListener('scroll', instance.scrollListener);
            if (instance.resizeObserver) {
                instance.resizeObserver.disconnect();
            }
            instances.delete(textarea);
        }
    };
    
    // Setup event listeners
    const handleInput = () => {
        adjustTextareaHeight(textarea, mirror);
    };
    
    const handleScroll = () => {
        if (textarea.scrollTop > 0) {
            textarea.scrollTop = 0;
        }
    };
    
    instance.inputListener = handleInput;
    instance.scrollListener = handleScroll;
    
    textarea.addEventListener('input', handleInput);
    textarea.addEventListener('scroll', handleScroll);
    
    // Setup resize observer to handle dynamic width changes
    if (window.ResizeObserver) {
        const resizeObserver = new ResizeObserver(() => {
            updateMirrorStyles(textarea, mirror);
            adjustTextareaHeight(textarea, mirror);
        });
        resizeObserver.observe(textarea);
        instance.resizeObserver = resizeObserver;
    }
    
    instances.set(textarea, instance);
    
    // Set initial height
    adjustTextareaHeight(textarea, mirror);
    
    return instance;
}

function autosizeInitialize(elements: AutosizeElement): void {
    if (elements instanceof $) {
        elements.each((_index, el) => {
            if (el instanceof HTMLTextAreaElement) {
                setupTextarea(el);
            }
        });
    } else if (elements instanceof HTMLTextAreaElement) {
        setupTextarea(elements);
    }
}

function autosizeUpdate(elements: AutosizeElement): void {
    if (elements instanceof $) {
        elements.each((_index, el) => {
            if (el instanceof HTMLTextAreaElement) {
                const instance = instances.get(el);
                if (instance) {
                    adjustTextareaHeight(instance.textarea, instance.mirror);
                }
            }
        });
    } else if (elements instanceof HTMLTextAreaElement) {
        const instance = instances.get(elements);
        if (instance) {
            adjustTextareaHeight(instance.textarea, instance.mirror);
        }
    }
}

function autosizeDestroy(elements: AutosizeElement): void {
    if (elements instanceof $) {
        elements.each((_index, el) => {
            if (el instanceof HTMLTextAreaElement) {
                const instance = instances.get(el);
                if (instance) {
                    instance.destroy();
                }
            }
        });
    } else if (elements instanceof HTMLTextAreaElement) {
        const instance = instances.get(elements);
        if (instance) {
            instance.destroy();
        }
    }
}

// Public API matching the original autosize library exactly
const autosize = (elements: AutosizeElement): void => {
    autosizeInitialize(elements);
};

autosize.update = autosizeUpdate;
autosize.destroy = autosizeDestroy;

// Default export
export default autosize;