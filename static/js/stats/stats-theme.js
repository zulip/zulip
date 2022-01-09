//  function to set theme for stats page
function setTheme(theme){
    
    'use strict';

    if(theme === "dark-theme"){        
        document.querySelector('body').classList.remove('color-scheme-automatic');
        document.querySelector('body').classList.add('dark-theme');

    }
    else{
        document.querySelector('body').classList.remove('dark-theme');
        document.querySelector('body').classList.add('color-scheme-automatic');
    }
}


//  Reading value of theme
const theme = localStorage.getItem('theme-value');
setTheme(theme);