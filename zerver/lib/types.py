from typing import TypeVar, Callable, Optional, List, Dict, Union, Tuple, Any
from typing_extensions import TypedDict
from django.http import HttpResponse

ViewFuncT = TypeVar('ViewFuncT', bound=Callable[..., HttpResponse])

# See zerver/lib/validator.py for more details of Validators,
# including many examples
Validator = Callable[[str, object], Optional[str]]
ExtendedValidator = Callable[[str, str, object], Optional[str]]
RealmUserValidator = Callable[[int, List[int], bool], Optional[str]]

ProfileDataElement = TypedDict('ProfileDataElement', {
    'id': int,
    'name': str,
    'type': int,
    'hint': Optional[str],
    'field_data': Optional[str],
    'order': int,
    'value': str,
    'rendered_value': Optional[str],
}, total=False)  # TODO: Can we remove this requirement?
ProfileData = List[ProfileDataElement]

FieldElement = Tuple[int, str, Validator, Callable[[Any], Any], str]
ExtendedFieldElement = Tuple[int, str, ExtendedValidator, Callable[[Any], Any], str]
UserFieldElement = Tuple[int, str, RealmUserValidator, Callable[[Any], Any], str]

ProfileFieldData = Dict[str, Union[Dict[str, str], str]]

UserDisplayRecipient = TypedDict('UserDisplayRecipient', {'email': str, 'full_name': str, 'short_name': str,
                                                          'id': int, 'is_mirror_dummy': bool})
DisplayRecipientT = Union[str, List[UserDisplayRecipient]]
