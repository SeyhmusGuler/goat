import pandas
from os.path import splitext


def save_to_excel_file(excel_filename, dataframe):
    writer = pandas.ExcelWriter(excel_filename, engine="xlsxwriter")
    base = splitext(excel_filename)[0]
    print(base)
    dataframe.to_excel(writer, base, index=False)

    background_color = "#0a0a23"
    font_color = "#ffffff"

    string_format = writer.book.add_format({"font_color": font_color, "bg_color": background_color, "border": 1})

    dollar_format = writer.book.add_format(
        {"num_format": "$0.00", "font_color": font_color, "bg_color": background_color, "border": 1}
    )

    integer_format = writer.book.add_format(
        {"num_format": "0", "font_color": font_color, "bg_color": background_color, "border": 1}
    )

    column_format = {
        "A": ["Ticker", string_format],
        "B": ["Stock Price", dollar_format],
        "C": ["Market Capitalization", dollar_format],
        "D": ["Number of Shares to Buy", integer_format],
    }

    for column in column_format:
        writer.sheets[base].write(f"{column}1", column_format[column][0], column_format[column][1])
        writer.sheets[base].set_column(f"{column}:{column}", 18, column_format[column][1])
    writer.save()
