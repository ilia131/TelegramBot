def number(value: int) -> str:
    return f"{value:,}".translate(str.maketrans("0123456789,", "۰۱۲۳۴۵۶۷۸۹٬"))


def details(order) -> str:
    return (
        f"حجم اشتراک: {number(order['volume_gb'])} گیگابایت\n"
        f"مدت اعتبار: {number(order['duration_days'])} روز\n"
        f"قیمت: {number(order['price_toman'])} تومان"
    )
