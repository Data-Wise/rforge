# class name snake_case (bad) -> class_name_case
mediator_model <- new_class("mediator_model",
  properties = list(
    n_obs = class_numeric,
    BadProp = class_character   # prop name not snake_case -> prop_name_case
  )
)
# NOTE: no validator= on a typed-properties class -> missing_validator

# bound var name does not match the name= string -> class_name_mismatch
Estimator <- new_class("Estimater", properties = list(value = class_numeric))

# generic name UpperCamelCase (bad) -> generic_name_case
ComputeEffect <- new_generic("ComputeEffect", "x")

# exported but undocumented (NAMESPACE export(undocumented_class)) -> undocumented_export
undocumented_class <- new_class("UndocumentedClass")

# property type that does not resolve from scanned source -> prop_type_unresolvable.
# `NoSuchClass` is NOT created via new_class(), so the static scanner can't resolve
# it (not in the defined-classes set); we bind it to a real S7 type so the package
# still LOADS at runtime (the runtime pass needs a clean load_all).
NoSuchClass <- S7::class_character
TypedThing <- new_class("TypedThing",
  properties = list(ref = NoSuchClass)
)

# validator that returns TRUE/FALSE instead of character()/NULL -> validator_return_shape
Validated <- new_class("Validated",
  properties = list(x = class_numeric),
  validator = function(self) {
    return(TRUE)
  }
)

# validator whose body is a constant NULL -> never inspects self, so it can never
# reject any value: present but provably NOT enforcing -> validator_not_enforcing
# (runtime family). The runtime pass is what flags this one.
NonEnforcing <- new_class("NonEnforcing",
  properties = list(y = class_numeric),
  validator = function(self) {
    NULL
  }
)

# method() on a generic not defined/imported here + no register call anywhere
# -> dangling_method AND missing_methods_register.
# `external_generic` is bound via an ALIAS (not a literal `new_generic(` call) so
# the static scanner still treats it as dangling, while the package LOADS at
# runtime (the runtime pass needs load_all to succeed). It has a method, so it is
# NOT a dead generic at runtime.
.make_generic <- S7::new_generic
external_generic <- .make_generic("external_generic", "x")
method(external_generic, mediator_model) <- function(x, ...) x
