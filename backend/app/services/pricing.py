def selling_price(list_price: int, sale_price: int | None) -> int:
    if sale_price is None:
        return list_price
    return sale_price


def quote_line(list_price: int, sale_price: int | None, quantity: int) -> tuple[int, int, int, int, int]:
    unit_price = selling_price(list_price, sale_price)
    line_subtotal = list_price * quantity
    line_total = unit_price * quantity
    line_discount = line_subtotal - line_total
    return unit_price, line_subtotal, line_discount, line_total, list_price


def quote_totals(lines: list[tuple[int, int]]) -> tuple[int, int, int]:
    subtotal = sum(line_subtotal for line_subtotal, _line_total in lines)
    total = sum(line_total for _line_subtotal, line_total in lines)
    return subtotal, subtotal - total, total


def fulfillment_charges(goods_total: int) -> tuple[int, int, int]:
    shipping = 0
    tax = 0
    return shipping, tax, goods_total + shipping + tax
