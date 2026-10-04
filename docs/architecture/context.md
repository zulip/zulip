# Diagrama de arquitectura preliminar - C4 Nivel 1

Este diagrama representa el contexto de Zulip y los actores relacionados con la mejora propuesta en el issue #7719: permitir notificar de forma puntual a un usuario mencionado que no está suscrito a un canal, sin modificar su suscripción.

```mermaid
flowchart LR

    autor["Miembro que menciona<br/><br/>Participa en conversaciones y<br/>menciona a otros usuarios"]

    zulip["Zulip<br/><br/>Plataforma de comunicación y colaboración<br/>organizada mediante canales y temas"]

    destino["Miembro mencionado<br/><br/>No está suscrito al canal,<br/>pero posee permiso de acceso"]

    admin["Administrador<br/><br/>Gestiona usuarios,<br/>canales y permisos"]

    autor -->|"Publica mensajes, menciona usuarios<br/>y solicita una notificación puntual"| zulip

    zulip -->|"Muestra conversaciones,<br/>avisos y estado de la acción"| autor

    zulip -->|"Envía una notificación puntual<br/>sin modificar su suscripción"| destino

    destino -->|"Accede a la conversación<br/>si posee los permisos requeridos"| zulip

    admin -->|"Configura usuarios,<br/>canales y permisos"| zulip