"""
Unit tests for services/broker_service.py — pure encryption helpers only.

No DB or network required. FERNET_KEY is set by conftest.py.
"""
from __future__ import annotations

import os
import pytest
from services.broker_service import encrypt_secret, decrypt_secret


# ─── Round-trip ───────────────────────────────────────────────────────────────

def test_encrypt_returns_bytes():
    result = encrypt_secret("my-api-key-12345")
    assert isinstance(result, bytes)
    assert len(result) > 0


def test_decrypt_round_trip():
    plaintext = "sk-live-abc123XYZ"
    assert decrypt_secret(encrypt_secret(plaintext)) == plaintext


def test_round_trip_long_key():
    plaintext = "A" * 200
    assert decrypt_secret(encrypt_secret(plaintext)) == plaintext


def test_round_trip_special_characters():
    plaintext = "ke!y-with$pec|al_ch@rs/and=equals"
    assert decrypt_secret(encrypt_secret(plaintext)) == plaintext


def test_round_trip_empty_string():
    assert decrypt_secret(encrypt_secret("")) == ""


# ─── Ciphertext is non-deterministic (random IV) ─────────────────────────────

def test_same_plaintext_different_ciphertext():
    plaintext = "same-key"
    c1 = encrypt_secret(plaintext)
    c2 = encrypt_secret(plaintext)
    # Fernet uses a random IV so two encryptions of the same value differ
    assert c1 != c2
    # Both should still decrypt correctly
    assert decrypt_secret(c1) == plaintext
    assert decrypt_secret(c2) == plaintext


# ─── Invalid ciphertext raises ValueError ────────────────────────────────────

def test_decrypt_invalid_raises():
    with pytest.raises(ValueError):
        decrypt_secret(b"this-is-not-valid-fernet-ciphertext")


def test_decrypt_corrupted_raises():
    ciphertext = encrypt_secret("real-key")
    corrupted = bytearray(ciphertext)
    # Flip a byte in the middle
    corrupted[len(corrupted) // 2] ^= 0xFF
    with pytest.raises(ValueError):
        decrypt_secret(bytes(corrupted))


# ─── Missing FERNET_KEY raises at call time ───────────────────────────────────

def test_missing_fernet_key_raises(monkeypatch):
    monkeypatch.delenv("FERNET_KEY", raising=False)
    with pytest.raises(RuntimeError, match="FERNET_KEY"):
        encrypt_secret("any-key")


def test_missing_fernet_key_decrypt_raises(monkeypatch):
    ciphertext = encrypt_secret("original")   # encrypted while key is present
    monkeypatch.delenv("FERNET_KEY", raising=False)
    with pytest.raises(RuntimeError, match="FERNET_KEY"):
        decrypt_secret(ciphertext)
