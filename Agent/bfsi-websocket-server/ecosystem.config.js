module.exports = {
  apps: [
    {
      name: "bfsi-ws-server",
      cwd: "/home/koushik/Agent/bfsi-websocket-server",
      script: "server.py",
      interpreter: "python3",
      autorestart: true,
      watch: false,
      max_memory_restart: "300M",
      env: {
        LOG_LEVEL: "INFO",
      },
      error_file: "/home/koushik/Agent/bfsi-websocket-server/logs/err.log",
      out_file: "/home/koushik/Agent/bfsi-websocket-server/logs/out.log",
      merge_logs: true,
    },
  ],
};
