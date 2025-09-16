const NodeMediaServer = require('node-media-server');

const config = {
  rtmp: {
    port: 1935
  }
};

const nms = new NodeMediaServer(config);
nms.run();

console.log('Simple RTMP Server started on port 1935');

// 5秒後にポート確認
setTimeout(() => {
  const net = require('net');
  const server = net.createServer();
  
  server.listen(1935, (err) => {
    if (err) {
      console.log('Port 1935 is already in use - GOOD');
    } else {
      console.log('Port 1935 is NOT in use - BAD');
      server.close();
    }
  });
  
  server.on('error', (err) => {
    if (err.code === 'EADDRINUSE') {
      console.log('Port 1935 is in use - RTMP server working');
    }
  });
}, 5000);
