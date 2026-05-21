def send_booking_notification(user_id: str, booking_id: str) -> None:
    # TODO(지현): 카카오 알림톡/이메일 발송 작업을 Celery로 위임.
    _ = (user_id, booking_id)
