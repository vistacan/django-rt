'''
This module defines the RTMiddleware responsible for injecting
the required javascript files:
   jQuery - www.jquery.org
   jQuery cookie - a plugin to handle cookies used to prevent CSRF
   util.js - Utility functions
   application.js - Main javascript entry
   socket.io.js - socket.io client script
   
TODO: retrieve file paths from settings
'''

from django.core.urlresolvers import reverse


RT_SCRIPT = '''
<script type="text/javascript" src="//ajax.googleapis.com/ajax/libs/jquery/2.0.0/jquery.min.js"></script>
<script type="text/javascript" src="/static/jquery.cookie.js"></script>
<script type="text/javascript" src="/static/util.js"></script>
<script type="text/javascript">
    script("%s", function(){
        console.log('Loaded: application.js');
        script("//"+document.domain+":8080/socket.io/socket.io.js", function(){
            console.log('Loaded: socket.io.js');
            init_socket();
        });
    });
</script>
''' % reverse('application_js')


class RTMiddleware(object):
    def process_response(self, request, response):
        pos = response.content.find('</head>')
        if pos != -1:
            response.content = response.content[:pos] + RT_SCRIPT + response.content[pos:]
        return response