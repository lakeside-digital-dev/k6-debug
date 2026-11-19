# k6-debug

A k6 binary with a built-in debugger (Debug Adapter Protocol server) for k6
test scripts written in JavaScript or TypeScript: breakpoints, variables
(including the `setup()` data), step over / into / out.

It is used by the **k6 Load Testing** plugin for JetBrains IDEs, which
downloads the matching binary from this repository's releases. It can be used
with any DAP client.

This project is a fork of [nhancdt2602/xk6-debug](https://github.com/nhancdt2602/xk6-debug)
(MIT, see [LICENSE](LICENSE)). Thanks to its author for the original
extension. Changes in this fork:

- TypeScript scripts (`.ts`, `.mts`, `.cts`) are instrumented; types are kept and stripped by k6.
- Function parameters are captured, so `data` returned by `setup()` is visible.
- Instrumentation runs inside the binary (Babel bundled and executed with sobek) — no Node.js needed.
- Step over respects the call depth; step in / step out added; stopped events carry `step`/`breakpoint`.
- `evaluate` for variable names and property paths (`data.user.id`, `res.headers["Content-Type"]`).
- `K6_DEBUG_DAP=127.0.0.1:0` picks a free port and prints it; VUs resume if the client goes away.
- Release binaries for linux/darwin (amd64, arm64) and windows (amd64), with `SHA256SUMS`.

Not affiliated with or endorsed by Grafana Labs. k6 is a trademark of Grafana Labs.

## License and source

- The extension code in this repository is MIT licensed ([LICENSE](LICENSE)).
- **k6 is AGPL-3.0; this binary bundles k6, source here:**
  [github.com/grafana/k6](https://github.com/grafana/k6) (each release names the exact k6 tag;
  current: [v2.4.0](https://github.com/grafana/k6/tree/v2.4.0)). The binaries are built
  unmodified from that tag plus this repository by the [release workflow](.github/workflows/release.yml).

## Usage

```bash
K6_DEBUG_DAP=127.0.0.1:0 k6-debug run script.ts
# stderr: [k6-debug] DAP server listening on 127.0.0.1:41234
```

Connect a DAP client to the printed port (TCP, `Content-Length` framing), send
`initialize`, `attach`, `setBreakpoints` (absolute path of the original
script), `configurationDone`. VUs wait until `configurationDone`.

The script is instrumented automatically: an instrumented copy
`.<name>.k6debug.<ext>` is written next to it (so relative imports and `open()`
work) and deleted as soon as k6 has loaded it. Only the main script is
instrumented; breakpoints in imported local modules are not supported.

Environment variables:

| Variable | Meaning |
|---|---|
| `K6_DEBUG_DAP` | `host:port` for the DAP server (`127.0.0.1:0` = free port). Without it, `k6-debug` behaves like k6 (plus the CLI mode of the original extension). |
| `K6_DEBUG_NO_INSTRUMENT` | Run the script as given (already instrumented). |
| `K6_DEBUG_KEEP` | Keep the instrumented copy. |
| `K6_DEBUG_VERBOSE` | Log DAP traffic and line hooks to stderr. |

Supported requests: `initialize`, `attach`/`launch`, `setBreakpoints`,
`configurationDone`, `threads` (one per VU), `stackTrace` (one frame),
`scopes`, `variables`, `evaluate` (paths only), `continue`, `next`, `stepIn`,
`stepOut`, `source`, `disconnect`. Not supported: conditional breakpoints,
arbitrary expressions, multiple stack frames, breakpoints in imported files.

## Build

Requires Go 1.26+ and [xk6](https://github.com/grafana/xk6) v1.5+:

```bash
go install go.k6.io/xk6/cmd/xk6@v1.5.1
xk6 build v2.4.0 --with github.com/lakeside-digital-dev/k6-debug=. --output k6-debug
```

Alternatively `go build -o k6-debug ./cmd/k6debug` (uses the k6 version in `go.mod`).

The embedded instrumenter `instrument/bundle.js` is generated from
`preprocessor/` (Node.js only needed for this step):

```bash
cd preprocessor && npm ci --ignore-scripts && npm test && npm run bundle
```

Tests:

```bash
go test ./...
python3 test/dap_smoke_test.py ./k6-debug   # end-to-end DAP session on test/smoke.ts
```

Releases are created by the `Release` workflow (manual dispatch) with tag
`v<k6-version>-<n>` and assets `k6-debug-<os>-<arch>[.exe]` + `SHA256SUMS`.
