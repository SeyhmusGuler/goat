from utils.excel import save_to_excel_file
import pandas as pd


class Strategy:
    def __init__(self, max_eq=float("inf")):
        self.name = "OPStrategy"
        self.MAX_EQ = max_eq
        self.position = pd.DataFrame()

    def __str__(self):
        return f"Max allowed equity : {self.MAX_EQ}"

    def set_max_equity(self, max_eq):
        self.MAX_EQ = max_eq

    def get_max_equity(self):
        return self.MAX_EQ

    def save_to_excel(self):
        save_to_excel_file(f"{self.name}_strategy.excel", self.position)
