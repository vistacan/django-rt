var redis = require('redis'),
    app = require('http').createServer(handler),
    io = require('socket.io').listen(app);

app.listen(8080);

function handler (req, res) {
    res.writeHead(404);
    res.end('Not found');
}

function poll(socket, queue_name, redis_client) {
    redis_client.blpop(queue_name, 0, function(err, data){
        console.warn('Found data in queue: ' + queue_name + '\n    data: ' + data);
        socket.emit(queue_name, data[1]);
    });
}

io.sockets.on('connection', function (socket) {
    console.warn('New connection');
    var queue_name = null;
    var interval = null;
    var redis_client = redis.createClient();
    redis_client.on("error", function (err) {
        console.log("Error " + err);
    });
    socket.on('client', function (data){
        queue_name = data['queue_name'];
        console.warn('New client -> '+queue_name);
        interval = setInterval(function () {
            poll(socket, queue_name, redis_client);
        }, 100);
    });
    socket.on('disconnect', function () {
        if(queue_name!=null){
            console.warn('Disconnected '+queue_name);
        }
        if(interval!=null){
            clearInterval(interval);
            interval = null;
        }
        if(redis_client!=null){
            redis_client.end();
            redis_client = null;
        }
    });
});