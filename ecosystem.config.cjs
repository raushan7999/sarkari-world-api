/*
 * PM2 process config.
 *
 * PM2 runs ONE process here and uvicorn forks its own workers (`WORKERS`).
 * Letting both fork would multiply the count and, more importantly, multiply
 * database connections: each uvicorn worker owns a pool, so total connections
 * are WORKERS x (DB_POOL_SIZE + DB_MAX_OVERFLOW).
 *
 * Secrets are NOT set here — this file is committed. SESSION_SECRET and
 * DATABASE_URL are read from the gitignored .env in the project root.
 */
module.exports = {
	apps: [
		{
			name: "sarkariworld-api-py",
			// The venv binary directly, not `uv run`: an extra wrapper process
			// makes PM2 restart and stop signal the wrong pid.
			script: ".venv/bin/uvicorn",
			interpreter: "none",
			args: [
				"sarkariworld.main:app",
				"--host", "127.0.0.1",
				"--port", "8000",
				"--workers", "4",
				"--proxy-headers",
				"--forwarded-allow-ips", "127.0.0.1",
			].join(" "),
			exec_mode: "fork",
			instances: 1,
			max_memory_restart: "500M",
			// Give in-flight requests time to finish before SIGKILL.
			kill_timeout: 5000,
			env: {
				ENVIRONMENT: "production",
				TZ: "Asia/Kolkata",
				LOG_JSON: "true",
				BEHIND_TLS_PROXY: "true",
			},
			out_file: "./logs/api-out.log",
			error_file: "./logs/api-error.log",
			merge_logs: true,
			time: false, // structlog already stamps every line
		},
	],
};
