Django RT - realtime web for django
===================================

`django_rt` is a Django application to enable realtime web programming for
Django. It relies heavily on [socket.io](socket.io) and [jQuery](jquery.com)
and is inspired by [Meteor](meteor.com).

Current satus
-------------

Very very alpha, but hard work is being put in.

Dependencies
------------

 * [Redis](redis.io) - message backend
 * [Node](nodejs.org) - message server
 * [socket.io](socket.io) - websocket support

Installation
------------

TODO: create proper `setup.py`

Usage
-----

Write a class based view handler subclass from `RTView` for you base page.

`example.html`:
	
	<!doctype html>
	<html>
		<head><title>Example</title></head>
		<body>
			<ul>
			{% for entry in entries %}
				<li>{{entry}}</li>
			{% endfor %}
			</ul>
			<input type="text" id="myinput">
			<button id="mybutton">Click</button>
			<div id="result"></div>
		</body>
	</html>

`views.py`:

	class ExampleView(RTView):
		template_name = 'example.html'
		def get_context_data(self, **kwargs):
			context = super(ExampleView, self).get_context_data(**kwargs)
			context['entries'] = ['a', 'b', 'c']

Add client side event handlers to your view handler:

	# instance method of your view
	@RTView.event('click', '#mybutton')
	def mybutton_click(self, request, gathered='#myinput'):
		return RTResponse('#result', 'Result: '+gathered)

The above event handler will be invoked when the `click` event from the DOM
node with `id` equal to `mybutton` is emitted. The value of the DOM node with
`id` equal to `myinput` is supplied and will be transfered through the
`gathered` keyword argument. Yes, the default value of this argument is used
to determine the jQuery query string to gather desired information.

RTContext and Models
--------------------

The `RTContext` class is a subclass of Django's `TemplateContext` with the
extra feature of inspecting the context before the template gets rendered and
replacing Models and Queries with `RTModelProxy`.

`RTModelProxy` class documentation states:

    '''
    A proxy for Model instances. After inspecting the template context
    any Model instance will be wrapped in an instance of RTModelProxy.
    The proxy does no modifications to the Model or data it wraps any
    attribute retrieved into a string:
        "<!--`object-identifier`-->`original`<!--/`object-identifier`-->
    so the client side script can relocate and modify its value when
    database entries change.
    '''

`django_rt` uses signals to keep track and hook into database changes. It
will automatically update clients with the new data. Consider the following
example.


	class Entry(models.Model):
		name = models.CharField(max_length=20)
		def __unicode__(self):
			return unicode(self.name)

	class ModelExampleView(RTView):
		template_name = 'example.html'
		def get_context_data(self, **kwargs):
			context = super(ExampleView, self).get_context_data(**kwargs)
			context['entries'] = Entry.objects.all()

Now add some entries and fire up the page in your browser. Keep it open while
you make changes to the viewed entries and observe it change realtime in your
browser.

TODO: Implement proper handling of `QuerySet` instances and database
deletion and addition.
