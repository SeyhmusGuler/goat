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
    
def add_two(x: int) -> int:
    """
    Adds 2 to the input and returns the result.

    Args:
        x (int, float): The input is number

    Raises:
        TypeError: If the input is not a number

    Returns:
        int, float: Input + 2
    """
    if type(x) == int or type(x) == float: 
        return x+2
    raise TypeError("Input is not a number.")
