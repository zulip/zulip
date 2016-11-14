(function () {
    var data = {
        ui: null,
        templates: null,
        template_ui: null
    };
    
    $.get("../public/templates/components.html", function (response) {
        data.templates = document.createElement("div");
        data.templates.innerHTML = response;
        
        run();
    });
    
    $.get("../public/views/ui.html", function (response) {
        data.template_ui = document.createElement("div");
        data.template_ui.innerHTML = response;
        
        run();
    });

    $.get("public/views/templates.html", function (response) {
        data.ui = document.createElement("div");
        data.ui.innerHTML = response;
        
        run();
    });
    
    var run = function () {
        var flag = Object.keys(data).filter(function (o) {
            return data[o];
        }).length === Object.keys(data).length;

        if (flag) {
            main(data); 
            events(); 
        }
    };
}());