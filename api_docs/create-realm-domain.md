Add organization domain

{generate_code_example(curl)|/realm/domains|example|user=hamlet}

Add a domain to the organization. This allows users with email addresses
belonging to the specified domain to join the organization.

Parameters

domain (string) — The domain to add to the organization.

allow_subdomains (boolean) — Whether subdomains of this domain are allowed.

Example response

{
  "result": "success",
  "msg": ""
}