import os
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path


class TestMiniappUploadArtifactScript(unittest.TestCase):
    def _make_fake_curl(self, bin_dir: Path) -> Path:
        curl_path = bin_dir / "curl"
        curl_path.write_text(
            textwrap.dedent(
                """\
                #!/usr/bin/env bash
                set -euo pipefail

                out_file=""
                while [[ $# -gt 0 ]]; do
                  case "$1" in
                    -o)
                      out_file="$2"
                      shift 2
                      ;;
                    -w)
                      shift 2
                      ;;
                    *)
                      shift
                      ;;
                  esac
                done

                body="${FAKE_CURL_BODY:-}"
                if [[ -z "${body}" ]]; then
                  body='{"ok":true}'
                fi
                code="${FAKE_CURL_HTTP_CODE:-200}"
                exit_code="${FAKE_CURL_EXIT_CODE:-0}"

                if [[ -n "${out_file}" ]]; then
                  printf '%s' "${body}" > "${out_file}"
                fi
                if [[ "${exit_code}" -ne 0 ]]; then
                  exit "${exit_code}"
                fi
                printf '%s' "${code}"
                """
            ),
            encoding="utf-8",
        )
        curl_path.chmod(0o755)
        return curl_path

    def _run_script(self, base_url: str, env_extra: dict[str, str]) -> subprocess.CompletedProcess[str]:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "miniapp_upload_artifact.sh"
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            bin_dir = tmp / "bin"
            bin_dir.mkdir(parents=True, exist_ok=True)
            self._make_fake_curl(bin_dir)

            payload = tmp / "artifact.txt"
            payload.write_text("hello\n", encoding="utf-8")

            env = os.environ.copy()
            env["PATH"] = f"{bin_dir}:{env.get('PATH', '')}"
            env.update(env_extra)

            return subprocess.run(
                [
                    str(script),
                    base_url,
                    str(payload),
                    "artifact.txt",
                    "text/plain",
                    "PIXEL",
                ],
                text=True,
                capture_output=True,
                env=env,
                check=False,
            )

    def test_success_requires_ok_true_json(self):
        proc = self._run_script(
            "https://example.com",
            {
                "FAKE_CURL_HTTP_CODE": "201",
                "FAKE_CURL_BODY": '{"ok": true, "artifact": {"id": "a1"}}',
            },
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr)
        self.assertIn('"ok": true', proc.stdout)

    def test_fails_on_http_error_status(self):
        proc = self._run_script(
            "https://example.com",
            {
                "FAKE_CURL_HTTP_CODE": "500",
                "FAKE_CURL_BODY": '{"ok": false, "error": "server"}',
            },
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("HTTP 500", proc.stderr)

    def test_fails_when_response_ok_is_not_true(self):
        proc = self._run_script(
            "https://example.com",
            {
                "FAKE_CURL_HTTP_CODE": "200",
                "FAKE_CURL_BODY": '{"ok": false}',
            },
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("ok=true", proc.stderr)

    def test_rejects_insecure_token_transport_for_non_localhost(self):
        proc = self._run_script(
            "http://example.com",
            {
                "INGEST_TOKEN": "secret",
            },
        )
        self.assertEqual(proc.returncode, 2)
        self.assertIn("Refusing token-auth upload", proc.stderr)


if __name__ == "__main__":
    unittest.main()
