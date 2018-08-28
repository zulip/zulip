from typing import TypeVar, Callable, Optional, List, Dict, Union, Tuple, Any
from django.http import HttpResponse

ViewFuncT = TypeVar('ViewFuncT', bound=Callable[..., HttpResponse])

# See zerver/lib/validator.py for more details of Validators,
# including many examples
Validator = Callable[[str, object], Optional[str]]
ExtendedValidator = Callable[[str, str, object], Optional[str]]
RealmUserValidator = Callable[[int, List[int], bool], Optional[str]]

ProfileDataElement = Dict[str, Union[int, float, Optional[str]]]
ProfileData = List[ProfileDataElement]

FieldElement = Tuple[int, str, Validator, Callable[[Any], Any], str]
ExtendedFieldElement = Tuple[int, str, ExtendedValidator, Callable[[Any], Any], str]
UserFieldElement = Tuple[int, str, RealmUserValidator, Callable[[Any], Any], str]

FieldTypeData = List[Union[FieldElement, ExtendedFieldElement, UserFieldElement]]

ProfileFieldData = Dict[str, Dict[str, str]]
