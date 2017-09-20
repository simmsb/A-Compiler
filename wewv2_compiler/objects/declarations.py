from base import BaseObject


class Function(BaseObject):
    """Function definition object.

    Function definitions should expand to a declaration with assignment to a const global variable with the name of the function.
    """

    def __init__(self, ast):
        self.name = ast.name
        self.params = ast.params
        self.type = ast.r
        self.body = ast.body

    ...
