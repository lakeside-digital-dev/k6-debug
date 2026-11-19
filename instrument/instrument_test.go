package instrument

import (
	"strings"
	"testing"
)

func TestSourceTypeScript(t *testing.T) {
	src := "import http from 'k6/http';\n" +
		"export function setup(): { token: string } { return { token: 'abc' }; }\n" +
		"export default function (data: { token: string }) {\n" +
		"  const res = http.get('http://x/' + data.token);\n" +
		"}\n"
	out, err := Source(src, "/abs/smoke.ts")
	if err != nil {
		t.Fatal(err)
	}
	for _, want := range []string{`from "k6/x/debug"`, `name: "data"`, `name: "res"`, `file: "/abs/smoke.ts"`, `data: {token: string;}`} {
		if !strings.Contains(out, want) {
			t.Errorf("missing %q in:\n%s", want, out)
		}
	}
	if got, want := strings.Count(strings.TrimRight(out, "\n"), "\n"), strings.Count(strings.TrimRight(src, "\n"), "\n"); got != want {
		t.Errorf("line count changed: %d != %d", got, want)
	}
}

func TestSourceSyntaxError(t *testing.T) {
	if _, err := Source("export default function ( {", "/abs/bad.js"); err == nil {
		t.Fatal("expected syntax error")
	}
}
