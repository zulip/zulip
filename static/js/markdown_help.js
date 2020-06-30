const markdown = require('./markdown');
exports.render_markdown = () => {
    let unrendered_text;
    let obj;
    $.each($(".apply_markdown"), function (id, element) {
        unrendered_text = element.textContent;
        obj = {
            raw_content: unrendered_text,
        };
        markdown.apply_markdown(obj);
        $(element).next().append(obj.content);
    }
    );
};
