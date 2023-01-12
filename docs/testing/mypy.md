# Python static type checker (mypy)

[mypy](http://mypy-lang.org/) is a compile-time static type checker
for Python, allowing optional, gradual typing of Python code. Zulip
was fully annotated with mypy's Python 2 syntax in 2016, before our
migration to Python 3 in late 2017. In 2018 and 2020, we migrated
essentially the entire codebase to the nice PEP 484 (Python 3 only)
and PEP 526 (Python 3.6) syntax for static types:

```python
user_dict: Dict[str, UserProfile] = {}

def get_user(email: str, realm: Realm) -> UserProfile:
    ... # Actual code of the function here
```

You can learn more about it at:

- The
  [mypy cheat sheet for Python 3](https://mypy.readthedocs.io/en/latest/cheat_sheet_py3.html)
  is the best resource for quickly understanding how to write the PEP
  484 type annotations used by mypy correctly.

- The
  [Python type annotation spec in PEP 484](https://www.python.org/dev/peps/pep-0484/).

- Our [blog post on being an early adopter of mypy][mypy-blog-post] from 2016.

- Our [best practices](#best-practices) section below.

The mypy type checker is run automatically as part of Zulip's Travis
CI testing process in the `backend` build.

[mypy-blog-post]: https://blog.zulip.org/2016/10/13/static-types-in-python-oh-mypy/

## Installing mypy

mypy is installed by default in the Zulip development environment.

## Running mypy on Zulip's code locally

To run mypy on Zulip's python code, you can run the command:

```bash
tools/run-mypy
```

Mypy outputs errors in the same style as a compiler would. For
example, if your code has a type error like this:

```python
foo = 1
foo = '1'
```

you'll get an error like this:

```console
test.py: note: In function "test":
test.py:200: error: Incompatible types in assignment (expression has type "str", variable has type "int")
```

## Mypy is there to find bugs in Zulip before they impact users

For the purposes of Zulip development, you can treat `mypy` like a
much more powerful linter that can catch a wide range of bugs. If,
after running `tools/run-mypy` on your Zulip branch, you get mypy
errors, it's important to get to the bottom of the issue, not just do
something quick to silence the warnings, before we merge the changes.
Possible explanations include:

- A bug in any new type annotations you added.
- A bug in the existing type annotations.
- A bug in Zulip!
- Some Zulip code is correct but confusingly reuses variables with
  different types.
- A bug in mypy (though this is increasingly rare as mypy is now
  fairly mature as a project).

Each explanation has its own solution, but in every case the result
should be solving the mypy warning in a way that makes the Zulip
codebase better. If you're having trouble, silence the warning with
an `Any` or `# type: ignore[code]` so you're not blocked waiting for help,
add a `# TODO: ` comment so it doesn't get forgotten in code review,
and ask for help in chat.zulip.org.

## Mypy stubs for third-party modules

For the Python standard library and some popular third-party modules,
the [typeshed project](https://github.com/python/typeshed) has
[stubs](https://github.com/python/mypy/wiki/Creating-Stubs-For-Python-Modules),
basically the equivalent of C header files defining the types used in
these Python APIs.

For other third-party modules that we call from Zulip, one either
needs to add an `ignore_missing_imports` entry in `pyproject.toml` in the
root of the project, letting `mypy` know that it's third-party code,
or add type stubs to the `stubs/` directory, which has type stubs that
mypy can use to type-check calls into that third-party module.

It's easy to add new stubs! Just read the docs, look at some of
existing examples to see how they work, and remember to remove the
`ignore_missing_imports` entry in `pyproject.toml` when you add them.

For any third-party modules that don't have stubs, `mypy` treats
everything in the third-party module as an `Any`, which is the right
model (one certainly wouldn't want to need stubs for everything just
to use `mypy`!), but means the code can't be fully type-checked.

## Working with types from django-stubs

For features that are difficult to be expressed with static type
annotations, type analysis is supplemented with mypy plugins. Zulip's
Python codebases uses the Django web framework, and such a plugin is
required in order for `mypy` to correctly infer the types of most code
interacting with Django model classes (i.e. code that accesses the
database).

We use the `mypy_django_plugin` plugin from the
[django-stubs](https://github.com/typeddjango/django-stubs) project,
which supports accurate type inference for classes like
`QuerySet`. For example, `Stream.objects.filter(realm=realm)` is
simple Django code to fetch all the streams in a realm. With this
plugin, mypy will correctly determine its type is `QuerySet[Stream]`,
aka a standard, lazily evaluated Django query object that can be
iterated through to access `Stream` objects, without the developer
needing to do an explicit annotation.

When declaring the types for functions that accept a `QuerySet`
object, you should always supply the model type that it accepts as the
type parameter.

```python
def foo(user: QuerySet[UserProfile]) -> None:
    ...
```

In cases where you need to type the return value from `.values_list`
or `.values` on a `QuerySet`, you can use the special
`django_stubs_ext.ValuesQuerySet` type.

For `.values_list`, the second type parameter will be the type of the
column.

```python
from django_stubs_ext import ValuesQuerySet

def get_book_page_counts() -> ValuesQuerySet[Book, int]:
    return Book.objects.filter().values_list("page_count", flat=True)
```

For `.values`, we prefer to define a `TypedDict` containing the
key-value pairs for the columns.

```python
from django_stubs_ext import ValuesQuerySet

class BookMetadata(TypedDict):
    id: int
    name: str

def get_book_meta_data(
    book_ids: List[int],
) -> ValuesQuerySet[Book, BookMetadata]:
    return Book.objects.filter(id__in=book_ids).values("name", "id")
```

When writing a helper function that returns the response from a test
client, it should be typed as `TestHttpResponse` instead of
`HttpResponse`. This type is only defined in the Django stubs, so it
has to be conditionally imported only when type
checking. Conventionally, we alias it as `TestHttpResponse`, which is
internally named `_MonkeyPatchedWSGIResponse` within django-stubs.

```python
from typing import TYPE_CHECKING
from zerver.lib.test_classes import ZulipTestCase

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedWSGIResponse as TestHttpResponse

class FooTestCase(ZulipTestCase):
    def helper(self) -> "TestHttpResponse":
        return self.client_get("/bar")
```

We sometimes encounter innaccurate type annotations in the Django
stubs project. We prefer to address these by [submitting a pull
request](https://github.com/typeddjango/django-stubs/pulls) to fix the
issue in the upstream project, just like we do with `typeshed` bugs.

## Using @overload to accurately describe variations

Sometimes, a function's type is most precisely expressed as a few
possibilities, and which possibility can be determined by looking at
the arguments. You can express that idea in a way mypy understands
using `@overload`. For example, `check_list` returns a `Validator`
function that verifies that an object is a list, raising an exception
if it isn't.

It supports being passed a `sub_validator`, which will verify that
each element in the list has a given type as well. One can express
the idea "If `sub_validator` validates that something is a `ResultT`,
`check_list(sub_validator)` validators that something is a
`List[ResultT]` as follows:

```python
@overload
def check_list(sub_validator: None, length: Optional[int]=None) -> Validator[List[object]]:
    ...
@overload
def check_list(sub_validator: Validator[ResultT],
               length: Optional[int]=None) -> Validator[List[ResultT]]:
    ...
def check_list(sub_validator: Optional[Validator[ResultT]]=None,
               length: Optional[int]=None) -> Validator[List[ResultT]]:
```

The first overload expresses the types for the case where no
`sub_validator` is passed, in which case all we know is that it
returns a `Validator[List[object]]`; whereas the second defines the
type logic for the case where we are passed a `sub_validator`.

**Warning:** Mypy only checks the body of an overloaded function
against the final signature and not against the more restrictive
`@overload` signatures. This allows some type errors to evade
detection by mypy:

```python
@overload
def f(x: int) -> int: ...
@overload
def f(x: str) -> int: ...  # oops
def f(x: Union[int, str]) -> Union[int, str]:
    return x

x: int = f("three!!")
```

Due to this potential for unsafety, we discourage overloading unless
it's absolutely necessary. Consider writing multiple functions with
different names instead.

See the [mypy overloading documentation][mypy-overloads] for more details.

[mypy-overloads]: https://mypy.readthedocs.io/en/stable/more_types.html#function-overloading

## Best practices

### When is a type annotation justified?

Usually in fully typed code, mypy will protect you from writing a type
annotation that isn't justified by the surrounding code. But when you
need to write annotations at the border between untyped and typed
code, keep in mind that **a type annotation should always represent a
guarantee,** not an aspiration. If you have validated that some value
is an `int`, it can go in an `int` annotated variable. If you are
going to validate it later, it should not. When in doubt, an `object`
annotation is always safe.

Mypy understands many Python constructs like `assert`, `if`,
`isinstance`, and logical operators, and uses them to automatically
narrow the type of validated objects in many cases.

```python
def f(x: object, y: Optional[str]) -> None:
    if isinstance(x, int):
        # Within this if block, mypy infers that x: int
        print(x + 1)
    assert y is not None
    # After that assert statement, mypy infers that y: str
    print(y.strip())
```

It won't be able do this narrowing if the validation is hidden behind
a function call, so sometimes it's helpful for a validation function
to return the type-narrowed value back to the caller even though the
caller already has it. (The validators in `zerver/lib/validator.py`
are examples of this pattern.)

### Avoid the `Any` type

Mypy provides the [`Any`
type](https://mypy.readthedocs.io/en/stable/dynamic_typing.html) for
interoperability with untyped code, but it is completely unchecked.
You can put an value of an arbitrary type into an expression of type
`Any`, and get an value of an arbitrary type out, and mypy will make
no effort to check that the input and output types match. So using
`Any` defeats the type safety that mypy would otherwise provide.

```python
x: Any = 5
y: str = x  # oops
print(y.strip())  # runtime error
```

If you think you need to use `Any`, consider the following safer
alternatives first:

- To annotate a dictionary where different keys correspond to values
  of different types, instead of writing `Dict[str, Any]`, try
  declaring a
  [**`dataclass`**](https://mypy.readthedocs.io/en/stable/additional_features.html#dataclasses)
  or a
  [**`TypedDict`**](https://mypy.readthedocs.io/en/stable/more_types.html#typeddict).

- If you're annotating a class or function that might be used with
  different data types at different call sites, similar to the builtin
  `List` type or the `sorted` function, [**generic
  types**](https://mypy.readthedocs.io/en/stable/generics.html) with
  `TypeVar` might be what you need.

- If you need to accept data of several specific possible types at a
  single site, you may want a [**`Union`
  type**](https://mypy.readthedocs.io/en/stable/kinds_of_types.html#union-types).
  `Union` is checked: before using `value: Union[str, int]` as a
  `str`, mypy requires that you validate it with an
  `instance(value, str)` test.

- If you really have no information about the type of a value, use the
  **`object` type**. Since every type is a subtype of `object`, you
  can correctly annotate any value as `object`. The [difference
  between `Any` and
  `object`](https://mypy.readthedocs.io/en/stable/dynamic_typing.html#any-vs-object)
  is that mypy will check that you safely validate an `object` with
  `isinstance` before using it in a way that expects a more specific
  type.

- A common way for `Any` annotations to sneak into your code is the
  interaction with untyped third-party libraries. Mypy treats any
  value imported from an untyped library as annotated with `Any`, and
  treats any type imported from an untyped library as equivalent to
  `Any`. Consider providing real type annotations for the library by
  [**writing a stub file**](#mypy-stubs-for-third-party-modules).

### Avoid `cast()`

The [`cast`
function](https://mypy.readthedocs.io/en/stable/type_narrowing.html#casts) lets you
provide an annotation that Mypy will not verify. Obviously, this is
completely unsafe in general.

```python
x = cast(str, 5)  # oops
print(x.strip())  # runtime error
```

Instead of using `cast`:

- You can use a [variable
  annotation](https://mypy.readthedocs.io/en/stable/type_inference_and_annotations.html#explicit-types-for-variables)
  to be explicit or to disambiguate types that mypy can check but
  cannot infer.

  ```python
  l: List[int] = []
  ```

- You can use an [`isinstance`
  test](https://mypy.readthedocs.io/en/stable/common_issues.html#complex-type-tests)
  to safely verify that a value really has the type you expect.

### Avoid `# type: ignore` comments

Mypy allows you to ignore any type checking error with a
[`# type: ignore`
comment](https://mypy.readthedocs.io/en/stable/common_issues.html#spurious-errors-and-locally-silencing-the-checker),
but you should avoid this in the absence of a very good reason, such
as a bug in mypy itself. If there are no safe options for dealing
with the error, prefer an unchecked `cast`, since its unsafety is
somewhat more localized.

Our linter requires all `# type: ignore` comments to be [scoped to the
specific error
code](https://mypy.readthedocs.io/en/stable/error_codes.html) being
ignored, and followed by an explanation such as a link to a GitHub
issue.

### Avoid other unchecked constructs

- As mentioned
  [above](#using-overload-to-accurately-describe-variations), we
  **discourage writing overloaded functions** because their bodies are
  not checked against the `@overload` signatures.

- **Avoid `Callable[..., T]`** (with literal ellipsis `...`), since
  mypy cannot check the types of arguments passed to it. Provide the
  specific argument types (`Callable[[int, str], T]`) in simple cases,
  or use [callback
  protocols](https://mypy.readthedocs.io/en/stable/protocols.html#callback-protocols)
  in more complex cases.

### Use `Optional` and `None` correctly

The [`Optional`
type](https://mypy.readthedocs.io/en/stable/cheat_sheet_py3.html#built-in-types)
is for optional values, which are values that could be `None`. For
example, `Optional[int]` is equivalent to `Union[int, None]`.

The `Optional` type is **not for optional parameters** (unless they
are also optional values as above). This signature does not use the
`Optional` type:

```python
def func(flag: bool = False) -> str:
    ...
```

A collection such as `List` should only be `Optional` if `None` would
have a different meaning than the natural meaning of an empty
collection. For example:

- An include list where the default is to include everything should be
  `Optional` with default `None`.
- An exclude list where the default is to exclude nothing should be
  non-`Optional` with default `[]`.

Don't test an `Optional` value using truthiness (`if value:`,
`not value`, `value or default_value`), especially when the type might
have falsy values other than `None`.

```python
s: Optional[str]
if not s:  # bad: are we checking for None or ""?
    ...
if s is None:  # good
    ...
```

### Read-only types

The basic Python collections
[`List`](https://docs.python.org/3/library/typing.html#typing.List),
[`Dict`](https://docs.python.org/3/library/typing.html#typing.Dict),
and [`Set`](https://docs.python.org/3/library/typing.html#typing.Set)
are mutable, but it's confusing for a function to mutate a collection
that was passed to it as an argument, especially by accident. To
avoid this, prefer annotating function parameters with read-only
types:

- [`Sequence`](https://docs.python.org/3/library/typing.html#typing.Sequence)
  instead of `List`,
- [`Mapping`](https://docs.python.org/3/library/typing.html#typing.Mapping)
  instead of `Dict`,
- [`AbstractSet`](https://docs.python.org/3/library/typing.html#typing.AbstractSet)
  instead of `Set`.

This is especially important for parameters with default arguments,
since a mutable default argument is confusingly shared between all
calls to the function.

```python
def f(items: Sequence[int] = []) -> int:
    items.append(1)  # mypy catches this mistake
    return sum(items)
```

In some cases the more general
[`Collection`](https://docs.python.org/3/library/typing.html#typing.Collection)
or
[`Iterable`](https://docs.python.org/3/library/typing.html#typing.Iterable)
types might be appropriate. (But don’t use `Iterable` for a value
that might be iterated multiple times, since a one-use iterator is
`Iterable` too.)

For example, if a function gets called with either a `list` or a `QuerySet`,
and it only iterates the object once, the parameter can be typed as `Iterable`.

```python
def f(items: Iterable[Realm]) -> None:
    for item in items:
        ...

realms_list: List[Realm] = [zulip, analytics]
realms_queryset: QuerySet[Realm] = Realm.objects.all()

f(realms_list)      # OK
f(realms_queryset)  # Also OK
```

A function's return type can be mutable if the return value is always
a freshly created collection, since the caller ends up with the only
reference to the value and can freely mutate it without risk of
confusion. But a read-only return type might be more appropriate for
a function that returns a reference to an existing collection.

Read-only types have the additional advantage of being [covariant
rather than
invariant](https://mypy.readthedocs.io/en/latest/common_issues.html#invariance-vs-covariance):
if `B` is a subtype of `A`, then `List[B]` may not be converted to
`List[A]`, but `Sequence[B]` may be converted to `Sequence[A]`.

### Typing decorators

A simple decorator that operates on functions of a fixed signature
works with no issues:

```python
def fancy(func: Callable[[str], str]) -> Callable[[int], str]:
    def wrapped_func(n: int) -> str:
        print("so fancy")
        return func(str(n))
    return wrapped_func

@fancy
def f(s: str) -> str:
    return s
```

A decorator with an argument also works:

```python
def fancy(message: str) -> Callable[[Callable[[str], str]], Callable[[int], str]]:
    def wrapper(func: Callable[[str], str]) -> Callable[[int], str]:
        def wrapped_func(n: int) -> str:
            print(message)
            return func(str(n))
        return wrapped_func
    return wrapper

@fancy("so fancy")
def f(s: str) -> str:
    return s
```

And a [generic
decorator](https://mypy.readthedocs.io/en/stable/generics.html#declaring-decorators)
that operates on functions of arbitrary signatures can be written
[with a `cast`](https://github.com/python/mypy/issues/1927) if the
output signature is always the same as the input signature:

```python
FuncT = TypeVar("FuncT", bound=Callable[..., object])

def fancy(func: FuncT) -> FuncT:
    def wrapped_func(*args: object, **kwargs: object) -> object:
        print("so fancy")
        return func(*args, **kwargs)
    return cast(FuncT, wrapped_func)  # https://github.com/python/mypy/issues/1927

@fancy
def f(s: str) -> str:
    return s
```

(A generic decorator with an argument would return
`Callable[[FuncT], FuncT]`.)

But Mypy doesn't yet support the advanced type annotations that would
be needed to correctly type generic signature-changing decorators,
such as `zerver.decorator.authenticated_json_view`, which passes an
extra argument to the inner function. For these decorators we must
unfortunately give up some type safety by falling back to
`Callable[..., T]`.

## Troubleshooting advice

All of our linters, including mypy, are designed to only check files
that have been added in Git (this is by design, since it means you
have untracked files in your Zulip checkout safely). So if you get a
`mypy` error like this after adding a new file that is referenced by
the existing codebase:

```console
mypy | zerver/models.py:1234: note: Import of 'zerver.lib.markdown_wrappers' ignored
mypy | zerver/models.py:1234: note: (Using --follow-imports=error, module not passed on command line)
```

The problem is that you need to `git add` the new file.
