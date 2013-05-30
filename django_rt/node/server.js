var redis = require('redis'),
    app = require('http').createServer(handler),
    io = require('socket.io').listen(app);

var SOCK_TIMEOUT = 1000*60*60; // 1 hour

app.listen(8887);

queues = {};

function handler (req, res) {
    res.writeHead(404);
    res.end('Not found');
}

function poll(queue_name, redis_client) {
    redis_client.blpop(queue_name, 0, function(err, data){
        console.warn('Found data in queue: ' + 
		     queue_name + 
		     '\n    data: ' + 
		     data);
	if(data!==undefined){
	    queues[queue_name].last_update = new Date();
            io.sockets.in(queue_name).emit(queue_name, data[1])
	}
    });
}

io.sockets.on('connection', function (socket) {
    console.warn('New connection');
    var queue_name = null;
    socket.on('client', function (data){
        queue_name = data['queue_name'];
        console.warn('New client -> '+queue_name);
        socket.join(queue_name);
        
        if(!queues[queue_name]){
            var redis_client = redis.createClient();
            redis_client.on("error", function (err) {
                console.log("Error " + err);
            });
            var interval = setInterval(function () {
                poll(queue_name, redis_client);
            }, 100);
            queues[queue_name] = {
                interval:interval,
                redis_client:redis_client,
		last_update:new Date()
            };
        }
    });
    socket.on('disconnect', function () {
        if(queue_name!=null){
            console.warn('Disconnected '+queue_name);
            client_list = io.sockets.clients(queue_name);
            if(client_list.length==0){
		purge_socket(queues[queue_name]);
            }
        }
    });
});

function purge_socket(sock_obj){
    console.warn('purging socket: '+sock_obj);
    clearInterval(sock_obj.interval);
    sock_obj.redis_client.end();
    sock_obj = null;
}

function check_timeouts(){
    var date_now = new Date();
    for(k in queues){
	if(date_now - queues[k].last_update > SOCK_TIMEOUT){
	    purge_socket(queues[k]);
	}
    }
}

setInterval(function(){
    check_timeouts();
}, 60000);