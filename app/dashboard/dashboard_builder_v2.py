def build_dashboard(df):
    critical = df[df["stock_status"] == "critical"]
    out_of_stock = df[df["stock_status"] == "out_of_stock"]

    groups = df.groupby("product_group")

    # дальше уже html как у тебя есть