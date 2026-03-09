package main

required_fields := [
  "owner",
  "requester",
  "objective",
  "success_criteria",
  "stop_gates",
]

deny[msg] {
  input.kind == "task_packet_v1"
  field := required_fields[_]
  not has_non_empty_field(field)
  msg := sprintf("missing or empty required field: %s", [field])
}

has_non_empty_field(field) {
  value := input[field]
  not is_empty(value)
}

is_empty(value) {
  value == null
}

is_empty(value) {
  is_string(value)
  trim(value) == ""
}

is_empty(value) {
  is_array(value)
  count(value) == 0
}

is_empty(value) {
  is_object(value)
  count(value) == 0
}
