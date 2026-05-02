"""
Country -> Language, Timezone, Business Hours mapping.
Used for sending emails at the right time in the right language.
"""

from datetime import datetime, timezone, timedelta

# Country code -> (language_code, language_name, timezone_offset_hours, timezone_name)
COUNTRY_MAP = {
    # Turkey
    "TR": ("tr", "Turkish", 3, "Europe/Istanbul"),
    # Europe
    "DE": ("de", "German", 2, "Europe/Berlin"),
    "FR": ("fr", "French", 2, "Europe/Paris"),
    "ES": ("es", "Spanish", 2, "Europe/Madrid"),
    "IT": ("it", "Italian", 2, "Europe/Rome"),
    "NL": ("nl", "Dutch", 2, "Europe/Amsterdam"),
    "BE": ("nl", "Dutch", 2, "Europe/Brussels"),
    "AT": ("de", "German", 2, "Europe/Vienna"),
    "CH": ("de", "German", 2, "Europe/Zurich"),
    "PT": ("pt", "Portuguese", 1, "Europe/Lisbon"),
    "SE": ("sv", "Swedish", 2, "Europe/Stockholm"),
    "NO": ("no", "Norwegian", 2, "Europe/Oslo"),
    "DK": ("da", "Danish", 2, "Europe/Copenhagen"),
    "FI": ("fi", "Finnish", 3, "Europe/Helsinki"),
    "PL": ("pl", "Polish", 2, "Europe/Warsaw"),
    "CZ": ("cs", "Czech", 2, "Europe/Prague"),
    "RO": ("ro", "Romanian", 3, "Europe/Bucharest"),
    "GR": ("el", "Greek", 3, "Europe/Athens"),
    "IE": ("en", "English", 1, "Europe/Dublin"),
    # UK
    "UK": ("en", "English", 1, "Europe/London"),
    "GB": ("en", "English", 1, "Europe/London"),
    # Americas
    "US": ("en", "English", -5, "America/New_York"),
    "CA": ("en", "English", -5, "America/Toronto"),
    "MX": ("es", "Spanish", -6, "America/Mexico_City"),
    "BR": ("pt", "Portuguese", -3, "America/Sao_Paulo"),
    "AR": ("es", "Spanish", -3, "America/Buenos_Aires"),
    "CO": ("es", "Spanish", -5, "America/Bogota"),
    "CL": ("es", "Spanish", -4, "America/Santiago"),
    # Middle East
    "AE": ("en", "English", 4, "Asia/Dubai"),
    "SA": ("ar", "Arabic", 3, "Asia/Riyadh"),
    "IL": ("en", "English", 3, "Asia/Jerusalem"),
    "QA": ("en", "English", 3, "Asia/Qatar"),
    # Asia
    "IN": ("en", "English", 5.5, "Asia/Kolkata"),
    "SG": ("en", "English", 8, "Asia/Singapore"),
    "JP": ("ja", "Japanese", 9, "Asia/Tokyo"),
    "KR": ("ko", "Korean", 9, "Asia/Seoul"),
    "CN": ("zh", "Chinese", 8, "Asia/Shanghai"),
    "ID": ("id", "Indonesian", 7, "Asia/Jakarta"),
    "MY": ("en", "English", 8, "Asia/Kuala_Lumpur"),
    "TH": ("th", "Thai", 7, "Asia/Bangkok"),
    "VN": ("vi", "Vietnamese", 7, "Asia/Ho_Chi_Minh"),
    "PH": ("en", "English", 8, "Asia/Manila"),
    # Africa
    "ZA": ("en", "English", 2, "Africa/Johannesburg"),
    "NG": ("en", "English", 1, "Africa/Lagos"),
    "KE": ("en", "English", 3, "Africa/Nairobi"),
    "EG": ("ar", "Arabic", 2, "Africa/Cairo"),
    # Oceania
    "AU": ("en", "English", 10, "Australia/Sydney"),
    "NZ": ("en", "English", 12, "Pacific/Auckland"),
    # International / Unknown
    "INT": ("en", "English", 0, "UTC"),
}

DEFAULT_LOCALE = ("en", "English", 0, "UTC")


def get_locale(country_code):
    return COUNTRY_MAP.get(country_code.upper(), DEFAULT_LOCALE)


def get_language(country_code):
    return get_locale(country_code)[0]


def get_language_name(country_code):
    return get_locale(country_code)[1]


def get_tz_offset(country_code):
    return get_locale(country_code)[2]


def get_local_time(country_code):
    offset = get_tz_offset(country_code)
    utc_now = datetime.now(timezone.utc)
    local_time = utc_now + timedelta(hours=offset)
    return local_time


def is_business_hours(country_code):
    local = get_local_time(country_code)
    return 9 <= local.hour < 17


def get_best_send_hour_utc(country_code):
    offset = get_tz_offset(country_code)
    utc_hour = (10 - offset) % 24
    return int(utc_hour)


def should_send_now(country_code):
    local = get_local_time(country_code)
    is_weekday = local.weekday() < 5
    is_morning = 9 <= local.hour <= 11
    return is_weekday and is_morning
