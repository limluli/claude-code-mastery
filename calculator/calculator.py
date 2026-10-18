"""간단한 GUI 계산기 (tkinter, 표준 라이브러리만 사용)."""

import ast
import operator
import tkinter as tk
from tkinter import messagebox

# 허용된 연산자만 평가한다 (eval 사용 금지)
OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def safe_eval(expression: str) -> float:
    """사칙연산 수식 문자열을 안전하게 계산한다."""

    def _eval(node):
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in OPERATORS:
            return OPERATORS[type(node.op)](_eval(node.left), _eval(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in OPERATORS:
            return OPERATORS[type(node.op)](_eval(node.operand))
        raise ValueError("잘못된 수식입니다.")

    normalized = expression.replace("×", "*").replace("÷", "/").replace("%", "/100")
    tree = ast.parse(normalized, mode="eval")
    return _eval(tree)


class Calculator(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("계산기")
        self.resizable(False, False)
        self.configure(bg="#1e1e1e")

        self.expression = ""
        self.display_var = tk.StringVar(value="0")

        self._build_display()
        self._build_buttons()
        self.bind("<Key>", self._on_key)
        self.bind("<Return>", lambda _e: self._calculate())
        self.bind("<BackSpace>", lambda _e: self._backspace())
        self.bind("<Escape>", lambda _e: self._clear())

    def _build_display(self):
        display = tk.Label(
            self,
            textvariable=self.display_var,
            anchor="e",
            font=("Segoe UI", 28),
            bg="#1e1e1e",
            fg="white",
            padx=16,
            pady=20,
        )
        display.grid(row=0, column=0, columnspan=4, sticky="nsew")

    def _build_buttons(self):
        layout = [
            ["C", "⌫", "%", "÷"],
            ["7", "8", "9", "×"],
            ["4", "5", "6", "-"],
            ["1", "2", "3", "+"],
            ["0", ".", "=", ""],
        ]
        for r, row in enumerate(layout, start=1):
            for c, label in enumerate(row):
                if not label:
                    continue
                if label == "C":
                    command = self._clear
                elif label == "⌫":
                    command = self._backspace
                elif label == "=":
                    command = self._calculate
                else:
                    command = lambda v=label: self._append(v)

                if label in ("C", "⌫", "%"):
                    bg, fg = "#a5a5a5", "black"
                elif label in ("÷", "×", "-", "+", "="):
                    bg, fg = "#f5a623", "white"
                else:
                    bg, fg = "#333333", "white"

                tk.Button(
                    self,
                    text=label,
                    command=command,
                    font=("Segoe UI", 18),
                    width=4,
                    height=2,
                    bg=bg,
                    fg=fg,
                    activebackground="#555555",
                    relief="flat",
                ).grid(row=r, column=c, padx=3, pady=3, sticky="nsew")

    def _append(self, value: str):
        self.expression += value
        self.display_var.set(self.expression)

    def _backspace(self):
        self.expression = self.expression[:-1]
        self.display_var.set(self.expression or "0")

    def _clear(self):
        self.expression = ""
        self.display_var.set("0")

    def _calculate(self):
        if not self.expression:
            return
        try:
            result = safe_eval(self.expression)
        except ZeroDivisionError:
            messagebox.showerror("오류", "0으로 나눌 수 없습니다.")
            self._clear()
            return
        except (ValueError, SyntaxError):
            messagebox.showerror("오류", "잘못된 수식입니다.")
            self._clear()
            return

        if isinstance(result, float) and result.is_integer():
            result = int(result)
        self.expression = str(result)
        self.display_var.set(self.expression)

    def _on_key(self, event):
        char = event.char
        if char in "0123456789.+-*/%":
            mapping = {"*": "×", "/": "÷"}
            self._append(mapping.get(char, char))
        elif char == "=":
            self._calculate()


if __name__ == "__main__":
    Calculator().mainloop()
