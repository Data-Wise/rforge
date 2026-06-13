#' A mediator model
#'
#' @export
MediatorModel <- new_class("MediatorModel",
  properties = list(
    n_obs = class_numeric,
    label = class_character
  ),
  validator = function(self) {
    if (self@n_obs < 0) {
      return("n_obs must be non-negative")
    }
    character(0)
  }
)

compute_effect <- new_generic("compute_effect", "model")

method(compute_effect, MediatorModel) <- function(model, ...) {
  model@n_obs
}

.onLoad <- function(libname, pkgname) {
  methods_register()
}
