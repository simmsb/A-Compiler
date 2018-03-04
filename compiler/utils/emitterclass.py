class Emitter(type):
    """Creates an 'emitter' class.

    Methods that have the 'emits' decorator used will become classmethods
    and their name and object will be included in the class attribute 'emitters'
    which will be a dict mapping method names to methods.

    Example usage:

    class MyEmitter(metaclass=Emitter):

        @emits("something")
        def my_method(cls, attr):
            return str(attr)

    MyEmitter.emitters  # = {'something': MyEmitter.my_method}
    """

    def __new__(mcs, name, bases, dict):

        klass = type.__new__(mcs, name, bases, dict)

        emitters = {}

        for attr in dir(klass):
            obj = getattr(klass, attr)
            if hasattr(obj, "emitter_for"):
                emitters[attr] = obj

        klass.emitters = emitters

        return klass


def emits(name: str):
    """Decorator that marks a function for what it will desugar.
    Also marks as a classmethod.
    """
    def deco(fn):
        fn.emitter_for = name
        return classmethod(fn)
    return deco
