# ctrl

Every call below is valid, so `lib.docaudit` must report nothing for this package.

| Function | Purpose |
|---|---|
| `vari(x, anything)` | Variadic: any listed names are fine |
| `fixed(alpha, beta)` | Listed names are formals |

Prose mentions `fixed()` and `vari()` with no arguments, and `stats::fixed(zzz = 1)` is another package.

```r
vari(1, 2, 3)               # variadic: any positional count is valid
fixed(1, 2, 3)              # 3 positionals, 3 formals
fixed(alp = 1, beta = "a")  # unique-prefix partial match
fixed(alpha = c(a = 1, b = 2), gamma = list(x = 1))  # nested names are not arguments
# fixed(bogus = 1)          # commented out
x <- "fixed(bogus = 1)"     # inside a string
f <- function(bogus = 1) fixed(bogus)
```

Inline `fixed(alpha = 1)` and `vari(x = 1, y = 2)` are valid too.
