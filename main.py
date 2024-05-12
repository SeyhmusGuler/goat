from strat.equal_weight_sp500 import EqualWeightSP
from utils.excel import save_to_excel_file


if __name__ == "__main__":
    equal_weight_sp = EqualWeightSP(1_000_000)
    print(equal_weight_sp)
    save_to_excel_file("equal_weight_sp500.xlsx", equal_weight_sp.n_shares)
