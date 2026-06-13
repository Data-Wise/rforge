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

# property type that does not resolve in scanned source -> prop_type_unresolvable
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

# method() on a generic not defined/imported here + no methods_register() anywhere
# -> dangling_method AND missing_methods_register
method(external_generic, mediator_model) <- function(x, ...) x
