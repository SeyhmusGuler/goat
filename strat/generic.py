class Strategy:
    def __init__(self, max_eq=float("inf")):
        self.MAX_EQ = max_eq

    def __str__(self):
        return f"Max allowed equity : {self.MAX_EQ}"

    def set_max_equity(self, max_eq):
        self.MAX_EQ = max_eq

    def get_max_equity(self):
        return self.MAX_EQ
