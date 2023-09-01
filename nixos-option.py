import nix
import nix.util, nix.expr
from nix.expr import Type, Value
from dataclasses import dataclass
from typing import Callable
import sys

nix.util.settings["extra-experimental-features"] = "flakes"

def parse_attr_path(s: str) -> list[str]:
    res = []
    cur = ''
    i = 0
    while i < len(s):
        if s[i] == '.':
            res.append(cur)
            cur = ''
        elif s[i] == '"':
            i += 1
            while True:
                if i >= len(s):
                    raise ValueError(f"missing closing quote in selection path '{s}'")
                if s[i] == '"':
                    break
                cur += s[i]
                i += 1
        else:
            cur += s[i]
        i += 1
    if cur:
        res.append(cur)
    return res

def join_attr_path(path: list[str]) -> str:
    return ".".join(map(quoteAttribute, path))

def appendPath(prefix: str, suffix: str) -> str:
    if prefix == "":
        return suffix
    else:
        return prefix + "." + quoteAttribute(suffix)

def isVarName(s: str) -> bool:
    if len(s) == 0:
        return False
    c = s[0]
    if c.isdigit() or c == '-' or c == '\'':
        return False
    for i in s:
        if not ((i.isalpha()) or i.isdigit() or i in ['_', '-', '\'']):
            return False
    return True

def print_string_value(string: str) -> str:
    result = "\""
    for char in string:
        if char in ['\"', '\\']:
            result += "\\" + char
        elif char == '\n':
            result += "\\n"
        elif char == '\r':
            result += "\\r"
        elif char == '\t':
            result += "\\t"
        else:
            result += char
    result += "\""
    return result


@dataclass
class Context:
    configRoot: Value
    optionsRoot: Value

def isOption(v: Value) -> bool:
    try:
        return v["_type"].force({Type.string}) == "option"
    except TypeError:
        return False
    except KeyError:
        return False

def quoteAttribute(attr: str) -> str:
    if isVarName(attr):
        return attr
    else:
        return printStringValue(attr)

def forbiddenRecursionName(name: str) -> bool:
    return (name and name[0] == "_") or name == "haskellPackages"

def recurse(f: Callable[[str, Value | Exception], bool], v: Value, path: str) -> None:
    try:
        evaluated: Value | Exception = v.force()
    except Exception as e:
        evaluated = e
    if not f(path, evaluated):
        return
    if isinstance(evaluated, Exception):
        return
    if evaluated.get_type() is not Types.attrs:
        return
    for name in evaluated:
        if not forbiddenRecursionName(name):
            recurse(f, evaluated[name], appendPath(path, name))
       
       

def optionTypeIs(v: Value, soughtType: str) -> bool:
    try:
        return v["type"]["name"].force({Type.string}) == soughtType
    except TypeError:
        return False
    except KeyError:
        return False

def isAggregateOptionType(v: Value) -> bool:
    return optionTypeIs(v, "attrsOf") or optionTypeIs(v, "listOf")

def getSubOptions(option: Value) -> Value:
    # todo: doesn't match c++
    return option["type"]["getSubOptions"]([])

def findAlongOptionPath(ctx: Context, path: str) -> (Value, str):
    tokens = path.split(".") # todo: parseAttrPath
    v = ctx.optionsRoot
    processedPath = []
    for i, attr in enumerate(tokens):
        lastAttribute = i == len(tokens) - 1
        v.force_type()
        if attr == "":
            raise RuntimeError("empty attribute name")
        if isOption(v) and optionTypeIs(v, "submodule"):
            v = getSubOptions(v)
        if isOption(v) and isAggregateOptionType(v):
            subOptions = getSubOptions(v)
            if lastAttribute and len(subOptions) == 0:
                break
            v = subOptions
        else:
            v = v[attr]
        processedPath.append(attr)
    # todo toAttrPath
    return (v, ".".join(processedPath))

def findAttrAlongPath(path: str, root: Value) -> Value:
    tokens = path.split(".")
    v = root
    for attr in tokens:
        v = v[attr]
    return v

def mapOptions(f: Callable[[str], None], path: str) -> None:
    (option, path) = findAlongOptionPath(path)
    def rec(path: str, v: Value | Exception) -> bool:
        isOpt = isinstance(v, Exception) or isOption(v)
        if isOpt:
            f(path)
        return not isOpt
    recurse(rec, option, path)

def mapConfigValuesInOption(
        f: Callable[[str, Value | Exception], None],
        path: str, ctx: Context) -> None:
    try:
        # todo implement findAlongAttrPath
        option = findAlongAttrPath(path, cfg.configRoot)[0]
     except Exception as e:
         f(path, e)
         return
    def rec(path: str, v: Value | Exception) -> bool:
        leaf = isinstance(v, Exception) or v.get_type() is not Types.attrs
        if not leaf:
            return True
        f(path, v)
        return False
    recurse(rec, option, path)

def describeError(e: Exception) -> str:
    return "«error: " + str(e) + "»"

def describeDerivation(v: Value) -> None:
    try:
        drvPath = v["drvPath"].force({Type.string})
        print("«derivation: " + drvPath + "»")
    except Exception as e:
        describeError(e)

def printValue(maybeValue: Evaluate | Exception, path: str) -> None:
    ...

# todo streams
def printList(v: Value) -> None:
    print("[")
    for i in v:
        printValue(i, "")
        print(",")
    print("]")

def printOption(ctx: Context, path: str, option: Value) -> None:
    print("Value:")
    print(findAttrAlongPath(path, ctx.configRoot).force(deep=True))
    print("\nDefault:")
    print(option["default"].force(deep=True))
    print("\nType:")
    print(option["type"]["description"])
    if "example" in option:
        print("\nExample:")
        print(option["example"].force(deep=True))
    print("\nDescription:")
    print(option["description"].force(deep=True))
    print("\nDeclarations:")
    print(option["declarations"].force(deep=True))
    print("\nDefined by:")
    print(option["files"].force(deep=True))

def printListing(v: Value) -> None:
    print("This attribute set contains:")
    for name in v:
        if name and name[0] != '_':
            print(name)

def printOne(ctx: Context, path: str):
    option, result_path = findAlongOptionPath(ctx, path)
    option.force_type()
    if path != result_path:
        print("Note: showing", result_path, "instead of", path)
    if isOption(option):
        printOption(ctx, result_path, option)
    else:
        printListing(option)


def main(args):
    dotfiles = nix.eval("builtins.getFlake")("/home/yorick/dotfiles")
    root = dotfiles["nixosConfigurations"]["blackadder"]
    configRoot = root["config"]
    optionsRoot = root["options"]
    ctx = Context(configRoot, optionsRoot)
    #print(dotfiles["nixosConfigurations"]["blackadder"]["config"]["boot"]["kernelModules"].force(deep=True))
    # todo recursive
    if len(args) == 0:
        pass
    for arg in args:
        printOne(ctx, arg)

main(sys.argv[1:])




