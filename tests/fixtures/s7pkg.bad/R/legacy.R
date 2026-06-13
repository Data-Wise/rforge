# S4 leftovers co-residing with new_class -> legacy_s4_in_s7
setClass("OldThing", representation(a = "numeric"))
setGeneric("oldGen", function(x) standardGeneric("oldGen"))

# R5 / R6 leftover -> legacy_r5_in_s7
Counter <- R6::R6Class("Counter", public = list(n = 0))

# S3 generic dispatching (heuristic) -> legacy_s3_generic
print.mediator_model <- function(x, ...) {
  UseMethod("print")
}
