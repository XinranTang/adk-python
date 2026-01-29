"""Function script with bash-style argument parsing."""

import argparse
import inspect
import shlex
import types
import typing
from typing import Any, Callable, Dict, List, Tuple, Union

from . import models


def _bool_type(v: Union[str, bool]) -> bool:
  """Converts value to boolean for argparse."""
  if isinstance(v, bool):
    return v
  if v.lower() in ("yes", "true", "t", "y", "1"):
    return True
  if v.lower() in ("no", "false", "f", "n", "0"):
    return False
  raise argparse.ArgumentTypeError("Boolean value expected.")


def _unwrap_type(type_hint: Any) -> Any:
  """Unwraps Optional and Union types to get the underlying type."""
  origin = getattr(type_hint, "__origin__", None)
  if origin is typing.Union or (
      hasattr(types, "UnionType") and origin is types.UnionType
  ):
    args = getattr(type_hint, "__args__", [])
    non_none_args = [arg for arg in args if arg is not types.NoneType]
    if non_none_args:
      return _unwrap_type(non_none_args[0])
  return type_hint


def _add_flag_argument(
    parser: argparse.ArgumentParser,
    cli_name: str,
    dest_name: str,
    param: inspect.Parameter,
    type_hint: Any,
    nargs: Union[str, int, None] = None,
):
  """Adds a flag argument to the argparse parser.

  Args:
    parser: The argparse.ArgumentParser instance.
    cli_name: The name of the argument (e.g. "my-arg").
    dest_name: The name of the attribute in the parsed namespace (e.g.,
      "my_arg").
    param: The inspect.Parameter object for the argument.
    type_hint: The Python type hint for the argument.
    nargs: The number of arguments to consume.
  """
  flag = f"--{cli_name}"

  if type_hint == bool and nargs is None:
    if param.default:
      # If default is True, flag should negate it
      # --no-arg-name
      parser.add_argument(
          f"--no-{cli_name}", dest=dest_name, action="store_false"
      )
      # Also support --arg-name to explicitly set True?
      # Usually boolean flags are False by default -> store_true.
      # If True by default, it's tricky.
      # Let's just provide the negation.
    else:
      parser.add_argument(flag, dest=dest_name, action="store_true")
  else:
    parser.add_argument(
        flag,
        dest=dest_name,
        default=param.default,
        type=_bool_type if type_hint == bool else type_hint,
        nargs=nargs,
    )


def _parse_unknown_args(unknown: List[str]) -> Dict[str, Any]:
  """Parses unknown args as --key val pairs. Supports multiple values."""
  res = {}
  i = 0
  while i < len(unknown):
    arg = unknown[i]
    if arg.startswith("--"):
      key = arg[2:].replace("-", "_")  # Normalize CLI key to python identifier?
      i += 1
      values = []
      while i < len(unknown) and not unknown[i].startswith("--"):
        values.append(unknown[i])
        i += 1

      if not values:
        val = True
      elif len(values) == 1:
        val = values[0]
      else:
        val = values
      res[key] = val
    else:
      # Ignore positional unknown
      i += 1
  return res


def _normalize_args(args: Union[str, List[Any]]) -> List[str]:
  """Normalizes arguments to a list of strings."""
  if isinstance(args, str):
    args = shlex.split(args)

  # Flatten args to support ["--arg", ["val1", "val2"]]
  flat_args = []
  for arg in args:
    if isinstance(arg, list):
      flat_args.extend(arg)
    else:
      flat_args.append(arg)
  # Ensure all args are strings for argparse
  return [str(a) for a in flat_args]


class FunctionScript(models.Script):
  """Script defined by a callable function.

  Skills typically rely on models issuing bash commands, which often involves
  executing Python scripts on the file system. This can be insecure.
  `FunctionScript` allows routing these commands to a predefined Python function
  instead. This function could execute local logic or wrap an MCP (Model Context
  Protocol) endpoint. This acts as a bridge, preserving the standard skill
  interface (bash-style argument parsing) while enabling safer, controlled
  execution.

  The `src` attribute defaults to the source code of the bound function.

  Example:
    # Binding a function to SKILL.md scripts/
    def my_tool(x: int, verbose: bool = False):
      print(x, verbose)
    script = FunctionScript(my_tool)

    # Register in resources to map a script name to this function
    # skill.resources.scripts["my_tool.py"] = script

    # When the model invokes bash command `python my_tool.py 42 --verbose`:
    args, kwargs = script.to_function_input("42 --verbose")
    my_tool(*args, **kwargs)
  """

  def __init__(self, func: Callable[..., Any]):
    """Initializes the FunctionScript.

    Args:
      func: The callable function to wrap.
    """
    try:
      src = inspect.getsource(func)
    except (OSError, TypeError):
      src = str(func)
    super().__init__(src=src)
    self.func = func

  def to_function_input(
      self, args: Union[str, List[Any]]
  ) -> Tuple[Tuple[Any, ...], Dict[str, Any]]:
    """Converts bash-style argument string to function arguments.

    Args:
      args: The argument string (e.g., "--foo bar") or list of strings/values.

    Returns:
      A tuple of (args, kwargs) to pass to the function.
    """
    args = _normalize_args(args)

    sig = inspect.signature(self.func)
    parser = argparse.ArgumentParser(description=self.func.__doc__)

    # Track if we have *args or **kwargs
    has_var_keyword = False

    for name, param in sig.parameters.items():
      if name == "self":
        continue

      type_hint = param.annotation
      if type_hint is inspect.Parameter.empty:
        type_hint = str

      type_hint = _unwrap_type(type_hint)

      # Handle List types
      nargs = None
      origin = getattr(type_hint, "__origin__", None)
      if origin in (list, List, typing.Sequence) or type_hint == list:
        nargs = "*"
        inner_args = getattr(type_hint, "__args__", None)
        if inner_args:
          type_hint = inner_args[0]
        else:
          type_hint = str

      # Convert underscores to dashes for CLI flags
      cli_name = name.replace("_", "-")

      if param.kind in (
          inspect.Parameter.POSITIONAL_ONLY,
          inspect.Parameter.POSITIONAL_OR_KEYWORD,
      ):
        if param.default is inspect.Parameter.empty:
          # Required positional
          # Positionals don't use -- flags
          if type_hint == bool:
            parser.add_argument(name, type=_bool_type, nargs=nargs)
          else:
            parser.add_argument(name, type=type_hint, nargs=nargs)
        else:
          # Optional (has default) -> flag
          _add_flag_argument(parser, cli_name, name, param, type_hint, nargs)

      elif param.kind == inspect.Parameter.KEYWORD_ONLY:
        _add_flag_argument(parser, cli_name, name, param, type_hint, nargs)

      elif param.kind == inspect.Parameter.VAR_POSITIONAL:
        # Consume all remaining positionals
        parser.add_argument(
            name,
            nargs="*",
            type=type_hint if type_hint is not inspect.Parameter.empty else str,
        )

      elif param.kind == inspect.Parameter.VAR_KEYWORD:
        has_var_keyword = True

    if has_var_keyword:
      parsed_ns, unknown = parser.parse_known_args(args)
      kwargs_extra = _parse_unknown_args(unknown)
    else:
      parsed_ns = parser.parse_args(args)
      kwargs_extra = {}

    # Convert Namespace to dict
    parsed_dict = vars(parsed_ns)

    # Merge extra kwargs
    parsed_dict.update(kwargs_extra)

    # Reconstruct positional arguments to satisfy sig.bind order
    pos_args = []
    # Remaining args are keyword arguments
    kw_args = parsed_dict

    for name, param in sig.parameters.items():
      if name == "self":
        continue

      if param.kind in (
          inspect.Parameter.POSITIONAL_ONLY,
          inspect.Parameter.POSITIONAL_OR_KEYWORD,
      ):
        if name in kw_args:
          pos_args.append(kw_args.pop(name))

      elif param.kind == inspect.Parameter.VAR_POSITIONAL:
        if name in kw_args:
          pos_args.extend(kw_args.pop(name))

    bound = sig.bind(*pos_args, **kw_args)
    bound.apply_defaults()
    return bound.args, bound.kwargs
