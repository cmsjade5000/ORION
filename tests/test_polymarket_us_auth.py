import base64
import os
import subprocess
import tempfile


def test_pkcs8_pem_and_signing_openssl_roundtrip():
    # 64 bytes total is common (seed + pubkey). Only first 32 bytes are used by our converter.
    seed = bytes([7]) * 32
    pub = bytes([9]) * 32
    secret_b64 = base64.b64encode(seed + pub).decode("ascii")

    import scripts.arb.polymarket_us as pm

    pem = pm.ed25519_pkcs8_pem_from_secret_b64(secret_b64)
    assert "BEGIN PRIVATE KEY" in pem

    tf = tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8")
    tf.write(pem)
    tf.flush()
    tf.close()
    key_path = tf.name

    try:
        # Ensure OpenSSL can parse the PKCS#8 key.
        proc = subprocess.run(["openssl", "pkey", "-in", key_path, "-noout"], capture_output=True, check=False, timeout=10)
        assert proc.returncode == 0, (proc.stderr or b"").decode("utf-8", errors="replace")

        sig_b64 = pm._ed25519_sign_base64(b"1234567890GET/v1/test", secret_b64=secret_b64, private_key_path="")
        sig = base64.b64decode(sig_b64)
        assert len(sig) == 64
    finally:
        try:
            os.remove(key_path)
        except Exception:
            pass

