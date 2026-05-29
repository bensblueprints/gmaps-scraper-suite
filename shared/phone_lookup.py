"""
Phone number type classification.

Free: toll-free area code detection + phonenumbers library (Google's libphonenumber).
Paid: Twilio Lookup API for definitive mobile/landline/VoIP (uses existing Twilio credentials).
"""
import re

_TOLL_FREE = {"800", "888", "877", "866", "855", "844", "833", "822"}


def _area_code(phone: str) -> str:
    digits = re.sub(r"\D", "", phone)
    if len(digits) == 11 and digits.startswith("1"):
        return digits[1:4]
    if len(digits) == 10:
        return digits[:3]
    return ""


def classify_phone(phone: str, twilio_sid: str = "", twilio_token: str = "") -> dict:
    """
    Returns {"type": str, "carrier": str, "formatted": str}
    type: "toll_free" | "mobile" | "landline" | "voip" | "premium" | "unknown"
    """
    result = {"type": "unknown", "carrier": "", "formatted": phone}
    if not phone:
        return result

    if _area_code(phone) in _TOLL_FREE:
        result["type"] = "toll_free"
        return result

    try:
        import phonenumbers
        from phonenumbers import number_type, PhoneNumberType
        from phonenumbers import carrier as ph_carrier

        parsed = phonenumbers.parse(phone, "US")
        if phonenumbers.is_valid_number(parsed):
            result["formatted"] = phonenumbers.format_number(
                parsed, phonenumbers.PhoneNumberFormat.NATIONAL
            )
            nt = number_type(parsed)
            result["type"] = {
                PhoneNumberType.MOBILE:               "mobile",
                PhoneNumberType.FIXED_LINE:           "landline",
                PhoneNumberType.FIXED_LINE_OR_MOBILE: "unknown",
                PhoneNumberType.VOIP:                 "voip",
                PhoneNumberType.TOLL_FREE:            "toll_free",
                PhoneNumberType.PREMIUM_RATE:         "premium",
            }.get(nt, "unknown")
            c = ph_carrier.name_for_number(parsed, "en")
            if c:
                result["carrier"] = c
    except Exception:
        pass

    # Twilio Lookup for definitive classification when still unknown
    if twilio_sid and twilio_token and result["type"] == "unknown":
        try:
            from twilio.rest import Client
            lookup = (Client(twilio_sid, twilio_token)
                      .lookups.v1.phone_numbers(phone)
                      .fetch(type=["carrier"]))
            info = lookup.carrier or {}
            ltype = info.get("type", "")
            if ltype in ("mobile", "landline", "voip"):
                result["type"] = ltype
            if info.get("name"):
                result["carrier"] = info["name"]
        except Exception:
            pass

    return result
