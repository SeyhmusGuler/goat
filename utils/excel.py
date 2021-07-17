import pandas


def save_to_excel_file(excel_filename, dataframe):
    writer = pandas.ExcelWriter(excel_filename+'.xlsx', engine='xlsxwriter')
    dataframe.to_excel(writer, excel_filename, index=False)

    background_color = '#0a0a23'
    font_color = '#ffffff'

    string_format = writer.book.add_format(
        {
            'font_color': font_color,
            'bg_color': background_color,
            'border': 1
        }
    )

    dollar_format = writer.book.add_format(
        {
            'num_format': '$0.00',
            'font_color': font_color,
            'bg_color': background_color,
            'border': 1
        }
    )

    integer_format = writer.book.add_format(
        {
            'num_format': '0',
            'font_color': font_color,
            'bg_color': background_color,
            'border': 1
        }
    )

    column_format = {
        'A': ['Ticker', string_format],
        'B': ['Stock Price', dollar_format],
        'C': ['Market Capitalization', dollar_format],
        'D': ['Number of Shares to Buy', integer_format]
    }

    for column in column_format.keys():
        writer.sheets[excel_filename].set_column(f"{column}:{column}",
                                                 18,
                                                 column_format[column])
