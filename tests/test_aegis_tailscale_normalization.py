import json
import shutil
import subprocess

import unittest


_JQ_FILTER_MEMBERS = r"""
{
  self: {dnsName: .Self.DNSName, hostName: .Self.HostName, os: .Self.OS, tailscaleIPs: .Self.TailscaleIPs},
  peers: (
    .Peer
    | to_entries
    | map(.value)
    | map({dnsName: .DNSName, hostName: .HostName, os: .OS, tailscaleIPs: .TailscaleIPs})
    | sort_by(.dnsName)
  )
}
""".strip()

_JQ_FILTER_STATUS = r"""
{
  self: {dnsName: .Self.DNSName, hostName: .Self.HostName, os: .Self.OS, tailscaleIPs: .Self.TailscaleIPs, online: .Self.Online, active: .Self.Active},
  peers: (
    .Peer
    | to_entries
    | map(.value)
    | map({dnsName: .DNSName, hostName: .HostName, os: .OS, tailscaleIPs: .TailscaleIPs, online: .Online, active: .Active})
    | sort_by(.dnsName)
  )
}
""".strip()


def _jq_normalize(obj: dict, filter_expr: str) -> dict:
    if not shutil.which("jq"):
        raise unittest.SkipTest("jq not installed")
    p = subprocess.run(
        ["jq", "-S", filter_expr],
        input=(json.dumps(obj) + "\n").encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    return json.loads(p.stdout.decode("utf-8"))


class TestAegisTailscaleNormalization(unittest.TestCase):
    def test_membership_normalization_ignores_online_active_churn(self):
        base = {
            "Self": {
                "DNSName": "aegis.example.ts.net",
                "HostName": "aegis",
                "OS": "linux",
                "TailscaleIPs": ["100.64.0.1"],
                "Online": True,
                "Active": True,
            },
            "Peer": {
                "peer1": {
                    "DNSName": "laptop.example.ts.net",
                    "HostName": "laptop",
                    "OS": "macos",
                    "TailscaleIPs": ["100.64.0.2"],
                    "Online": True,
                    "Active": True,
                }
            },
        }
        churned = json.loads(json.dumps(base))
        churned["Peer"]["peer1"]["Online"] = False
        churned["Peer"]["peer1"]["Active"] = False

        members_a = _jq_normalize(base, _JQ_FILTER_MEMBERS)
        members_b = _jq_normalize(churned, _JQ_FILTER_MEMBERS)
        self.assertEqual(members_a, members_b)

        status_a = _jq_normalize(base, _JQ_FILTER_STATUS)
        status_b = _jq_normalize(churned, _JQ_FILTER_STATUS)
        self.assertNotEqual(status_a, status_b)
