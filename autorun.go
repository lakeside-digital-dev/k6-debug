package debug

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"sync"

	"github.com/lakeside-digital-dev/k6-debug/instrument"
)

// Automatic instrumentation: when K6_DEBUG_DAP is set and k6 is started with
// `run <script>`, the script is instrumented in-process (no Node.js needed).
// The instrumented copy is written next to the original (so relative imports
// and open() keep working) as .<name>.k6debug<ext>, passed to k6 instead of
// the original and deleted as soon as k6 has loaded it.
//
// Set K6_DEBUG_NO_INSTRUMENT=1 to run an already instrumented script and
// K6_DEBUG_KEEP=1 to keep the instrumented copy for inspection.

var (
	instrumentedMu   sync.Mutex
	instrumentedCopy string
)

var scriptExt = map[string]bool{".js": true, ".mjs": true, ".cjs": true, ".ts": true, ".mts": true, ".cts": true}

func init() {
	if os.Getenv("K6_DEBUG_DAP") == "" {
		return
	}
	if os.Getenv("K6_AUTO_EXTENSION_RESOLUTION") == "" {
		_ = os.Setenv("K6_AUTO_EXTENSION_RESOLUTION", "false")
	}
	if os.Getenv("K6_DEBUG_NO_INSTRUMENT") != "" {
		return
	}
	if err := instrumentRunArgs(os.Args); err != nil {
		fmt.Fprintf(os.Stderr, "[k6-debug] instrumentation failed: %v\n", err)
		os.Exit(1)
	}
}

// instrumentRunArgs finds the script of `k6 run … <script>` in args,
// instruments it and replaces the argument in place.
func instrumentRunArgs(args []string) error {
	runIdx := -1
	for i, a := range args[1:] {
		if a == "run" {
			runIdx = i + 1
			break
		}
		if !strings.HasPrefix(a, "-") {
			return nil // another subcommand
		}
	}
	if runIdx < 0 {
		return nil
	}

	scriptIdx := -1
	for i := len(args) - 1; i > runIdx; i-- {
		a := args[i]
		if strings.HasPrefix(a, "-") || !scriptExt[strings.ToLower(filepath.Ext(a))] {
			continue
		}
		if fi, err := os.Stat(a); err == nil && !fi.IsDir() {
			scriptIdx = i
			break
		}
	}
	if scriptIdx < 0 {
		return nil
	}

	orig, err := filepath.Abs(args[scriptIdx])
	if err != nil {
		return err
	}
	src, err := os.ReadFile(orig)
	if err != nil {
		return err
	}
	if strings.Contains(string(src), "k6/x/debug") {
		return nil // already instrumented
	}
	out, err := instrument.Source(string(src), orig)
	if err != nil {
		return err
	}

	ext := filepath.Ext(orig)
	copyPath := filepath.Join(filepath.Dir(orig), "."+strings.TrimSuffix(filepath.Base(orig), ext)+".k6debug"+ext)
	if err := os.WriteFile(copyPath, []byte(out), 0o600); err != nil {
		return err
	}
	instrumentedMu.Lock()
	instrumentedCopy = copyPath
	instrumentedMu.Unlock()
	args[scriptIdx] = copyPath
	return nil
}

// removeInstrumentedCopy deletes the temporary instrumented script once k6
// has read it (called when the debug module is first instantiated).
func removeInstrumentedCopy() {
	instrumentedMu.Lock()
	defer instrumentedMu.Unlock()
	if instrumentedCopy == "" || os.Getenv("K6_DEBUG_KEEP") != "" {
		return
	}
	_ = os.Remove(instrumentedCopy)
	instrumentedCopy = ""
}
