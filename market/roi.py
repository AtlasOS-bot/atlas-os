class ROIEngine:

    EBAY_FEE_RATE = 0.13
    DEFAULT_SHIPPING = 8.00

    @staticmethod
    def calculate(
        retail_price,
        average_sold_price,
        shipping_cost=None,
        fee_rate=None,
    ):

        if retail_price is None or average_sold_price is None:
            return None

        shipping = (
            shipping_cost
            if shipping_cost is not None
            else ROIEngine.DEFAULT_SHIPPING
        )

        fees = (
            average_sold_price
            * (
                fee_rate
                if fee_rate is not None
                else ROIEngine.EBAY_FEE_RATE
            )
        )

        net_revenue = average_sold_price - fees - shipping

        profit = net_revenue - retail_price

        roi = (profit / retail_price) * 100 if retail_price > 0 else 0

        return {
            "retail_price": round(retail_price, 2),
            "average_sold_price": round(average_sold_price, 2),
            "fees": round(fees, 2),
            "shipping": round(shipping, 2),
            "net_revenue": round(net_revenue, 2),
            "profit": round(profit, 2),
            "roi": round(roi, 2),
        }