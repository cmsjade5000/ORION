import json
import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path


class TestTelegramSendMessageScript(unittest.TestCase):
    def _repo_root(self) -> Path:
        return Path(__file__).resolve().parents[1]

    def _script(self) -> Path:
        return self._repo_root() / "scripts" / "telegram_send_message.sh"

    def _mock_curl(self, bindir: Path) -> Path:
        p = bindir / "curl"
        p.write_text(
            """#!/usr/bin/env bash
set -euo pipefail
LOG="${MOCK_CURL_LOG:?}"
MODE="${MOCK_CURL_MODE:-ok}"
url=""
data=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    -H|-d|--data|--data-raw)
      if [[ $# -ge 2 ]]; then
        if [[ "$1" == "-d" || "$1" == "--data" || "$1" == "--data-raw" ]]; then
          data="$2"
        fi
        shift 2
      else
        shift
      fi
      ;;
    -s|-S|-f|-L|--fail|--silent|--show-error)
      shift
      ;;
    http://*|https://*)
      url="$1"
      shift
      ;;
    *)
      shift
      ;;
  esac
done
method="${url##*/}"
printf '%s\\t%s\\n' "${method}" "${data}" >> "${LOG}"
if [[ "${MODE}" == "draft_network_fail" && "${method}" == "sendMessageDraft" ]]; then
  echo "curl: (7) Failed to connect" >&2
  exit 7
fi
if [[ "${MODE}" == "draft_unsupported" && "${method}" == "sendMessageDraft" ]]; then
  printf '{"ok":false,"error_code":404,"description":"Not Found"}'
elif [[ "${MODE}" == "send_error" && "${method}" == "sendMessage" ]]; then
  printf '{"ok":false,"error_code":500,"description":"Internal Server Error"}'
else
  printf '{"ok":true,"result":{}}'
fi
""",
            encoding="utf-8",
        )
        p.chmod(p.stat().st_mode | stat.S_IXUSR)
        return p

    def _run_script(self, *, text: str, extra_env: dict[str, str] | None = None) -> tuple[subprocess.CompletedProcess[str], list[tuple[str, dict]]]:
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            bindir = tdp / "bin"
            bindir.mkdir(parents=True, exist_ok=True)
            self._mock_curl(bindir)
            log_path = tdp / "curl.log"

            env = dict(os.environ)
            env["PATH"] = f"{bindir}:{env.get('PATH', '')}"
            env["MOCK_CURL_LOG"] = str(log_path)
            env["TELEGRAM_BOT_TOKEN"] = "test-token"
            env["ORION_SUPPRESS_TELEGRAM"] = "0"
            if extra_env:
                env.update(extra_env)

            proc = subprocess.run(
                ["bash", str(self._script()), "12345", text],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
                cwd=str(self._repo_root()),
                check=False,
            )

            calls: list[tuple[str, dict]] = []
            if log_path.exists():
                for line in log_path.read_text(encoding="utf-8").splitlines():
                    if not line.strip():
                        continue
                    method, payload = line.split("\t", 1)
                    calls.append((method, json.loads(payload)))
            return proc, calls

    def test_send_message_default(self):
        proc, calls = self._run_script(text="hello world")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual([m for m, _ in calls], ["sendMessage"])
        self.assertEqual(calls[0][1]["chat_id"], "12345")
        self.assertEqual(calls[0][1]["text"], "hello world")
        self.assertTrue(calls[0][1]["disable_web_page_preview"])

    def test_parse_mode_html_opt_in(self):
        proc, calls = self._run_script(text="hello world", extra_env={"TELEGRAM_PARSE_MODE": "HTML"})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(calls[0][1]["parse_mode"], "HTML")

    def test_invalid_parse_mode_fails_fast(self):
        proc, calls = self._run_script(text="hello world", extra_env={"TELEGRAM_PARSE_MODE": "BAD"})
        self.assertEqual(proc.returncode, 2)
        self.assertIn("Invalid TELEGRAM_PARSE_MODE", proc.stderr)
        self.assertEqual(calls, [])

    def test_preview_can_be_enabled(self):
        proc, calls = self._run_script(
            text="hello world",
            extra_env={"TELEGRAM_DISABLE_WEB_PREVIEW": "0"},
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertFalse(calls[0][1]["disable_web_page_preview"])

    def test_reply_to_message_id_attached(self):
        proc, calls = self._run_script(
            text="hello world",
            extra_env={"TELEGRAM_REPLY_TO_MESSAGE_ID": "42"},
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(calls[0][1]["reply_to_message_id"], 42)

    def test_long_message_chunks_under_limit(self):
        text = "0123456789012345678901234"
        proc, calls = self._run_script(
            text=text,
            extra_env={"TELEGRAM_MAX_CHARS": "10"},
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(all(method == "sendMessage" for method, _ in calls))
        self.assertGreater(len(calls), 1)
        self.assertTrue(all(len(payload["text"]) <= 10 for _, payload in calls))
        self.assertEqual("".join(payload["text"] for _, payload in calls), text)

    def test_chunked_reply_id_only_first_chunk(self):
        proc, calls = self._run_script(
            text="0123456789012345678901234",
            extra_env={
                "TELEGRAM_MAX_CHARS": "10",
                "TELEGRAM_REPLY_TO_MESSAGE_ID": "42",
            },
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(calls[0][1]["reply_to_message_id"], 42)
        for _, payload in calls[1:]:
            self.assertNotIn("reply_to_message_id", payload)

    def test_stream_draft_then_send(self):
        proc, calls = self._run_script(
            text="hello world!",
            extra_env={
                "TELEGRAM_STREAM_DRAFT": "1",
                "TELEGRAM_STREAM_CHUNK_CHARS": "5",
                "TELEGRAM_STREAM_STEP_MS": "0",
            },
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual([m for m, _ in calls], ["sendMessageDraft", "sendMessageDraft", "sendMessage"])
        self.assertEqual(calls[0][1]["text"], "hello")
        self.assertEqual(calls[1][1]["text"], "hello worl")
        self.assertEqual(calls[2][1]["text"], "hello world!")
        self.assertTrue(isinstance(calls[0][1]["draft_id"], int))
        self.assertGreater(calls[0][1]["draft_id"], 0)
        self.assertEqual(calls[0][1]["draft_id"], calls[1][1]["draft_id"])

    def test_stream_falls_back_when_draft_unsupported(self):
        proc, calls = self._run_script(
            text="hello world!",
            extra_env={
                "MOCK_CURL_MODE": "draft_unsupported",
                "TELEGRAM_STREAM_DRAFT": "true",
                "TELEGRAM_STREAM_CHUNK_CHARS": "5",
                "TELEGRAM_STREAM_STEP_MS": "0",
            },
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual([m for m, _ in calls], ["sendMessageDraft", "sendMessage"])
        self.assertIn("falling back to sendMessage", proc.stderr)

    def test_stream_draft_network_failure_falls_back_once(self):
        proc, calls = self._run_script(
            text="hello world!",
            extra_env={
                "MOCK_CURL_MODE": "draft_network_fail",
                "TELEGRAM_STREAM_DRAFT": "1",
                "TELEGRAM_STREAM_CHUNK_CHARS": "5",
                "TELEGRAM_STREAM_STEP_MS": "0",
            },
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual([m for m, _ in calls], ["sendMessageDraft", "sendMessage"])
        self.assertEqual(proc.stderr.count("falling back to sendMessage"), 1)

    def test_stream_final_send_failure_does_not_double_send(self):
        proc, calls = self._run_script(
            text="hello world!",
            extra_env={
                "MOCK_CURL_MODE": "send_error",
                "TELEGRAM_STREAM_DRAFT": "1",
                "TELEGRAM_STREAM_CHUNK_CHARS": "5",
                "TELEGRAM_STREAM_STEP_MS": "0",
            },
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual([m for m, _ in calls], ["sendMessageDraft", "sendMessageDraft", "sendMessage"])

    def test_stream_short_text_skips_drafts_without_warning(self):
        proc, calls = self._run_script(
            text="hi",
            extra_env={
                "TELEGRAM_STREAM_DRAFT": "1",
                "TELEGRAM_STREAM_CHUNK_CHARS": "50",
                "TELEGRAM_STREAM_STEP_MS": "0",
            },
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual([m for m, _ in calls], ["sendMessage"])
        self.assertNotIn("falling back to sendMessage", proc.stderr)


if __name__ == "__main__":
    unittest.main()
