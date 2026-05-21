def verify_toss_webhook(signature: str, body: bytes) -> bool:
    # TODO(지현): Toss Payments webhook 서명 검증 구현.
    return bool(signature and body)
