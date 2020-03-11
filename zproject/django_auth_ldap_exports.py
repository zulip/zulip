from django_auth_ldap.config import (
    ActiveDirectoryGroupType,
    GroupOfNamesType,
    GroupOfUniqueNamesType,
    LDAPGroupQuery,
    LDAPSearch,
    LDAPSearchUnion,
    MemberDNGroupType,
    NestedActiveDirectoryGroupType,
    NestedGroupOfNamesType,
    NestedGroupOfUniqueNamesType,
    NestedMemberDNGroupType,
    NestedOrganizationalRoleGroupType,
    OrganizationalRoleGroupType,
    PosixGroupType,
)

# Suppress pyflakes warnings about unused modules.
assert (
    LDAPSearch
    and LDAPSearchUnion
    and LDAPGroupQuery
    and PosixGroupType
    and MemberDNGroupType
    and NestedMemberDNGroupType
    and GroupOfNamesType
    and NestedGroupOfNamesType
    and GroupOfUniqueNamesType
    and NestedGroupOfUniqueNamesType
    and ActiveDirectoryGroupType
    and NestedActiveDirectoryGroupType
    and OrganizationalRoleGroupType
    and NestedOrganizationalRoleGroupType
)
