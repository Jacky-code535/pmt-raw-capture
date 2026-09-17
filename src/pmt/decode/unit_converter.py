"""Restricted arithmetic expressions supplied by platform XML."""

import ast
import math
import operator
import re


OPERATORS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
             ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv,
             ast.Mod: operator.mod, ast.BitAnd: operator.and_, ast.BitOr: operator.or_,
             ast.BitXor: operator.xor}
COMPARISONS = {ast.Eq: operator.eq, ast.NotEq: operator.ne, ast.Lt: operator.lt,
               ast.LtE: operator.le, ast.Gt: operator.gt, ast.GtE: operator.ge}


class Formula:
    def __init__(self, expression):
        if not isinstance(expression, str) or len(expression) > 4096:
            raise ValueError("XML formula must be a string of at most 4096 characters")
        expression = re.sub(r"\$([A-Za-z_][A-Za-z_0-9]*)", r"\1", expression).strip()
        try:
            self.tree = ast.parse(expression, mode="eval").body
        except SyntaxError as error:
            raise ValueError("unsupported XML formula syntax: " + expression) from error
        if len(list(ast.walk(self.tree))) > 256:
            raise ValueError("XML formula exceeds complexity limit")
        allowed = {ast.BinOp, ast.UnaryOp, ast.Name, ast.Load, ast.Constant, ast.Compare, ast.IfExp, ast.Call,
                   ast.Pow, ast.LShift, ast.RShift, ast.USub, ast.UAdd, ast.Invert}
        allowed.update(OPERATORS)
        allowed.update(COMPARISONS)
        self.names = set()
        functions = set()
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Call):
                if not isinstance(node.func, ast.Name) or node.func.id != "sqrt" or len(node.args) != 1 or node.keywords:
                    raise ValueError("only sqrt(value) is supported in XML formulas")
                functions.add(node.func)
        for node in ast.walk(self.tree):
            if type(node) not in allowed and type(node).__name__ != "Num":
                raise ValueError("unsupported XML expression node: " + type(node).__name__)
            if isinstance(node, ast.Constant) and type(node.value) not in (int, float):
                raise ValueError("XML constants must be numeric")
            if isinstance(node, ast.Name) and node not in functions:
                self.names.add(node.id)

    def evaluate(self, variables):
        def visit(node):
            value = evaluate_node(node)
            if isinstance(value, int) and value.bit_length() <= 4096:
                return value
            if isinstance(value, float) and math.isfinite(value):
                return value
            raise ValueError("XML arithmetic exceeds numeric limits")

        def evaluate_node(node):
            if isinstance(node, ast.Call):
                return math.sqrt(visit(node.args[0]))
            if isinstance(node, ast.Constant) and type(node.value) in (int, float):
                return node.value
            if type(node).__name__ == "Num":
                return node.n
            if isinstance(node, ast.Name):
                return variables[node.id]
            if isinstance(node, ast.BinOp):
                left, right = visit(node.left), visit(node.right)
                if isinstance(node.op, ast.Pow):
                    if abs(right) > 64:
                        raise ValueError("XML exponent outside supported range")
                    return left ** right
                if isinstance(node.op, (ast.LShift, ast.RShift)):
                    if not isinstance(right, int) or not 0 <= right <= 64:
                        raise ValueError("XML shift outside 0..64")
                    return left << right if isinstance(node.op, ast.LShift) else left >> right
                if type(node.op) in OPERATORS:
                    return OPERATORS[type(node.op)](left, right)
            if isinstance(node, ast.UnaryOp):
                value = visit(node.operand)
                if isinstance(node.op, ast.USub):
                    return -value
                if isinstance(node.op, ast.UAdd):
                    return value
                if isinstance(node.op, ast.Invert):
                    return ~value
            if isinstance(node, ast.Compare):
                left = visit(node.left)
                for operation, comparator in zip(node.ops, node.comparators):
                    right = visit(comparator)
                    if type(operation) not in COMPARISONS or not COMPARISONS[type(operation)](left, right):
                        return False
                    left = right
                return True
            if isinstance(node, ast.IfExp):
                return visit(node.body if visit(node.test) else node.orelse)
            raise ValueError("unsupported XML expression node: " + type(node).__name__)

        value = visit(self.tree)
        if not isinstance(value, (int, float)):
            raise ValueError("XML formula did not produce a finite number")
        return value