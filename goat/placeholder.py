def multiply_by_2(x: int) -> int:
    """
    Multiplies the input integer x by 2.

    Parameters
    ----------
    x : int
        The input integer

    Returns
    -------
    int
        The input times 2

    Raises
    ------
    TypeError
        If the type of input isn't int.
    """
    if type(x) == int:
        return x * 2
    raise TypeError("The type of the input wasn't int.")
