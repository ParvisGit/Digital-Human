module.exports = {
  apps: [
    {
      name: "banking-grpc",
      cwd: "/home/giniiris_voice/AI_secondary_folder/Digital-Human/Agent/Banking_agent",
      script: "run_grpc.py",
      interpreter: "/home/giniiris_voice/AI_secondary_folder/Digital-Human/Agent/Banking_agent/venv1/bin/python",
      autorestart: true,
      watch: false,
      max_memory_restart: "500M",
      env: {
        LOG_LEVEL: "INFO",
        GRPC_PORT: "8008",
        GOOGLE_APPLICATION_CREDENTIALS: "/home/giniiris_voice/AI_secondary_folder/Digital-Human/Agent/vertex-gemini-agent.json",
      },
      error_file: "/home/giniiris_voice/AI_secondary_folder/Digital-Human/Agent/Banking_agent/logs/grpc-err.log",
      out_file: "/home/giniiris_voice/AI_secondary_folder/Digital-Human/Agent/Banking_agent/logs/grpc-out.log",
      merge_logs: true,
    },
    {
      name: "banking-streamlit",
      cwd: "/home/giniiris_voice/AI_secondary_folder/Digital-Human/Agent/Banking_agent",
      script: "/home/giniiris_voice/AI_secondary_folder/Digital-Human/Agent/Banking_agent/venv1/bin/streamlit",
      args: "run streamlit_app.py --server.port 8502 --server.address 0.0.0.0",
      interpreter: "none",
      autorestart: true,
      watch: false,
      max_memory_restart: "300M",
      env: {
        GRPC_SERVER: "localhost:8008",
        LOG_LEVEL: "INFO",
      },
      error_file: "/home/giniiris_voice/AI_secondary_folder/Digital-Human/Agent/Banking_agent/logs/streamlit-err.log",
      out_file: "/home/giniiris_voice/AI_secondary_folder/Digital-Human/Agent/Banking_agent/logs/streamlit-out.log",
      merge_logs: true,
    },
  ],
};
