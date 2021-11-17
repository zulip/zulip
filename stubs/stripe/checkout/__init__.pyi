from typing import Any, Dict, List, Optional

class Session:
    id: str

    customer: str
    metadata: Dict[str, Any]
    setup_intent: str
    url: str
    @staticmethod
    def create(
        cancel_url: str,
        success_url: str,
        mode: str,
        payment_method_types: List[str],
        customer: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        setup_intent_data: Optional[Dict[str, Any]] = None,
    ) -> Session: ...
    @staticmethod
    def list(limit: int = ...) -> List[Session]: ...
    def to_dict_recursive(self) -> Dict[str, Any]: ...
