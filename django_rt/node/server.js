var redis = require('redis'),
    app = require('http').createServer(handler),
    io = require('socket.io').listen(app);

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
                redis_client:redis_client
            };
        }
    });
    socket.on('disconnect', function () {
        if(queue_name!=null){
            console.warn('Disconnected '+queue_name);
            client_list = io.sockets.clients(queue_name);
            if(client_list.length==0){
                clearInterval(queueus[queue_name].interval);
                queues[queue_name].redis_client.end();
                queues[queue_name] = false;
            }
        }
    });
});