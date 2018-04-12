from typing import TypeVar, Callable, Optional, List, Dict, Union
from django.http import HttpResponse

ViewFuncT = TypeVar('ViewFuncT', bound=Callable[..., HttpResponse])

# See zerver/lib/validator.py for more details of Validators,
# including many examples
Validator = Callable[[str, object], Optional[str]]

ProfileDataElement = Dict[str, Union[int, float, Optional[str]]]
ProfileData = List[ProfileDataElement]
