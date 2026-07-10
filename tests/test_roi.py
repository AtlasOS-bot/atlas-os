from market.roi import ROIEngine


def test_roi_calculation():

    result = ROIEngine.calculate(
        retail_price=50,
        average_sold_price=110,
    )

    assert result["profit"] > 0
    assert result["roi"] > 50