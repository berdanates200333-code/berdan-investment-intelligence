"""Versiegelte Prognose-Übergabe: Inhalt bleibt bis zum Cutoff für ALLE (auch die andere KI) unlesbar.

Je Sitzung erzeugt der Eingangsdienst (GitHub-Actions-Lauf) ein Einmal-Schlüsselpaar. Nur der ÖFFENTLICHE Schlüssel wird committet; der private
Schlüssel existiert ausschließlich im Arbeitsspeicher des Laufs (kein Secret, keine Ablage) und entschlüsselt erst nach dem Cutoff. Die KI
verschlüsselt (RSA-OAEP + AES-GCM) und legt nur das Chiffrat ab. Hash des Chiffrats = Commit-Beleg (Inhalt später nicht änderbar).
"""
from __future__ import annotations

import base64
import hashlib
import json
import os

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def new_keypair() -> tuple[bytes, str]:
    k = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    priv = k.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    pub = k.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()
    return priv, pub


_OAEP = padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None)


def encrypt(public_pem: str, prognosen: list) -> dict:
    key, nonce = AESGCM.generate_key(bit_length=256), os.urandom(12)
    pt = json.dumps(prognosen, sort_keys=True, ensure_ascii=False).encode()
    ct = AESGCM(key).encrypt(nonce, pt, None)
    ek = serialization.load_pem_public_key(public_pem.encode()).encrypt(key, _OAEP)
    return {"v": 1, "ek": base64.b64encode(ek).decode(), "nonce": base64.b64encode(nonce).decode(), "ct": base64.b64encode(ct).decode()}


def decrypt(private_pem: bytes, blob: dict) -> list:
    key = serialization.load_pem_private_key(private_pem, None).decrypt(base64.b64decode(blob["ek"]), _OAEP)
    return json.loads(AESGCM(key).decrypt(base64.b64decode(blob["nonce"]), base64.b64decode(blob["ct"]), None))


def blob_hash(blob: dict) -> str:
    return hashlib.sha256(json.dumps(blob, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
