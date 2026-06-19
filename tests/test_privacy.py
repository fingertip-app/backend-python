from app.services.ai.privacy import mask_personal_data


def test_mask_personal_data_masks_email_and_phone():
    text = "문의는 john@example.com 또는 010-1234-5678로 주세요."

    masked = mask_personal_data(text)

    assert masked == "문의는 [email] 또는 [phone]로 주세요."
