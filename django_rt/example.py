from views import RTView, RTResponse
from models import Test


class ExampleView(RTView):
    
    template_name = "example.html"
    
    def get_context_data(self, **kwargs):
        context = super(ExampleView, self).get_context_data(**kwargs)
        context['test_entries'] = Test.objects.all()
        return context
    
    @RTView.event('click', '#mybutton')
    def mybutton_click(self, request, myinput='#myinput'):
        return RTResponse('#result', 'Result! '+myinput)