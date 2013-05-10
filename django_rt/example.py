from views import RTView, RTTemplateResponse, RTObservable
from models import Test

from django.template import Template


class ExampleView(RTView):
    
    template_name = "example.html"
    
    def get_context_data(self, **kwargs):
        context = super(ExampleView, self).get_context_data(**kwargs)
        context['title'] = RTObservable('title', {'value':'Hello'})
        return context
    
    @RTView.event('click', '#mybutton')
    def mybutton_click(self, request, myinput='#myinput'):
        
        RTObservable('title', {'value':myinput}).set_changed()

        return RTTemplateResponse(
            request,
            Template(
                '''<tbody>
                {% for entry in test_entries %}
                <tr><td>{{entry.name}}</td></tr>
                {% endfor %}
                </tbody>'''
            ),
            {
                'test_entries': Test.objects.all(),
            },
            target_query='.table',
        )