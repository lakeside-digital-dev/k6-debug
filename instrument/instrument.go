// Package instrument rewrites a k6 script (JavaScript or TypeScript) so the
// k6/x/debug module can pause on lines and capture variables.
//
// The Babel-based preprocessor (../preprocessor) is bundled into bundle.js
// (`npm run bundle`) and executed with sobek, so no Node.js is needed at
// runtime.
package instrument

import (
	_ "embed"
	"fmt"
	"sync"

	"github.com/grafana/sobek"
)

//go:embed bundle.js
var bundleSource string

const shim = `var process = globalThis.process || { env: {}, argv: [], emitWarning: function () {}, cwd: function () { return "/"; } };
var console = globalThis.console || { log: function () {}, warn: function () {}, error: function () {} };`

var (
	compileOnce sync.Once
	program     *sobek.Program
	compileErr  error
)

// Source instruments source. filename must be the absolute path of the
// original script: it is embedded into every hook so breakpoints set on the
// original file match. A .ts/.mts/.cts filename enables TypeScript parsing.
func Source(source, filename string) (string, error) {
	compileOnce.Do(func() {
		program, compileErr = sobek.Compile("k6-debug-instrument.js", bundleSource, false)
	})
	if compileErr != nil {
		return "", fmt.Errorf("compile instrumenter: %w", compileErr)
	}

	rt := sobek.New()
	if _, err := rt.RunString(shim); err != nil {
		return "", fmt.Errorf("instrumenter shim: %w", err)
	}
	if _, err := rt.RunProgram(program); err != nil {
		return "", fmt.Errorf("load instrumenter: %w", err)
	}
	fn, ok := sobek.AssertFunction(rt.Get("k6DebugInstrument"))
	if !ok {
		return "", fmt.Errorf("instrumenter entry point missing")
	}
	out, err := fn(sobek.Undefined(), rt.ToValue(source), rt.ToValue(filename))
	if err != nil {
		return "", fmt.Errorf("instrument %s: %w", filename, err)
	}
	return out.String(), nil
}
