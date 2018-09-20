from typing import Any, Callable, TypeVar

import typing
import weakref
import os

import attr

from jsii import _reference_map
from jsii._compat import importlib_resources
from jsii._kernel import Kernel


# Yea, a global here is kind of gross, however, there's not really a better way of
# handling this. Fundamentally this is a global value, since we can only reasonably
# have a single kernel active at any one time in a real program.
kernel = Kernel()


@attr.s(auto_attribs=True, frozen=True, slots=True)
class JSIIAssembly:

    name: str
    version: str
    module: str
    filename: str

    @classmethod
    def load(cls, *args, _kernel=kernel, **kwargs):
        # Our object here really just acts as a record for our JSIIAssembly, it doesn't
        # offer any functionality itself, besides this class method that will trigger
        # the loading of the given assembly in the JSII Kernel.
        assembly = cls(*args, **kwargs)

        # Actually load the assembly into the kernel, we're using the
        # importlib.resources API here isntead of manually constructing the path, in
        # the hopes that this will make JSII modules able to be used with zipimport
        # instead of only on the FS.
        with importlib_resources.path(
            f"{assembly.module}._jsii", assembly.filename
        ) as assembly_path:
            _kernel.load(assembly.name, assembly.version, os.fspath(assembly_path))

        # Give our record of the assembly back to the caller.
        return assembly


class JSIIMeta(type):
    def __new__(cls, name, bases, attrs, *, jsii_type):
        # TODO: We need to figure out exactly what we're going to do this the kernel
        #       here. Right now we're "creating" a new one per type, and relying on
        #       the fact it's a singleton so that everything is in the same kernel.
        #       That might not make complete sense though, particularly if we ever
        #       want to have multiple kernels in a single process (does that even
        #       make sense?). Perhaps we should pass it in like we pass the type, and
        #       have the autogenerated code either create it once per library or once
        #       per process.
        attrs["__jsii_kernel__"] = kernel
        attrs["__jsii_type__"] = jsii_type

        # We need to lift all of the classproperty instances out of the class, because
        # they need to actually be set *on* the metaclass.. which is us. However we
        # don't want to have to derive a separate metaclass for each class, so instead
        # we're going to dynamically handle these.
        class_properties, new_attrs = {}, {}
        for key, value in attrs.items():
            if isinstance(value, jsii_classproperty):
                class_properties[key] = value
            else:
                new_attrs[key] = value
        new_attrs["__jsii_class_properties__"] = class_properties

        obj = type.__new__(cls, name, bases, new_attrs)

        # We need to go through an implement the __set_name__ portion of our API.
        for key, value in obj.__jsii_class_properties__.items():
            value.__set_name__(obj, key)

        _reference_map.register_type(obj.__jsii_type__, obj)

        return obj

    def __call__(cls, *args, **kwargs):
        # Create our object at the JS level.
        # TODO: Handle args/kwargs
        # TODO: Handle Overrides
        ref = cls.__jsii_kernel__.create(cls)

        # Create our object at the Python level.
        obj = cls.__class__.from_reference(cls, ref, *args, **kwargs)

        # Whenever the object we're creating gets garbage collected, then we want to
        # delete it from the JS runtime as well.
        # TODO: Figure out if this is *really* true, what happens if something goes
        #       out of scope at the Python level, but something is holding onto it
        #       at the JS level? What mechanics are in place for this if any?
        weakref.finalize(obj, cls.__jsii_kernel__.delete, obj.__jsii_ref__)

        # Instatiate our object at the Python level.
        if isinstance(obj, cls):
            obj.__init__(*args, **kwargs)

        return obj

    def from_reference(cls, ref, *args, **kwargs):
        obj = cls.__new__(cls, *args, **kwargs)
        obj.__jsii_ref__ = ref

        _reference_map.register_reference(obj.__jsii_ref__.ref, obj)

        return obj

    def __getattr__(obj, name):
        if name in obj.__jsii_class_properties__:
            return obj.__jsii_class_properties__[name].__get__(obj, None)

        raise AttributeError(f"type object {obj.__name__!r} has no attribute {name!r}")

    def __setattr__(obj, name, value):
        if name in obj.__jsii_class_properties__:
            return obj.__jsii_class_properties__[name].__set__(obj, value)

        return super().__setattr__(name, value)


# NOTE: We do this goofy thing so that typing works on our generated stub classes,
#       because MyPy does not currently understand the decorator protocol very well.
#       Something like https://github.com/python/peps/pull/242 should make this no
#       longer required.
if typing.TYPE_CHECKING:
    jsii_property = property
else:
    # The naming is a little funky on this, since it's a class but named like a
    # function. This is done to better mimic other decorators like @proeprty.
    class jsii_property:

        # We throw away the getter function here, because it doesn't really matter or
        # provide us with anything useful. It exists only to provide a way to pass
        # naming into us, and so that consumers of this library can "look at the
        # source" and at least see something that resembles the structure of the
        # library they're using, even though it won't have any of the body of the code.
        def __init__(self, getter):
            pass

        # TODO: Figure out a way to let the caller of this override the name. This might
        #       be useful in cases where the name that the JS level code is using isn't
        #       a valid python identifier, but we still want to be able to bind it, and
        #       doing so would require giving it a different name at the Python level.
        def __set_name__(self, owner, name):
            self.name = name

        def __get__(self, instance, owner):
            return instance.__jsii_kernel__.get(instance.__jsii_ref__, self.name)

        def __set__(self, instance, value):
            instance.__jsii_kernel__.set(instance.__jsii_ref__, self.name, value)


class _JSIIMethod:
    def __init__(self, obj, method_name):
        self.obj = obj
        self.method_name = method_name

    def __call__(self, *args):
        kernel = self.obj.__jsii_kernel__
        return kernel.invoke(self.obj.__jsii_ref__, self.method_name, args)


# NOTE: We do this goofy thing so that typing works on our generated stub classes,
#       because MyPy does not currently understand the decorator protocol very well.
#       Something like https://github.com/python/peps/pull/242 should make this no
#       longer required.
if typing.TYPE_CHECKING:
    F = TypeVar("F", bound=Callable[..., Any])

    def jsii_method(func: F) -> F:
        ...


else:
    # Again, the naming is a little funky on this, since it's a class but named like a
    # function. This is done to better mimic other decorators like @classmethod.
    class jsii_method:

        # Again, we're throwing away the actual function body, because it exists only
        # to provide the structure of the library for people who read the code, and a
        # way to pass the name/typing signatures through.
        def __init__(self, meth):
            pass

        # TODO: Figure out a way to let the caller of this override the name. This might
        #       be useful in cases where the name that the JS level code is using isn't
        #       a valid python identifier, but we still want to be able to bind it, and
        #       doing so would require giving it a different name at the Python level.
        def __set_name__(self, owner, name):
            self.name = name

        def __get__(self, instance, owner):
            return _JSIIMethod(instance, self.name)


class _JSIIClassMethod:
    def __init__(self, klass, method_name):
        self.klass = klass
        self.method_name = method_name

    def __call__(self, *args):
        kernel = self.klass.__jsii_kernel__
        return kernel.sinvoke(self.klass, self.method_name, args)


if typing.TYPE_CHECKING:
    jsii_classmethod = classmethod
else:

    class jsii_classmethod:
        def __init__(self, meth):
            pass

        def __set_name__(self, owner, name):
            self.name = name

        def __get__(self, instance, owner):
            return _JSIIClassMethod(owner, self.name)


if typing.TYPE_CHECKING:
    # TODO: Figure out if this type checks correctly, if not how do we make it type
    #       check correctly... or is it even possible at all?
    jsii_classproperty = property
else:

    class jsii_classproperty:
        def __init__(self, meth):
            pass

        def __set_name__(self, owner, name):
            self.name = name

        def __get__(self, instance, owner):
            return instance.__jsii_kernel__.sget(instance, self.name)

        def __set__(self, instance, value):
            instance.__jsii_kernel__.sset(instance, self.name, value)
