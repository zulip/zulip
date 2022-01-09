//function to set theme for stats page
function setTheme(theme){
    if(theme == "dark-theme"){
        // document.body.removeClass("color-scheme-automatic").addClass("dark-theme");
        document.querySelector('body').classList.remove('color-scheme-automatic');
        document.querySelector('body').classList.add('dark-theme');

    }
    else{
        // document.body.removeClass("dark-theme").addClass("color-scheme-automatic");
        document.querySelector('body').classList.remove('dark-theme');
        document.querySelector('body').classList.add('color-scheme-automatic');
    }
}


//Reading value of theme
let theme = localStorage.getItem('theme-value');
setTheme(theme);