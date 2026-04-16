#!/usr/bin/env node
// Free a TCP port by killing whichever process holds it.
// Used as a pre-step for `electron:dev` so stale dev servers (orphaned vite /
// electron children from a prior crash) can't block port 5173, which would
// otherwise make `wait-on` hang forever and make the Electron window never
// appear. Mirrors the 8080 auto-kill pattern in src/channels/desktop.py.

const { execSync } = require('child_process');

const port = Number(process.argv[2]);
if (!Number.isInteger(port) || port <= 0) {
  console.error(`free-port: invalid port "${process.argv[2]}"`);
  process.exit(1);
}

function killPids(pids) {
  for (const pid of pids) {
    try {
      if (process.platform === 'win32') {
        execSync(`taskkill /F /PID ${pid}`, { stdio: 'ignore' });
      } else {
        execSync(`kill -9 ${pid}`, { stdio: 'ignore' });
      }
      console.log(`[free-port] killed pid ${pid} holding :${port}`);
    } catch {
      // Process may already be gone or we lack permission — not fatal.
    }
  }
}

try {
  if (process.platform === 'win32') {
    // NOTE: No `-p tcp` — that only returns IPv4. Vite's Node http server
    // often listens on IPv6 [::1] and would be missed. Plain `netstat -ano`
    // includes both TCP and TCPv6.
    const out = execSync(`netstat -ano`, { encoding: 'utf8' });
    const pids = new Set();
    for (const line of out.split(/\r?\n/)) {
      // e.g. "  TCP    [::1]:5173    [::]:0   LISTENING    268"
      //      "  TCP    127.0.0.1:5173    0.0.0.0:0   LISTENING    268"
      const m = line.match(/\s(?:\[[^\]]+\]|\d+\.\d+\.\d+\.\d+):(\d+)\s+\S+\s+LISTENING\s+(\d+)/);
      if (m && Number(m[1]) === port) pids.add(m[2]);
    }
    if (pids.size) killPids([...pids]);
  } else {
    const out = execSync(`lsof -ti tcp:${port}`, { encoding: 'utf8' }).trim();
    if (out) killPids(out.split(/\s+/));
  }
} catch {
  // No listener on port — nothing to do.
}
