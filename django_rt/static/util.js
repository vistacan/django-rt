function script(url, callback) {
    var s = document.createElement('script');
    s.type = 'text/javascript';
    s.async = true;
    s.src = url;
    if(callback){
        s.addEventListener('load', function(e){ callback(); });
    }
    var x = document.getElementsByTagName('head')[0];
    x.appendChild(s);
}