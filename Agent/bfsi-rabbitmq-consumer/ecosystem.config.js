module.exports = {
  apps: [
    {
      name: "bfsi-rmq-consumer",
      cwd: "/home/giniiris_voice/AI_Backend/Digital-Human/Agent/bfsi-rabbitmq-consumer",
      script: "consumer.py",
      interpreter: "python3",
      autorestart: true,
      watch: false,
      max_memory_restart: "300M",
      env: {
        LOG_LEVEL: "INFO",
      },
      error_file: "/home/giniiris_voice/AI_Backend/Digital-Human/Agent/bfsi-rabbitmq-consumer/logs/err.log",
      out_file: "/home/giniiris_voice/AI_Backend/Digital-Human/Agent/bfsi-rabbitmq-consumer/logs/out.log",
      merge_logs: true,
    },
  ],
};
