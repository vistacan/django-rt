from views import RTView, RTTemplateResponse, RTObservable
from models import Test

from django.template import Template


class ExampleView(RTView):
    
    template_name = "example.html"
    
    def get_context_data(self, **kwargs):
        context = super(ExampleView, self).get_context_data(**kwargs)
        context['test_entries'] = Test.objects.all()
        context['title'] = RTObservable('title', {'value':'Hello'})
        return context
    
    @RTView.event('click', '#mybutton')
    def mybutton_click(self, request, myinput='#myinput'):
        
        RTObservable('title', {'value':myinput}).set_changed()

        return RTTemplateResponse(
            request,
            Template('<div class="well">Result! {{result}}</div>'),
            {'result': myinput},
            target_query='#result',
        )