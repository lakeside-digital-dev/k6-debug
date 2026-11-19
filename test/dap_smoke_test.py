#!/usr/bin/env python3
"""End-to-end DAP test for the k6-debug binary (stdlib only).

Usage: python3 test/dap_smoke_test.py /path/to/k6-debug

Starts a local HTTP server, runs `k6-debug run test/smoke.ts` with
K6_DEBUG_DAP=127.0.0.1:0, reads the port from the "DAP server listening on"
line and drives a session: breakpoint, variables (incl. setup() data),
step over, step in, step out, evaluate, continue.
"""
import http.server, json, os, re, socket, subprocess, sys, threading

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "smoke.ts")
BP_LINE = 19          # const url = buildUrl(base, data.token);
IN_BUILD_URL = 9      # const url = `${base}/ping?t=${token}`;  (inside buildUrl)
AFTER_BP = 20         # const res = http.get(url);


class Ping(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers(); self.wfile.write(b"pong")

    def log_message(self, *a):
        pass


def main(binary):
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Ping)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    env = dict(os.environ, K6_DEBUG_DAP="127.0.0.1:0",
               BASE_URL="http://127.0.0.1:%d" % srv.server_address[1])
    proc = subprocess.Popen([binary, "run", "--quiet", SCRIPT], env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)

    port = None
    for line in proc.stderr:
        m = re.search(r"DAP server listening on .*:(\d+)", line)
        if m:
            port = int(m.group(1)); print("handshake:", line.strip()); break
    assert port, "no 'DAP server listening on' line"
    threading.Thread(target=lambda: [sys.stderr.write("k6: " + l) for l in proc.stderr], daemon=True).start()

    s = socket.create_connection(("127.0.0.1", port)); f = s.makefile("rb"); seq = [0]

    def send(cmd, args=None):
        seq[0] += 1
        body = json.dumps({"seq": seq[0], "type": "request", "command": cmd, "arguments": args or {}}).encode()
        s.sendall(b"Content-Length: %d\r\n\r\n" % len(body) + body)
        return seq[0]

    def recv():
        n = 0
        while True:
            l = f.readline().strip()
            if not l: break
            if l.lower().startswith(b"content-length"): n = int(l.split(b":")[1])
        return json.loads(f.read(n))

    def wait(pred):
        while True:
            m = recv()
            print("<<", json.dumps(m)[:300])
            if pred(m): return m

    def req(cmd, args=None):
        r = send(cmd, args); print(">>", cmd, json.dumps(args or {}))
        return wait(lambda m: m.get("request_seq") == r)

    def stopped_line(tid):
        wait(lambda m: m.get("event") == "stopped")
        return req("stackTrace", {"threadId": tid})["body"]["stackFrames"][0]

    def variables(frame_id):
        scopes = req("scopes", {"frameId": frame_id})["body"]["scopes"]
        return {v["name"]: v for v in req("variables", {"variablesReference": scopes[0]["variablesReference"]})["body"]["variables"]}

    req("initialize", {"adapterID": "k6", "linesStartAt1": True})
    req("attach", {})
    bp = req("setBreakpoints", {"source": {"path": SCRIPT}, "breakpoints": [{"line": BP_LINE}]})
    assert bp["body"]["breakpoints"][0]["verified"]
    req("configurationDone")

    st = wait(lambda m: m.get("event") == "stopped")
    tid = st["body"]["threadId"]
    frame = req("stackTrace", {"threadId": tid})["body"]["stackFrames"][0]
    assert frame["line"] == BP_LINE and frame["source"]["path"] == SCRIPT, frame
    vs = variables(frame["id"])
    assert "data" in vs and "abc123" in vs["data"]["value"], vs
    assert vs["data"]["variablesReference"] > 0
    kids = {v["name"]: v for v in req("variables", {"variablesReference": vs["data"]["variablesReference"]})["body"]["variables"]}
    assert kids["token"]["value"] == '"abc123"', kids
    ev = req("evaluate", {"expression": "data.user.id", "frameId": frame["id"]})
    assert ev["success"] and ev["body"]["result"] == "7", ev

    req("next", {"threadId": tid})                       # step over buildUrl()
    frame = stopped_line(tid)
    assert frame["line"] == AFTER_BP, "step over went to %s" % frame["line"]
    assert "url" in variables(frame["id"])

    req("setBreakpoints", {"source": {"path": SCRIPT}, "breakpoints": []})
    req("continue", {"threadId": tid})
    proc.wait(timeout=60)
    assert proc.returncode == 0, proc.returncode
    print("PASS: breakpoint line %d, data=%s, step over -> line %d, exit 0" % (BP_LINE, vs["data"]["value"], AFTER_BP))


def main_step_in(binary):
    """Second run: step in / step out around buildUrl()."""
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Ping)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    env = dict(os.environ, K6_DEBUG_DAP="127.0.0.1:0",
               BASE_URL="http://127.0.0.1:%d" % srv.server_address[1])
    proc = subprocess.Popen([binary, "run", "--quiet", SCRIPT], env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    port = next(int(m.group(1)) for m in (re.search(r"listening on .*:(\d+)", l) for l in proc.stderr) if m)
    threading.Thread(target=lambda: [l for l in proc.stderr], daemon=True).start()
    s = socket.create_connection(("127.0.0.1", port)); f = s.makefile("rb"); seq = [0]

    def send(cmd, args=None):
        seq[0] += 1
        body = json.dumps({"seq": seq[0], "type": "request", "command": cmd, "arguments": args or {}}).encode()
        s.sendall(b"Content-Length: %d\r\n\r\n" % len(body) + body); return seq[0]

    def recv():
        n = 0
        while True:
            l = f.readline().strip()
            if not l: break
            if l.lower().startswith(b"content-length"): n = int(l.split(b":")[1])
        return json.loads(f.read(n))

    def wait(pred):
        while True:
            m = recv()
            if pred(m): return m

    def req(cmd, args=None):
        r = send(cmd, args); return wait(lambda m: m.get("request_seq") == r)

    def line_after_stop(tid):
        wait(lambda m: m.get("event") == "stopped")
        return req("stackTrace", {"threadId": tid})["body"]["stackFrames"][0]

    req("initialize", {"adapterID": "k6"}); req("attach")
    req("setBreakpoints", {"source": {"path": SCRIPT}, "breakpoints": [{"line": BP_LINE}]})
    req("configurationDone")
    tid = wait(lambda m: m.get("event") == "stopped")["body"]["threadId"]
    req("stepIn", {"threadId": tid})
    fr = line_after_stop(tid)
    assert fr["line"] == IN_BUILD_URL and fr["name"].startswith("buildUrl"), fr
    req("stepOut", {"threadId": tid})
    fr = line_after_stop(tid)
    assert fr["line"] == AFTER_BP, fr
    req("disconnect")
    proc.wait(timeout=60)
    assert proc.returncode == 0, proc.returncode
    print("PASS: step in -> %s line %d, step out -> line %d" % (fr["name"], IN_BUILD_URL, AFTER_BP))


if __name__ == "__main__":
    binary = os.path.abspath(sys.argv[1])
    main(binary)
    main_step_in(binary)
    leftovers = [n for n in os.listdir(HERE) if ".k6debug." in n]
    assert not leftovers, leftovers
    print("PASS: no instrumented copy left behind")
