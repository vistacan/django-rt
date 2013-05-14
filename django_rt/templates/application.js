//{% comment %}
//THIS IS A DJANGO TEMPLATE!!

// Template tags and blocks are mostly commented out
// to improve readability but this document should
// be refactored.

// TODO: improve networking events, `reconnect` and
// `react` when connection is lost.

//{% endcomment %}


// Collects the value from a jQuery std query
// Used to collect client side data sent to the
// server to fuel RTView.event decorated functions
function getValue(query, scope){
    if(query=='$(this)'){
	return getValue(scope);
    }
    var val = $(query).val();
    if(val){
        return val;
    }
    val = $(query).text();
    if(val){
        return val;
    }
    return $(query).html();
}


// The list of DOM elements that might update when
// a database change message is sent.
var watchlist={};


// The socket connected to the server
var socket=null;


// Collection of client side events
var events = {};


// Initialize the connection to the server
function init_socket(){
    // {% comment %}
    // Connect to the socket.io server
    // TODO: Get server info from the settings
    // {% endcomment %}
    
    socket = io.connect('//'+document.domain+':8887');
    
    socket.on('connect', function(){
        // Send this client's channel name to the server
        // to initiate the connection
        console.log('Emitting channel name:{{channel}}');
        socket.emit('client', {queue_name: '{{channel}}'});
        
        // Respond to messages send from the server
        socket.on('{{channel}}', function (data) {
            eval('data = '+data);
            if(data['message']){
                console.log('Received message: '+data['message']); // --> HI
            } else {
                // This is not a message
                // Update the DOM
                for(k in data){
                    console.log('Updating '+k+' -> '+data[k]);
                    update_watched_object(data[k], k);
                }
            }
        });
    });
}


// Update DOM elements identified by `identifier` with `obj` values
function update_watched_object(obj, identifier){
    // example: update_watched_object({name:'foo'}, 'django_rt%test%2');
    if(identifier=='emit'){
	if(''+obj in events){
	    events[''+obj](true);
	}
    } else {
	for(k in watchlist){
            // k is of format '<app_label>%<model_name>%<pk>%<field_name>'
            // but the `identifier` does not contian the field name
            // it identifies the full obj which is a model instance repr or
	    // an object ({emit:'event_id'}) 
	    // in case a query was updated
            if(k.indexOf(identifier)==0){
		// get the field name and update the DOM
		field_name = k.replace(identifier, '').substring(1);
		// the element is a text element so we use `data`
		watchlist[k].data = obj[field_name];
	    }
        }
    }
}


// This function walks over all the DOM nodes in the jqresult
// including its children and children's children to collect
// nodes that require watching - their format is:
//   <#Comment> <#Text> <#Comment>
// and the comment nodes exactly contain:
//   /<!--\/?P<app_label>(.*)%P<model_name>(.*)\
//   %P<pk>(.*)%P<field_name>(.*)-->/
function build_watchlist(jqresult){
    var ostr = null,        // the opening comment
        elem = null,        // the current element
        data_elem = null,   // the text element
        match = null,       // the data matched againts /\%/g
        conts = jqresult.contents();
        
    for(var i=0; i<conts.length; i++){
        elem = conts[i];
	if(elem && elem.data){
	    match = elem.data.match(/\%/g) || [];
	} else {
	    match = [];
	}
        if(
           elem.nodeType === 8 && // comment
           ostr == null &&
           match.length == 3 // format check
        ){
            // found the opening comment tag
            ostr = elem.data;
        } else if(
            elem.nodeType === 8 && // comment
            ostr != null &&
            elem.data == '/'+ostr
        ){
	    if(data_elem == null){
		console.log('TODO: Must handle empty data elements!');
	    }
            // found the closing comment tag
            // store this occurence
            watchlist[ostr] = data_elem;
            ostr = null;
            data_elem = null;
        } else if(
            ostr != null &&
            elem.nodeType === 3
        ){
            // found the tag containing the actual data
            data_elem = elem;
        } else if(
            elem.nodeType != 3 &&
            elem.nodeType != 8
        ){
            // not finding anything, go into elem recursive
            build_watchlist($(elem));
        }
    }
}

// Main initializer function for Django RT.
// This function is executed after each event!
function rtinit(load_body){

    var document_url = ''+ document.location;

    // Listen to all client side events registered
    // using the RTView.event decorator.
    
    // for{ {% for event_dict in events %}
        // for{ {% for event_id, event_tuple in event_dict.iteritems %}
            // event_id -> (
            //     self_, func, name, query, dict(zip(args, defaults)))
    events['{{event_id}}'] = 
	function(fireIt){
	    if(!fireIt){
		$('{{event_tuple.3}}').one(
		    '{{event_tuple.2}}', 
		    {},
		    function(eventObject){
		
			var headers = {},
			csrf = $.cookie('csrftoken');
                    
			headers['X-CSRFToken'] = csrf;
			headers['X-Event-Id'] = '{{event_id}}';
    
			// Collect the required data to be send to the server
			// as specified inside the server side registered event 
			// handler function with keyword arguments and default 
			// values
			var data = {};
			// for{ {% for k, v in event_tuple.4.iteritems %}
			data['{{k}}'] = getValue('{{v}}', this);
			// } {% endfor %}
			
			$.ajax({
			    url: document_url,
			    type: 'POST',
			    dataType: 'json',
			    headers: headers,
			    data: data,
			    success: function(data, textStatus, jqXHR) {
				data = eval(data);
				$(data['target_query']).html(data['body']);
				rtinit(); // re-init
			    },
			    error: function(request, status, error) { 
				if(request.responseText)
				    alert(request.responseText); 
				else
				    rtinit();
			    }
			});

			return false;
		    });
	    } else {
		$('{{event_tuple.3}}').trigger('{{event_tuple.2}}');
	    }
	};
        // } {% endfor %}
    // } {% endfor %}

    for(event_id in events){
	events[event_id]();
    }

    build_watchlist($('body'));

    if(load_body){
	$('body').trigger('load');
    }

    $('body').trigger('inited');
}

$(function(){
    rtinit(true);
});